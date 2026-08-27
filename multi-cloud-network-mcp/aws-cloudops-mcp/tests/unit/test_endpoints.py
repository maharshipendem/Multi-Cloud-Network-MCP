from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.endpoints import list_vpc_endpoint_services, list_vpc_endpoints
from aws_cloudops_mcp.models.network_resources import MAX_POLICY_DOCUMENT_CHARS


@pytest.fixture
def endpoint_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        rt = ec2.create_route_table(VpcId=vpc["VpcId"])["RouteTable"]

        gateway_endpoint = ec2.create_vpc_endpoint(
            VpcId=vpc["VpcId"],
            ServiceName="com.amazonaws.us-east-1.s3",
            VpcEndpointType="Gateway",
            RouteTableIds=[rt["RouteTableId"]],
        )["VpcEndpoint"]

        interface_endpoint = ec2.create_vpc_endpoint(
            VpcId=vpc["VpcId"],
            ServiceName="com.amazonaws.us-east-1.ec2",
            VpcEndpointType="Interface",
            SubnetIds=[subnet["SubnetId"]],
            PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": []}),
        )["VpcEndpoint"]

        yield {
            "vpc_id": vpc["VpcId"],
            "subnet_id": subnet["SubnetId"],
            "route_table_id": rt["RouteTableId"],
            "gateway_endpoint_id": gateway_endpoint["VpcEndpointId"],
            "interface_endpoint_id": interface_endpoint["VpcEndpointId"],
        }


def test_list_vpc_endpoints_gateway_type(
    client_factory: ClientFactory, endpoint_fixture: dict[str, str]
) -> None:
    endpoints = list_vpc_endpoints(
        client_factory, region="us-east-1", vpc_id=endpoint_fixture["vpc_id"]
    )
    gw = next(e for e in endpoints if e.vpc_endpoint_id == endpoint_fixture["gateway_endpoint_id"])
    assert gw.vpc_endpoint_type == "Gateway"
    assert endpoint_fixture["route_table_id"] in gw.route_table_ids


def test_list_vpc_endpoints_interface_type(
    client_factory: ClientFactory, endpoint_fixture: dict[str, str]
) -> None:
    endpoints = list_vpc_endpoints(
        client_factory, region="us-east-1", vpc_id=endpoint_fixture["vpc_id"]
    )
    iface = next(
        e for e in endpoints if e.vpc_endpoint_id == endpoint_fixture["interface_endpoint_id"]
    )
    assert iface.vpc_endpoint_type == "Interface"
    assert endpoint_fixture["subnet_id"] in iface.subnet_ids


def test_policy_document_omitted_by_default(
    client_factory: ClientFactory, endpoint_fixture: dict[str, str]
) -> None:
    endpoints = list_vpc_endpoints(
        client_factory, region="us-east-1", vpc_id=endpoint_fixture["vpc_id"]
    )
    iface = next(
        e for e in endpoints if e.vpc_endpoint_id == endpoint_fixture["interface_endpoint_id"]
    )
    assert iface.policy_document is None
    assert iface.policy_document_truncated is False


def test_policy_document_included_when_requested(
    client_factory: ClientFactory, endpoint_fixture: dict[str, str]
) -> None:
    endpoints = list_vpc_endpoints(
        client_factory,
        region="us-east-1",
        vpc_id=endpoint_fixture["vpc_id"],
        include_policies=True,
    )
    iface = next(
        e for e in endpoints if e.vpc_endpoint_id == endpoint_fixture["interface_endpoint_id"]
    )
    assert iface.policy_document is not None
    assert json.loads(iface.policy_document)["Version"] == "2012-10-17"
    assert iface.policy_document_truncated is False


def test_policy_document_truncated_past_size_cap(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.1.0.0/16")["Vpc"]
        huge_policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [{"Sid": f"s{i}", "Effect": "Allow"} for i in range(500)],
            }
        )
        assert len(huge_policy) > MAX_POLICY_DOCUMENT_CHARS
        ep = ec2.create_vpc_endpoint(
            VpcId=vpc["VpcId"],
            ServiceName="com.amazonaws.us-east-1.s3",
            VpcEndpointType="Gateway",
            PolicyDocument=huge_policy,
        )["VpcEndpoint"]

        endpoints = list_vpc_endpoints(
            client_factory, region="us-east-1", vpc_id=vpc["VpcId"], include_policies=True
        )
        match = next(e for e in endpoints if e.vpc_endpoint_id == ep["VpcEndpointId"])
        assert match.policy_document_truncated is True
        assert len(match.policy_document) == MAX_POLICY_DOCUMENT_CHARS


def test_list_vpc_endpoints_zero_resources_for_unmatched_vpc(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert (
            list_vpc_endpoints(client_factory, region="us-east-1", vpc_id="vpc-doesnotexist") == []
        )


def test_list_vpc_endpoint_services_includes_aws_services(client_factory: ClientFactory) -> None:
    with mock_aws():
        services = list_vpc_endpoint_services(client_factory, region="us-east-1")
        assert any(s.service_name.endswith(".s3") for s in services)
        assert all(s.region == "us-east-1" for s in services)
