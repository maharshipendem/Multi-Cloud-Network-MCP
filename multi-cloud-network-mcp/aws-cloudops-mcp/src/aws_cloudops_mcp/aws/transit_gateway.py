"""AWS service layer: Transit Gateways, attachments, route tables, and routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.transit_gateway import (
    TransitGateway,
    TransitGatewayAttachment,
    TransitGatewayAttachmentAssociation,
    TransitGatewayOptions,
    TransitGatewayRoute,
    TransitGatewayRouteAttachment,
    TransitGatewayRouteTable,
    TransitGatewayRouteTableAssociation,
    TransitGatewayRouteTablePropagation,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

DEFAULT_ROUTE_SEARCH_MAX_RESULTS = 100


def list_transit_gateways(
    client_factory: ClientFactory,
    *,
    region: str,
    transit_gateway_ids: list[str] | None = None,
) -> list[TransitGateway]:
    """Call ec2:DescribeTransitGateways and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"TransitGatewayIds": transit_gateway_ids} if transit_gateway_ids else {}
    raw = paginate(
        client,
        "describe_transit_gateways",
        "TransitGateways",
        max_items=settings.max_page_results,
        **kwargs,
    )
    result = []
    for tgw in raw:
        opts = tgw.get("Options", {})
        result.append(
            TransitGateway(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="ec2:DescribeTransitGateways",
                transit_gateway_id=tgw["TransitGatewayId"],
                transit_gateway_arn=tgw.get("TransitGatewayArn"),
                owner_id=tgw.get("OwnerId"),
                description=tgw.get("Description"),
                state=tgw.get("State", ""),
                options=TransitGatewayOptions(
                    amazon_side_asn=opts.get("AmazonSideAsn"),
                    auto_accept_shared_attachments=opts.get("AutoAcceptSharedAttachments"),
                    default_route_table_association=opts.get("DefaultRouteTableAssociation"),
                    default_route_table_propagation=opts.get("DefaultRouteTablePropagation"),
                    dns_support=opts.get("DnsSupport"),
                    vpn_ecmp_support=opts.get("VpnEcmpSupport"),
                    multicast_support=opts.get("MulticastSupport"),
                    cidr_blocks=opts.get("TransitGatewayCidrBlocks", []),
                ),
                tags=normalize_tags(tgw.get("Tags")),
            )
        )
    return result


def list_transit_gateway_attachments(
    client_factory: ClientFactory,
    *,
    region: str,
    transit_gateway_id: str | None = None,
    resource_type: str | None = None,
) -> list[TransitGatewayAttachment]:
    """Call ec2:DescribeTransitGatewayAttachments and return the normalized list.

    Covers all attachment resource types AWS reports (``vpc``, ``vpn``,
    ``direct-connect-gateway``, ``peering``, ``connect``, ``tgw-peering``),
    including attachments owned by another account (visible when this
    account owns the Transit Gateway side) -- ``resource_owner_id`` on
    each record differing from the caller's own account ID signals a
    cross-account attachment.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = []
    if transit_gateway_id:
        filters.append({"Name": "transit-gateway-id", "Values": [transit_gateway_id]})
    if resource_type:
        filters.append({"Name": "resource-type", "Values": [resource_type]})
    kwargs: dict[str, Any] = {"Filters": filters} if filters else {}

    raw = paginate(
        client,
        "describe_transit_gateway_attachments",
        "TransitGatewayAttachments",
        max_items=settings.max_page_results,
        **kwargs,
    )
    result = []
    for att in raw:
        assoc_raw = att.get("Association")
        result.append(
            TransitGatewayAttachment(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="ec2:DescribeTransitGatewayAttachments",
                transit_gateway_attachment_id=att["TransitGatewayAttachmentId"],
                transit_gateway_id=att.get("TransitGatewayId", ""),
                transit_gateway_owner_id=att.get("TransitGatewayOwnerId"),
                resource_owner_id=att.get("ResourceOwnerId"),
                resource_type=att.get("ResourceType", ""),
                resource_id=att.get("ResourceId"),
                state=att.get("State", ""),
                association=(
                    TransitGatewayAttachmentAssociation(
                        transit_gateway_route_table_id=assoc_raw.get("TransitGatewayRouteTableId"),
                        state=assoc_raw.get("State"),
                    )
                    if assoc_raw
                    else None
                ),
                tags=normalize_tags(att.get("Tags")),
            )
        )
    return result


def list_transit_gateway_route_tables(
    client_factory: ClientFactory,
    *,
    region: str,
    transit_gateway_id: str | None = None,
    transit_gateway_route_table_ids: list[str] | None = None,
    include_associations: bool = False,
    include_propagations: bool = False,
) -> CollectionResult:
    """Call ec2:DescribeTransitGatewayRouteTables and return the normalized list.

    ``include_associations``/``include_propagations`` each opt into one
    extra API call per route table (bounded by ``Settings.max_fanout_calls``,
    shared across both), the same inline-enrichment pattern Milestone 2
    used for VPC route tables.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if transit_gateway_id:
        kwargs["Filters"] = [{"Name": "transit-gateway-id", "Values": [transit_gateway_id]}]
    elif transit_gateway_route_table_ids:
        kwargs["TransitGatewayRouteTableIds"] = transit_gateway_route_table_ids

    raw = paginate(
        client,
        "describe_transit_gateway_route_tables",
        "TransitGatewayRouteTables",
        max_items=settings.max_page_results,
        **kwargs,
    )

    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    route_tables = []
    for rt in raw:
        rt_id = rt["TransitGatewayRouteTableId"]
        associations: list[TransitGatewayRouteTableAssociation] | None = None
        propagations: list[TransitGatewayRouteTablePropagation] | None = None

        if include_associations:
            if fanout_budget > 0:
                associations = list_transit_gateway_route_table_associations(
                    client_factory, region=region, transit_gateway_route_table_id=rt_id
                )
                fanout_budget -= 1
            else:
                warnings.append(_fanout_cap_warning("associations", rt_id, settings))

        if include_propagations:
            if fanout_budget > 0:
                propagations = list_transit_gateway_route_table_propagations(
                    client_factory, region=region, transit_gateway_route_table_id=rt_id
                )
                fanout_budget -= 1
            else:
                warnings.append(_fanout_cap_warning("propagations", rt_id, settings))

        route_tables.append(
            TransitGatewayRouteTable(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="ec2:DescribeTransitGatewayRouteTables",
                transit_gateway_route_table_id=rt_id,
                transit_gateway_id=rt.get("TransitGatewayId", ""),
                state=rt.get("State", ""),
                default_association_route_table=rt.get("DefaultAssociationRouteTable", False),
                default_propagation_route_table=rt.get("DefaultPropagationRouteTable", False),
                associations=associations,
                propagations=propagations,
                tags=normalize_tags(rt.get("Tags")),
            )
        )

    return CollectionResult(data=route_tables, warnings=warnings)


