from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.nat import list_nat_gateways


@pytest.fixture
def nat_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        nat = ec2.create_nat_gateway(SubnetId=subnet["SubnetId"], ConnectivityType="private")[
            "NatGateway"
        ]
        yield {
            "vpc_id": vpc["VpcId"],
            "subnet_id": subnet["SubnetId"],
            "nat_id": nat["NatGatewayId"],
        }


def test_list_nat_gateways_filters_by_vpc(
    client_factory: ClientFactory, nat_fixture: dict[str, str]
) -> None:
    nats = list_nat_gateways(client_factory, region="us-east-1", vpc_id=nat_fixture["vpc_id"])
    assert len(nats) == 1
    nat = nats[0]
    assert nat.nat_gateway_id == nat_fixture["nat_id"]
    assert nat.subnet_id == nat_fixture["subnet_id"]
    assert nat.connectivity_type == "private"
    assert nat.account_id == "123456789012"


def test_list_nat_gateways_filters_by_subnet(
    client_factory: ClientFactory, nat_fixture: dict[str, str]
) -> None:
    nats = list_nat_gateways(client_factory, region="us-east-1", subnet_id=nat_fixture["subnet_id"])
    assert [n.nat_gateway_id for n in nats] == [nat_fixture["nat_id"]]


def test_list_nat_gateways_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_nat_gateways(client_factory, region="us-east-1") == []


def test_nat_gateway_failure_fields_present_in_model(
    client_factory: ClientFactory, nat_fixture: dict[str, str]
) -> None:
    """failure_code/failure_message are surfaced when AWS reports a failed
    NAT gateway; moto always reports success, so this only proves the
    normalized model carries the fields (default None) rather than
    silently dropping them if AWS ever populates them."""
    nats = list_nat_gateways(client_factory, region="us-east-1", vpc_id=nat_fixture["vpc_id"])
    assert nats[0].failure_code is None
    assert nats[0].failure_message is None
    assert hasattr(nats[0], "failure_code")
    assert hasattr(nats[0], "failure_message")
