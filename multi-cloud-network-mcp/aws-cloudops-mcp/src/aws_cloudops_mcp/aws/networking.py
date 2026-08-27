"""AWS service layer: VPC networking inventory (VPCs, subnets, route tables).

Kept as one module (not split per-resource) because these three EC2
resources are read together in the same DescribeVpcs/DescribeSubnets/
DescribeRouteTables family and share the same normalization helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.filters import ids_filter, vpc_filter
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.common import (
    CollectionWarning,
    Route,
    RouteTable,
    RouteTableAssociation,
    Subnet,
    SubnetIpv6CidrBlockAssociation,
    Vpc,
    VpcCidrBlockAssociation,
    VpcIpv6CidrBlockAssociation,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# Maps a Route's AWS target field to a normalized (target, target_type) pair.
# GatewayId is deliberately excluded here: AWS reuses that one field for
# three different resource types (an internet gateway, a virtual private
# gateway, or the literal string "local"), so it needs prefix-based
# disambiguation instead of a fixed field->type mapping -- see
# _classify_gateway_id below.
_ROUTE_TARGET_FIELDS: tuple[tuple[str, str], ...] = (
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


def _classify_gateway_id(gateway_id: str) -> str:
    """AWS's ``GatewayId`` route field is reused for four different things:
    an internet gateway ID (``igw-...``), a virtual private gateway ID
    (``vgw-...``), a Gateway-type VPC endpoint ID (``vpce-...`` -- AWS
    represents an S3/DynamoDB Gateway endpoint route as a ``GatewayId``
    pointing at the endpoint, paired with a ``DestinationPrefixListId``,
    not a distinct route field), or the literal string ``"local"``."""
    if gateway_id == "local":
        return "local"
    if gateway_id.startswith("vgw-"):
        return "virtual_private_gateway"
    if gateway_id.startswith("vpce-"):
        return "vpc_endpoint"
    return "gateway"


def _normalize_route(raw: dict[str, Any]) -> Route:
    target: str | None = None
    target_type: str | None = None
    gateway_id = raw.get("GatewayId")
    if gateway_id:
        target, target_type = gateway_id, _classify_gateway_id(gateway_id)
    else:
        for field, ttype in _ROUTE_TARGET_FIELDS:
            if raw.get(field):
                target, target_type = raw[field], ttype
                break
    return Route(
        destination_cidr_block=raw.get("DestinationCidrBlock"),
        destination_ipv6_cidr_block=raw.get("DestinationIpv6CidrBlock"),
        destination_prefix_list_id=raw.get("DestinationPrefixListId"),
        target=target,
        target_type=target_type,
        state=raw.get("State"),
        origin=raw.get("Origin"),
        is_propagated=raw.get("Origin") == "EnableVgwRoutePropagation",
    )


def _normalize_association(raw: dict[str, Any]) -> RouteTableAssociation:
    return RouteTableAssociation(
        route_table_association_id=raw.get("RouteTableAssociationId"),
        subnet_id=raw.get("SubnetId"),
        gateway_id=raw.get("GatewayId"),
        main=raw.get("Main", False),
        association_state=(raw.get("AssociationState") or {}).get("State"),
    )


def _fetch_dns_attributes(
    client: Any, vpc_id: str
) -> tuple[bool | None, bool | None, CollectionWarning | None]:
    """Best-effort fetch of a VPC's two DNS attributes (2 extra API calls).

    Returns ``(enable_dns_support, enable_dns_hostnames, warning)`` -- on any
    failure (most commonly missing ``ec2:DescribeVpcAttribute`` permission)
    both values are ``None`` and a warning is returned instead of raising,
    so one VPC's enrichment failure never fails the whole tool call.
    """
    try:
        support = call_readonly(
            client, "describe_vpc_attribute", VpcId=vpc_id, Attribute="enableDnsSupport"
        )
        hostnames = call_readonly(
            client, "describe_vpc_attribute", VpcId=vpc_id, Attribute="enableDnsHostnames"
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return (
            None,
            None,
            CollectionWarning(
                resource_type="vpc_dns_attributes",
                code="ENRICHMENT_FAILED",
                message=f"Could not fetch DNS attributes for {vpc_id}: {code}.",
            ),
        )
    return (
        support.get("EnableDnsSupport", {}).get("Value"),
        hostnames.get("EnableDnsHostnames", {}).get("Value"),
        None,
    )


def list_vpcs(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_ids: list[str] | None = None,
    include_dns_attributes: bool = False,
) -> CollectionResult:
    """Call ec2:DescribeVpcs and return the normalized VPC list for ``region``.

    ``include_dns_attributes`` opts into fetching ``enable_dns_support``/
    ``enable_dns_hostnames`` per VPC (2 extra ``DescribeVpcAttribute`` calls
    each, since AWS does not include them in DescribeVpcs) up to
    ``Settings.max_fanout_calls`` VPCs; VPCs beyond that cap, or any VPC
    whose enrichment call fails, are recorded as a ``CollectionWarning``
    rather than silently omitted or left ambiguous.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw_vpcs = paginate(
        client,
        "describe_vpcs",
        "Vpcs",
        max_items=settings.max_page_results,
        **ids_filter("vpc-id", vpc_ids),
    )

    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    vpcs: list[Vpc] = []
    for v in raw_vpcs:
        vpc_id = v["VpcId"]
        enable_dns_support: bool | None = None
        enable_dns_hostnames: bool | None = None
        if include_dns_attributes:
            if fanout_budget > 0:
                enable_dns_support, enable_dns_hostnames, warning = _fetch_dns_attributes(
                    client, vpc_id
                )
                fanout_budget -= 1
                if warning:
                    warnings.append(warning)
            else:
                warnings.append(
                    CollectionWarning(
                        resource_type="vpc_dns_attributes",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"Skipped DNS attribute enrichment for {vpc_id}: "
                            f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                        ),
                    )
                )

        vpcs.append(
            Vpc(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                vpc_id=vpc_id,
                cidr_block=v.get("CidrBlock", ""),
                cidr_block_associations=[
                    VpcCidrBlockAssociation(
                        association_id=a.get("AssociationId"),
                        cidr_block=a["CidrBlock"],
                        state=(a.get("CidrBlockState") or {}).get("State"),
                    )
                    for a in v.get("CidrBlockAssociationSet", [])
                ],
                ipv6_cidr_block_associations=[
                    VpcIpv6CidrBlockAssociation(
                        association_id=a.get("AssociationId"),
                        ipv6_cidr_block=a["Ipv6CidrBlock"],
                        state=(a.get("Ipv6CidrBlockState") or {}).get("State"),
                        ipv6_pool=a.get("Ipv6Pool"),
                        network_border_group=a.get("NetworkBorderGroup"),
                    )
                    for a in v.get("Ipv6CidrBlockAssociationSet", [])
                ],
                state=v.get("State", ""),
                is_default=v.get("IsDefault", False),
                instance_tenancy=v.get("InstanceTenancy"),
                dhcp_options_id=v.get("DhcpOptionsId"),
                enable_dns_support=enable_dns_support,
                enable_dns_hostnames=enable_dns_hostnames,
                tags=normalize_tags(v.get("Tags")),
            )
        )

    return CollectionResult(data=vpcs, warnings=warnings)