def _fanout_cap_warning(kind: str, route_table_id: str, settings: Any) -> CollectionWarning:
    return CollectionWarning(
        resource_type=f"transit_gateway_route_table_{kind}",
        code="FANOUT_CAP_REACHED",
        message=(
            f"Skipped {kind} enrichment for {route_table_id}: "
            f"max_fanout_calls ({settings.max_fanout_calls}) reached."
        ),
    )


def list_transit_gateway_route_table_associations(
    client_factory: ClientFactory, *, region: str, transit_gateway_route_table_id: str
) -> list[TransitGatewayRouteTableAssociation]:
    """Call ec2:GetTransitGatewayRouteTableAssociations for one route table."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings

    raw = paginate(
        client,
        "get_transit_gateway_route_table_associations",
        "Associations",
        max_items=settings.max_page_results,
        TransitGatewayRouteTableId=transit_gateway_route_table_id,
    )
    return [
        TransitGatewayRouteTableAssociation(
            transit_gateway_attachment_id=a.get("TransitGatewayAttachmentId"),
            resource_id=a.get("ResourceId"),
            resource_type=a.get("ResourceType"),
            state=a.get("State"),
        )
        for a in raw
    ]


def list_transit_gateway_route_table_propagations(
    client_factory: ClientFactory, *, region: str, transit_gateway_route_table_id: str
) -> list[TransitGatewayRouteTablePropagation]:
    """Call ec2:GetTransitGatewayRouteTablePropagations for one route table."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings

    raw = paginate(
        client,
        "get_transit_gateway_route_table_propagations",
        "TransitGatewayRouteTablePropagations",
        max_items=settings.max_page_results,
        TransitGatewayRouteTableId=transit_gateway_route_table_id,
    )
    return [
        TransitGatewayRouteTablePropagation(
            transit_gateway_attachment_id=p.get("TransitGatewayAttachmentId"),
            resource_id=p.get("ResourceId"),
            resource_type=p.get("ResourceType"),
            state=p.get("State"),
        )
        for p in raw
    ]


def search_transit_gateway_routes(
    client_factory: ClientFactory,
    *,
    region: str,
    transit_gateway_route_table_id: str,
    destination_cidr_block: str | None = None,
    route_search_type: str | None = None,
    max_results: int = DEFAULT_ROUTE_SEARCH_MAX_RESULTS,
) -> list[TransitGatewayRoute]:
    """Call ec2:SearchTransitGatewayRoutes with a bounded result cap.

    AWS requires at least one filter; if the caller gives neither
    ``destination_cidr_block`` nor ``route_search_type``, this defaults to
    ``type in (static, propagated)`` (i.e. every real route, excluding
    only the AWS-internal ``blackhole``-only edge case that requires no
    filter match). AWS itself constrains ``MaxResults`` to the range
    [5, 1000]; this clamps into that range rather than passing an
    out-of-range value through to a confusing AWS-side validation error --
    this is the milestone's "bound route-search fan-out" requirement.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    # AWS's own MaxResults floor (5) is a wire-protocol constraint, not the
    # tool's contract with its caller -- request at least that many from
    # AWS, but still honor whatever (possibly smaller) cap the caller asked
    # for when slicing the final result below.
    caller_max_results = max(0, min(max_results, 1000))
    api_max_results = max(5, caller_max_results)

    filters = []
    if destination_cidr_block:
        filters.append({"Name": "route-search.exact-match", "Values": [destination_cidr_block]})
    if route_search_type:
        filters.append({"Name": "type", "Values": [route_search_type]})
    if not filters:
        filters.append({"Name": "type", "Values": ["static", "propagated"]})

    response = call_readonly(
        client,
        "search_transit_gateway_routes",
        TransitGatewayRouteTableId=transit_gateway_route_table_id,
        Filters=filters,
        MaxResults=api_max_results,
    )
    routes = []
    for r in response.get("Routes", [])[:caller_max_results]:
        routes.append(
            TransitGatewayRoute(
                destination_cidr_block=r.get("DestinationCidrBlock"),
                route_type=r.get("Type"),
                state=r.get("State"),
                attachments=[
                    TransitGatewayRouteAttachment(
                        transit_gateway_attachment_id=a.get("TransitGatewayAttachmentId"),
                        resource_id=a.get("ResourceId"),
                        resource_type=a.get("ResourceType"),
                    )
                    for a in r.get("TransitGatewayAttachments", [])
                ],
            )
        )
    return routes
