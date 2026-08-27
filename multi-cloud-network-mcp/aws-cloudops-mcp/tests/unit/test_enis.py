from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.enis import list_network_interfaces


@pytest.fixture
def eni_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        sg = ec2.create_security_group(
            GroupName="eni-sg", Description="eni sg", VpcId=vpc["VpcId"]
        )["GroupId"]
        eni = ec2.create_network_interface(
            SubnetId=subnet["SubnetId"],
            Description="test eni",
            Groups=[sg],
        )["NetworkInterface"]
        yield {
            "vpc_id": vpc["VpcId"],
            "subnet_id": subnet["SubnetId"],
            "sg_id": sg,
            "eni_id": eni["NetworkInterfaceId"],
        }


def test_list_network_interfaces_normalizes_fields(
    client_factory: ClientFactory, eni_fixture: dict[str, str]
) -> None:
    enis = list_network_interfaces(
        client_factory, region="us-east-1", vpc_id=eni_fixture["vpc_id"]
    )
    match = next(e for e in enis if e.network_interface_id == eni_fixture["eni_id"])

    assert match.subnet_id == eni_fixture["subnet_id"]
    assert match.vpc_id == eni_fixture["vpc_id"]
    assert match.description == "test eni"
    assert eni_fixture["sg_id"] in match.security_group_ids
    assert match.private_ip_address


def test_list_network_interfaces_filters_by_subnet(
    client_factory: ClientFactory, eni_fixture: dict[str, str]
) -> None:
    enis = list_network_interfaces(
        client_factory, region="us-east-1", subnet_id=eni_fixture["subnet_id"]
    )
    assert [e.network_interface_id for e in enis] == [eni_fixture["eni_id"]]


def test_list_network_interfaces_zero_resources_for_unmatched_vpc(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        result = list_network_interfaces(
            client_factory, region="us-east-1", vpc_id="vpc-doesnotexist"
        )
        assert result == []
