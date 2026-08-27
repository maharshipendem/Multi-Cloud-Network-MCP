from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.gateways import (
    list_egress_only_internet_gateways,
    list_internet_gateways,
)


@pytest.fixture
def igw_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        igw = ec2.create_internet_gateway()["InternetGateway"]
        ec2.attach_internet_gateway(InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc["VpcId"])
        ec2.create_tags(
            Resources=[igw["InternetGatewayId"]], Tags=[{"Key": "Name", "Value": "test-igw"}]
        )
        eigw = ec2.create_egress_only_internet_gateway(VpcId=vpc["VpcId"])[
            "EgressOnlyInternetGateway"
        ]
        yield {
            "vpc_id": vpc["VpcId"],
            "igw_id": igw["InternetGatewayId"],
            "eigw_id": eigw["EgressOnlyInternetGatewayId"],
        }


def test_list_internet_gateways_filters_by_vpc(
    client_factory: ClientFactory, igw_fixture: dict[str, str]
) -> None:
    igws = list_internet_gateways(client_factory, region="us-east-1", vpc_id=igw_fixture["vpc_id"])
    assert len(igws) == 1
    igw = igws[0]
    assert igw.internet_gateway_id == igw_fixture["igw_id"]
    assert igw.tags == {"Name": "test-igw"}
    assert igw.account_id == "123456789012"
    assert len(igw.attachments) == 1
    assert igw.attachments[0].vpc_id == igw_fixture["vpc_id"]
    assert igw.attachments[0].state == "available"


def test_list_internet_gateways_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_internet_gateways(client_factory, region="us-east-1") == []


def test_list_egress_only_internet_gateways(
    client_factory: ClientFactory, igw_fixture: dict[str, str]
) -> None:
    eigws = list_egress_only_internet_gateways(client_factory, region="us-east-1")
    match = next(e for e in eigws if e.egress_only_internet_gateway_id == igw_fixture["eigw_id"])
    assert any(a.vpc_id == igw_fixture["vpc_id"] for a in match.attachments)
