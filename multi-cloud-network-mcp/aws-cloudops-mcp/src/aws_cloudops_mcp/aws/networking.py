"""AWS service layer: VPC networking inventory (VPCs, subnets, route tables).

Kept as one module (not split per-resource) because these three EC2
resources are read together in the same DescribeVpcs/DescribeSubnets/
DescribeRouteTables family and share the same normalization helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.config import get_settings
from aws_cloudops_mcp.models.common import (
    Route,
    RouteTable,
    RouteTableAssociation,
    Subnet,
    Vpc,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# Maps a Route's AWS target field to a normalized (target, target_type) pair.
_ROUTE_TARGET_FIELDS: tuple[tuple[str, str], ...] = (
    ("GatewayId", "gateway"),
    ("NatGatewayId", "nat_gateway"),
    ("TransitGatewayId", "transit_gateway"),
    ("VpcPeeringConnectionId", "vpc_peering_connection"),
    ("NetworkInterfaceId", "network_interface"),
    ("EgressOnlyInternetGatewayId", "egress_only_internet_gateway"),
    ("InstanceId", "instance"),
    ("LocalGatewayId", "local_gateway"),
    ("CarrierGatewayId", "carrier_gateway"),
    ("CoreNetworkArn", "core_network"),
)


def _vpc_filter(vpc_id: str | None) -> dict[str, Any]:
    if not vpc_id:
        return {}
    return {"Filters": [{"Name": "vpc-id", "Values": [vpc_id]}]}


def _normalize_route(raw: dict[str, Any]) -> Route:
    target: str | None = None
    target_type: str | None = None
    for field, ttype in _ROUTE_TARGET_FIELDS:
        if raw.get(field):
            target, target_type = raw[field], ttype
            break
    return Route(
        destination_cidr_block=raw.get("DestinationCidrBlock"),
        destination_prefix_list_id=raw.get("DestinationPrefixListId"),
        target=target,
        target_type=target_type,
        state=raw.get("State"),
        origin=raw.get("Origin"),
    )


def _normalize_association(raw: dict[str, Any]) -> RouteTableAssociation:
    return RouteTableAssociation(
        route_table_association_id=raw.get("RouteTableAssociationId"),
        subnet_id=raw.get("SubnetId"),
        gateway_id=raw.get("GatewayId"),
        main=raw.get("Main", False),
    )


def list_vpcs(client_factory: ClientFactory, *, region: str) -> list[Vpc]:
    """Call ec2:DescribeVpcs and return the normalized VPC list for ``region``."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    max_items = get_settings().max_page_results

    raw_vpcs = paginate(client, "describe_vpcs", "Vpcs", max_items=max_items)
    return [
        Vpc(
            vpc_id=v["VpcId"],
            cidr_block=v.get("CidrBlock", ""),
            state=v.get("State", ""),
            is_default=v.get("IsDefault", False),
            dhcp_options_id=v.get("DhcpOptionsId"),
            tags=normalize_tags(v.get("Tags")),
            region=region,
        )
        for v in raw_vpcs
    ]


def list_subnets(
    client_factory: ClientFactory, *, region: str, vpc_id: str | None = None
) -> list[Subnet]:
    """Call ec2:DescribeSubnets and return the normalized subnet list for ``region``."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    max_items = get_settings().max_page_results

    raw_subnets = paginate(
        client, "describe_subnets", "Subnets", max_items=max_items, **_vpc_filter(vpc_id)
    )
    return [
        Subnet(
            subnet_id=s["SubnetId"],
            vpc_id=s["VpcId"],
            cidr_block=s.get("CidrBlock", ""),
            availability_zone=s.get("AvailabilityZone", ""),
            available_ip_address_count=s.get("AvailableIpAddressCount", 0),
            map_public_ip_on_launch=s.get("MapPublicIpOnLaunch", False),
            tags=normalize_tags(s.get("Tags")),
            region=region,
        )
        for s in raw_subnets
    ]


def list_route_tables(
    client_factory: ClientFactory, *, region: str, vpc_id: str | None = None
) -> list[RouteTable]:
    """Call ec2:DescribeRouteTables and return the normalized route table list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    max_items = get_settings().max_page_results

    raw_route_tables = paginate(
        client, "describe_route_tables", "RouteTables", max_items=max_items, **_vpc_filter(vpc_id)
    )
    return [
        RouteTable(
            route_table_id=rt["RouteTableId"],
            vpc_id=rt.get("VpcId", ""),
            routes=[_normalize_route(r) for r in rt.get("Routes", [])],
            associations=[_normalize_association(a) for a in rt.get("Associations", [])],
            tags=normalize_tags(rt.get("Tags")),
            region=region,
        )
        for rt in raw_route_tables
    ]
