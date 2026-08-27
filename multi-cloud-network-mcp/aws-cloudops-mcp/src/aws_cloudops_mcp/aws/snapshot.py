"""AWS service layer: assembles a ``diagnostics.snapshot.NetworkSnapshot``
by calling the existing Milestone 1-3 service-layer functions.

This is the *only* module that bridges boto3 (``aws_cloudops_mcp.aws.*``)
and the diagnostics engine (``aws_cloudops_mcp.diagnostics.*``) -- the
diagnostics package itself never imports boto3 or this module. Every
resource type is fetched with the same normalization/pagination/guardrail
path every other tool in this codebase already uses; this module adds no
new AWS API calls of its own, it only orchestrates existing ones and
shapes their output into one bundle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.endpoints import list_vpc_endpoints
from aws_cloudops_mcp.aws.enis import list_network_interfaces
from aws_cloudops_mcp.aws.gateways import (
    list_egress_only_internet_gateways,
    list_internet_gateways,
)
from aws_cloudops_mcp.aws.loadbalancers import list_load_balancers
from aws_cloudops_mcp.aws.nacls import list_network_acls
from aws_cloudops_mcp.aws.nat import list_nat_gateways
from aws_cloudops_mcp.aws.networking import list_route_tables, list_subnets, list_vpcs
from aws_cloudops_mcp.aws.peering import list_vpc_peering_connections
from aws_cloudops_mcp.aws.prefix_lists import list_managed_prefix_lists
from aws_cloudops_mcp.aws.security import list_security_groups
from aws_cloudops_mcp.aws.transit_gateway import (
    list_transit_gateway_attachments,
    list_transit_gateway_route_tables,
    list_transit_gateways,
    search_transit_gateway_routes,
)
from aws_cloudops_mcp.aws.vpn import list_customer_gateways, list_vpn_connections
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import CollectionWarning

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_T = TypeVar("_T")


def collect_network_snapshot(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_ids: list[str] | None = None,
    include_transit_gateway: bool = False,
    include_vpn: bool = False,
) -> NetworkSnapshot:
    """Assemble a :class:`NetworkSnapshot` for ``region``.

    Every VPC-scoped resource type is fetched region-wide in a single
    call sequence (not once per VPC) and, when ``vpc_ids`` is given,
    filtered down client-side -- this keeps the AWS call count constant
    regardless of how many VPCs are in scope, rather than growing
    linearly with ``len(vpc_ids)``. Transit Gateway and VPN resources are
    opt-in (``include_transit_gateway``/``include_vpn``): they are
    account-wide, not VPC-scoped, and a caller doing pure intra-VPC
    diagnostics (e.g. "why can't this ENI reach that ENI in the same
    VPC") does not need them collected.
    """
    account_id = client_factory.get_account_id()
    warnings: list[CollectionWarning] = []

    def _filtered(items: list[_T], vpc_id_getter: Callable[[_T], str | None]) -> list[_T]:
        if vpc_ids is None:
            return items
        return [item for item in items if vpc_id_getter(item) in vpc_ids]

    vpc_result = list_vpcs(client_factory, region=region)
    warnings.extend(vpc_result.warnings)
    vpcs = _filtered(vpc_result.data, lambda v: v.vpc_id)

    subnets = _filtered(list_subnets(client_factory, region=region), lambda s: s.vpc_id)
    route_tables = _filtered(list_route_tables(client_factory, region=region), lambda r: r.vpc_id)
    security_groups = _filtered(
        list_security_groups(client_factory, region=region), lambda s: s.vpc_id
    )
    network_acls = _filtered(list_network_acls(client_factory, region=region), lambda n: n.vpc_id)
    network_interfaces = _filtered(
        list_network_interfaces(client_factory, region=region), lambda e: e.vpc_id
    )
    internet_gateways = list_internet_gateways(client_factory, region=region)
    if vpc_ids is not None:
        internet_gateways = [
            igw for igw in internet_gateways if any(a.vpc_id in vpc_ids for a in igw.attachments)
        ]
    egress_only_internet_gateways = list_egress_only_internet_gateways(
        client_factory, region=region
    )
    if vpc_ids is not None:
        egress_only_internet_gateways = [
            eigw
            for eigw in egress_only_internet_gateways
            if any(a.vpc_id in vpc_ids for a in eigw.attachments)
        ]
    nat_gateways = _filtered(list_nat_gateways(client_factory, region=region), lambda n: n.vpc_id)
    vpc_peering_connections = list_vpc_peering_connections(client_factory, region=region)
    if vpc_ids is not None:
        vpc_peering_connections = [
            p
            for p in vpc_peering_connections
            if p.requester.vpc_id in vpc_ids or p.accepter.vpc_id in vpc_ids
        ]
    vpc_endpoints = _filtered(list_vpc_endpoints(client_factory, region=region), lambda e: e.vpc_id)
    lb_result = list_load_balancers(client_factory, region=region)
    warnings.extend(lb_result.warnings)
    load_balancers = _filtered(lb_result.data, lambda lb: lb.vpc_id)

    referenced_prefix_list_ids = {
        route.destination_prefix_list_id
        for rt in route_tables
        for route in rt.routes
        if route.destination_prefix_list_id
    }
    managed_prefix_lists: list = []
    if referenced_prefix_list_ids:
        pl_result = list_managed_prefix_lists(
            client_factory,
            region=region,
            include_entries=True,
            prefix_list_ids=sorted(referenced_prefix_list_ids),
        )
        warnings.extend(pl_result.warnings)
        managed_prefix_lists = pl_result.data

    transit_gateways: list = []
    transit_gateway_attachments: list = []
    transit_gateway_route_tables: list = []
    transit_gateway_routes: list = []
    if include_transit_gateway:
        transit_gateways = list_transit_gateways(client_factory, region=region)
        transit_gateway_attachments = list_transit_gateway_attachments(
            client_factory, region=region
        )
        tgw_rt_result = list_transit_gateway_route_tables(
            client_factory, region=region, include_associations=True, include_propagations=True
        )
        warnings.extend(tgw_rt_result.warnings)
        transit_gateway_route_tables = tgw_rt_result.data
        for rt in transit_gateway_route_tables:
            routes = search_transit_gateway_routes(
                client_factory,
                region=region,
                transit_gateway_route_table_id=rt.transit_gateway_route_table_id,
            )
            transit_gateway_routes.extend(routes)

    vpn_connections: list = []
    customer_gateways: list = []
    if include_vpn:
        vpn_connections = list_vpn_connections(client_factory, region=region)
        customer_gateways = list_customer_gateways(client_factory, region=region)

    return NetworkSnapshot(
        region=region,
        account_id=account_id,
        collected_at=now_iso(),
        vpcs=vpcs,
        subnets=subnets,
        route_tables=route_tables,
        security_groups=security_groups,
        network_acls=network_acls,
        network_interfaces=network_interfaces,
        internet_gateways=internet_gateways,
        egress_only_internet_gateways=egress_only_internet_gateways,
        nat_gateways=nat_gateways,
        vpc_peering_connections=vpc_peering_connections,
        vpc_endpoints=vpc_endpoints,
        managed_prefix_lists=managed_prefix_lists,
        load_balancers=load_balancers,
        transit_gateways=transit_gateways,
        transit_gateway_attachments=transit_gateway_attachments,
        transit_gateway_route_tables=transit_gateway_route_tables,
        transit_gateway_routes=transit_gateway_routes,
        vpn_connections=vpn_connections,
        customer_gateways=customer_gateways,
        warnings=warnings,
    )


__all__ = ["collect_network_snapshot"]
