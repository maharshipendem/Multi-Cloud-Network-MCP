from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.networking import (
    _normalize_route,
    list_route_tables,
    list_subnets,
    list_vpcs,
)
from aws_cloudops_mcp.exceptions import InvalidRegionError


@pytest.fixture
def ec2_resources(client_factory: ClientFactory) -> dict[str, str]:
    """Create a VPC, subnet, and route table in moto's mocked EC2, tagged for lookup.

    Wraps its own ``mock_aws()`` context (rather than relying on a decorator)
    so the mocked backend is guaranteed active for the whole test body,
    regardless of pytest fixture-vs-decorator ordering.
    """
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")

        vpc = ec2.create_vpc(CidrBlock="10.42.0.0/16")["Vpc"]
        vpc_id = vpc["VpcId"]
        ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "test-vpc"}])

        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.42.1.0/24")["Subnet"]
        subnet_id = subnet["SubnetId"]
        ec2.create_tags(Resources=[subnet_id], Tags=[{"Key": "Name", "Value": "test-subnet"}])

        route_table = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]
        route_table_id = route_table["RouteTableId"]
        igw = ec2.create_internet_gateway()["InternetGateway"]
        igw_id = igw["InternetGatewayId"]
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        ec2.create_route(
            RouteTableId=route_table_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id
        )

        yield {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "route_table_id": route_table_id,
            "igw_id": igw_id,
        }


def test_list_vpcs_returns_normalized_vpc(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    result = list_vpcs(client_factory, region="us-east-1")
    match = next(v for v in result.data if v.vpc_id == ec2_resources["vpc_id"])

    assert match.cidr_block == "10.42.0.0/16"
    assert match.state == "available"
    assert match.tags == {"Name": "test-vpc"}
    assert match.region == "us-east-1"
    assert match.account_id == "123456789012"
    assert match.observed_at
    assert isinstance(match.is_default, bool)
    assert result.warnings == []


def test_list_vpcs_include_dns_attributes(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    result = list_vpcs(client_factory, region="us-east-1", include_dns_attributes=True)
    match = next(v for v in result.data if v.vpc_id == ec2_resources["vpc_id"])

    assert match.enable_dns_support is not None
    assert match.enable_dns_hostnames is not None
    assert result.warnings == []


def test_list_vpcs_filters_by_vpc_ids(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    result = list_vpcs(client_factory, region="us-east-1", vpc_ids=[ec2_resources["vpc_id"]])
    assert [v.vpc_id for v in result.data] == [ec2_resources["vpc_id"]]


@mock_aws
def test_list_vpcs_rejects_invalid_region(client_factory: ClientFactory) -> None:
    with pytest.raises(InvalidRegionError):
        list_vpcs(client_factory, region="not-a-region")


def test_list_subnets_returns_normalized_subnet(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    subnets = list_subnets(client_factory, region="us-east-1", vpc_id=ec2_resources["vpc_id"])

    assert len(subnets) == 1
    subnet = subnets[0]
    assert subnet.subnet_id == ec2_resources["subnet_id"]
    assert subnet.vpc_id == ec2_resources["vpc_id"]
    assert subnet.cidr_block == "10.42.1.0/24"
    assert subnet.tags == {"Name": "test-subnet"}
    assert subnet.available_ip_address_count >= 0


def test_list_subnets_empty_for_nonexistent_vpc_filter(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    subnets = list_subnets(client_factory, region="us-east-1", vpc_id="vpc-doesnotexist")
    assert subnets == []


def test_list_route_tables_normalizes_routes_and_associations(
    client_factory: ClientFactory, ec2_resources: dict[str, str]
) -> None:
    route_tables = list_route_tables(
        client_factory, region="us-east-1", vpc_id=ec2_resources["vpc_id"]
    )
    match = next(rt for rt in route_tables if rt.route_table_id == ec2_resources["route_table_id"])

    igw_routes = [r for r in match.routes if r.target == ec2_resources["igw_id"]]
    assert len(igw_routes) == 1
    assert igw_routes[0].destination_cidr_block == "0.0.0.0/0"
    assert igw_routes[0].target_type == "gateway"
    assert igw_routes[0].is_propagated is False
    assert match.vpc_id == ec2_resources["vpc_id"]
    assert match.account_id == "123456789012"
    assert match.observed_at


def test_normalize_route_preserves_blackhole_state() -> None:
    """moto does not simulate AWS transitioning a route to State=blackhole
    when its target is deleted, so this exercises the normalizer directly
    against a synthetic raw route shaped like AWS's real blackhole output."""
    route = _normalize_route(
        {
            "DestinationCidrBlock": "10.1.0.0/16",
            "VpcPeeringConnectionId": "pcx-0123456789abcdef0",
            "Origin": "CreateRoute",
            "State": "blackhole",
        }
    )
    assert route.state == "blackhole"
    assert route.target == "pcx-0123456789abcdef0"
    assert route.target_type == "vpc_peering_connection"
    assert route.is_propagated is False


def test_normalize_route_marks_propagated_routes() -> None:
    route = _normalize_route(
        {
            "DestinationCidrBlock": "192.168.0.0/16",
            "GatewayId": "vgw-0123456789abcdef0",
            "Origin": "EnableVgwRoutePropagation",
            "State": "active",
        }
    )
    assert route.is_propagated is True
    assert route.origin == "EnableVgwRoutePropagation"


def test_normalize_route_prefix_list_destination() -> None:
    route = _normalize_route(
        {
            "DestinationPrefixListId": "pl-0123456789abcdef0",
            "NatGatewayId": "nat-0123456789abcdef0",
            "Origin": "CreateRoute",
            "State": "active",
        }
    )
    assert route.destination_prefix_list_id == "pl-0123456789abcdef0"
    assert route.destination_cidr_block is None
    assert route.target == "nat-0123456789abcdef0"
    assert route.target_type == "nat_gateway"
