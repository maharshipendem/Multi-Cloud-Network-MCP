from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.peering import list_vpc_peering_connections


@pytest.fixture
def peering_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc_a = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        vpc_b = ec2.create_vpc(CidrBlock="10.1.0.0/16")["Vpc"]
        pcx = ec2.create_vpc_peering_connection(VpcId=vpc_a["VpcId"], PeerVpcId=vpc_b["VpcId"])[
            "VpcPeeringConnection"
        ]
        yield {
            "vpc_a": vpc_a["VpcId"],
            "vpc_b": vpc_b["VpcId"],
            "pcx_id": pcx["VpcPeeringConnectionId"],
        }


def test_list_vpc_peering_connections_visible_from_requester_side(
    client_factory: ClientFactory, peering_fixture: dict[str, str]
) -> None:
    result = list_vpc_peering_connections(
        client_factory, region="us-east-1", vpc_id=peering_fixture["vpc_a"]
    )
    assert [p.vpc_peering_connection_id for p in result] == [peering_fixture["pcx_id"]]
    assert result[0].requester.vpc_id == peering_fixture["vpc_a"]
    assert result[0].accepter.vpc_id == peering_fixture["vpc_b"]


def test_list_vpc_peering_connections_visible_from_accepter_side(
    client_factory: ClientFactory, peering_fixture: dict[str, str]
) -> None:
    """A peering connection must be discoverable by querying the VPC on
    either side, not just the requester -- this exercises the
    accepter-side filter merge in aws.peering.list_vpc_peering_connections."""
    result = list_vpc_peering_connections(
        client_factory, region="us-east-1", vpc_id=peering_fixture["vpc_b"]
    )
    assert [p.vpc_peering_connection_id for p in result] == [peering_fixture["pcx_id"]]


def test_list_vpc_peering_connections_zero_resources_for_account_with_none(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        assert list_vpc_peering_connections(client_factory, region="us-east-1") == []