def list_subnets(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    subnet_ids: list[str] | None = None,
) -> list[Subnet]:
    """Call ec2:DescribeSubnets and return the normalized subnet list for ``region``."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = vpc_filter(vpc_id) or ids_filter("subnet-id", subnet_ids)
    raw_subnets = paginate(
        client, "describe_subnets", "Subnets", max_items=settings.max_page_results, **filters
    )
    return [
        Subnet(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            subnet_id=s["SubnetId"],
            vpc_id=s["VpcId"],
            cidr_block=s.get("CidrBlock", ""),
            ipv6_cidr_block_associations=[
                SubnetIpv6CidrBlockAssociation(
                    association_id=a.get("AssociationId"),
                    ipv6_cidr_block=a["Ipv6CidrBlock"],
                    state=(a.get("Ipv6CidrBlockState") or {}).get("State"),
                )
                for a in s.get("Ipv6CidrBlockAssociationSet", [])
            ],
            availability_zone=s.get("AvailabilityZone", ""),
            availability_zone_id=s.get("AvailabilityZoneId"),
            available_ip_address_count=s.get("AvailableIpAddressCount", 0),
            map_public_ip_on_launch=s.get("MapPublicIpOnLaunch", False),
            assign_ipv6_address_on_creation=s.get("AssignIpv6AddressOnCreation"),
            default_for_az=s.get("DefaultForAz"),
            state=s.get("State"),
            tags=normalize_tags(s.get("Tags")),
        )
        for s in raw_subnets
    ]


def list_route_tables(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    route_table_ids: list[str] | None = None,
) -> list[RouteTable]:
    """Call ec2:DescribeRouteTables and return the normalized route table list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = vpc_filter(vpc_id) or ids_filter("route-table-id", route_table_ids)
    raw_route_tables = paginate(
        client,
        "describe_route_tables",
        "RouteTables",
        max_items=settings.max_page_results,
        **filters,
    )
    return [
        RouteTable(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            route_table_id=rt["RouteTableId"],
            vpc_id=rt.get("VpcId", ""),
            routes=[_normalize_route(r) for r in rt.get("Routes", [])],
            associations=[_normalize_association(a) for a in rt.get("Associations", [])],
            propagating_vgws=[
                g["GatewayId"] for g in rt.get("PropagatingVgws", []) if g.get("GatewayId")
            ],
            tags=normalize_tags(rt.get("Tags")),
        )
        for rt in raw_route_tables
    ]
