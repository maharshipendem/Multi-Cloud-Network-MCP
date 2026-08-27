"""ARM service layer: route tables, routes, and effective route tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly_lro
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import EffectiveRoute, Route, RouteTable

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _normalize_route(route: Any) -> Route:
    return Route(
        name=route.name,
        address_prefix=getattr(route, "address_prefix", None),
        next_hop_type=getattr(route, "next_hop_type", None),
        next_hop_ip_address=getattr(route, "next_hop_ip_address", None),
        provisioning_state=getattr(route, "provisioning_state", None),
    )


def list_route_tables(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[RouteTable]:
    """Call RouteTablesOperations.list_all (whole subscription) or .list
    (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.route_tables,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.route_tables, "list_all", max_items=settings.max_page_results)

    result = []
    for rt in raw:
        parsed = parse_resource_id(rt.id)
        result.append(
            RouteTable(
                resource_id=rt.id,
                name=rt.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=rt.location,
                provisioning_state=getattr(rt, "provisioning_state", None),
                tags=normalize_tags(rt.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/routeTables",
                routes=[_normalize_route(r) for r in (rt.routes or [])],
                subnet_ids=[s.id for s in (rt.subnets or []) if s.id],
                disable_bgp_route_propagation=getattr(rt, "disable_bgp_route_propagation", None),
            )
        )
    return result


def get_effective_route_table(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_interface_name: str,
) -> list[EffectiveRoute]:
    """Call NetworkInterfacesOperations.begin_get_effective_route_table --
    the route Azure actually applies to a NIC, merged from system
    routes, UDRs, and BGP-propagated routes. Read-only despite the
    ``begin_`` prefix; see security/guardrails.py's module docstring for
    why this specific operation is explicitly allowlisted.
    """
    client = client_factory.get_network_client(subscription_id)
    result = call_readonly_lro(
        client.network_interfaces,
        "begin_get_effective_route_table",
        resource_group_name=resource_group,
        network_interface_name=network_interface_name,
    )
    return [
        EffectiveRoute(
            name=r.name,
            address_prefixes=list(r.address_prefix or []),
            next_hop_type=getattr(r, "next_hop_type", None),
            next_hop_ip_addresses=list(getattr(r, "next_hop_ip_address", None) or []),
            source=getattr(r, "source", None),
            state=getattr(r, "state", None),
        )
        for r in (result.value or [])
    ]


__all__ = ["get_effective_route_table", "list_route_tables"]
