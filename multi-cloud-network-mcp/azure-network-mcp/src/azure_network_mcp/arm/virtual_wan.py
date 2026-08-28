"""ARM service layer: Virtual WAN, Virtual Hub, hub route tables/routes,
hub VNet connections, hub BGP connections (also used for standalone Azure
Route Server -- see ``arm/route_server.py``), and routing-intent route
maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly_lro
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.hybrid_connectivity import (
    BgpHubConnection,
    HubRoute,
    HubRouteTable,
    HubVirtualNetworkConnection,
    PeerRoute,
    RouteMap,
    RouteMapRuleSummary,
    VirtualHub,
    VirtualWan,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_virtual_wans(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VirtualWan]:
    """Call VirtualWansOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.virtual_wans,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.virtual_wans, "list", max_items=settings.max_page_results)

    result = []
    for wan in raw:
        parsed = parse_resource_id(wan.id)
        result.append(
            VirtualWan(
                resource_id=wan.id,
                name=wan.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=wan.location,
                provisioning_state=getattr(wan, "provisioning_state", None),
                tags=normalize_tags(wan.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualWans",
                disable_vpn_encryption=getattr(wan, "disable_vpn_encryption", None),
                allow_branch_to_branch_traffic=getattr(wan, "allow_branch_to_branch_traffic", None),
                office365_local_breakout_category=getattr(
                    wan, "office365_local_breakout_category", None
                ),
                virtual_hub_ids=[h.id for h in (wan.virtual_hubs or []) if getattr(h, "id", None)],
                vpn_site_ids=[s.id for s in (wan.vpn_sites or []) if getattr(s, "id", None)],
            )
        )
    return result


def list_virtual_hubs(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VirtualHub]:
    """Call VirtualHubsOperations.list (whole subscription) or
    .list_by_resource_group (one resource group).

    ``is_route_server`` is derived client-side: Azure represents a
    standalone Route Server as a Virtual Hub with ``sku == "Standard"``
    and no ``virtual_wan`` reference.
    """
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.virtual_hubs,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.virtual_hubs, "list", max_items=settings.max_page_results)

    result = []
    for hub in raw:
        parsed = parse_resource_id(hub.id)
        virtual_wan_id = hub.virtual_wan.id if getattr(hub, "virtual_wan", None) else None
        sku = getattr(hub, "sku", None)
        result.append(
            VirtualHub(
                resource_id=hub.id,
                name=hub.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=hub.location,
                provisioning_state=getattr(hub, "provisioning_state", None),
                tags=normalize_tags(hub.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualHubs",
                virtual_wan_id=virtual_wan_id,
                address_prefix=getattr(hub, "address_prefix", None),
                sku=sku,
                routing_state=getattr(hub, "routing_state", None),
                virtual_router_asn=getattr(hub, "virtual_router_asn", None),
                virtual_router_ips=list(getattr(hub, "virtual_router_ips", None) or []),
                allow_branch_to_branch_traffic=getattr(hub, "allow_branch_to_branch_traffic", None),
                hub_routing_preference=getattr(hub, "hub_routing_preference", None),
                is_route_server=(sku == "Standard" and virtual_wan_id is None),
            )
        )
    return result


def list_hub_route_tables(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_hub_name: str,
) -> list[HubRouteTable]:
    """Call HubRouteTablesOperations.list for one Virtual Hub."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.hub_route_tables,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_hub_name=virtual_hub_name,
    )
    result = []
    for rt in raw:
        parsed = parse_resource_id(rt.id)
        result.append(
            HubRouteTable(
                resource_id=rt.id,
                name=rt.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(rt, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualHubs/hubRouteTables",
                virtual_hub_name=virtual_hub_name,
                routes=[
                    HubRoute(
                        name=r.name,
                        destination_type=getattr(r, "destination_type", None),
                        destinations=list(getattr(r, "destinations", None) or []),
                        next_hop_type=getattr(r, "next_hop_type", None),
                        next_hop=getattr(r, "next_hop", None),
                    )
                    for r in (rt.routes or [])
                ],
                labels=list(getattr(rt, "labels", None) or []),
                associated_connection_ids=list(getattr(rt, "associated_connections", None) or []),
                propagating_connection_ids=list(getattr(rt, "propagating_connections", None) or []),
            )
        )
    return result


def list_hub_virtual_network_connections(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_hub_name: str,
) -> list[HubVirtualNetworkConnection]:
    """Call HubVirtualNetworkConnectionsOperations.list for one Virtual Hub."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.hub_virtual_network_connections,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_hub_name=virtual_hub_name,
    )
    result = []
    for conn in raw:
        parsed = parse_resource_id(conn.id)
        routing = getattr(conn, "routing_configuration", None)
        result.append(
            HubVirtualNetworkConnection(
                resource_id=conn.id,
                name=conn.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(conn, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualHubs/hubVirtualNetworkConnections",
                virtual_hub_name=virtual_hub_name,
                remote_virtual_network_id=(
                    conn.remote_virtual_network.id
                    if getattr(conn, "remote_virtual_network", None)
                    else None
                ),
                allow_hub_to_remote_vnet_transit=getattr(
                    conn, "allow_hub_to_remote_vnet_transit", None
                ),
                allow_remote_vnet_to_use_hub_vnet_gateways=getattr(
                    conn, "allow_remote_vnet_to_use_hub_vnet_gateways", None
                ),
                enable_internet_security=getattr(conn, "enable_internet_security", None),
                associated_route_table_id=(
                    routing.associated_route_table.id
                    if routing and getattr(routing, "associated_route_table", None)
                    else None
                ),
                propagated_route_table_ids=(
                    list(routing.propagated_route_tables.ids or [])
                    if routing
                    and getattr(routing, "propagated_route_tables", None)
                    and getattr(routing.propagated_route_tables, "ids", None)
                    else []
                ),
            )
        )
    return result


def list_virtual_hub_bgp_connections(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_hub_name: str,
) -> list[BgpHubConnection]:
    """Call VirtualHubBgpConnectionsOperations.list -- the BGP peers of a
    Virtual Hub (also used for a standalone Route Server's peers; see
    arm/route_server.py)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_hub_bgp_connections,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_hub_name=virtual_hub_name,
    )
    result = []
    for conn in raw:
        parsed = parse_resource_id(conn.id)
        result.append(
            BgpHubConnection(
                resource_id=conn.id,
                name=conn.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(conn, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualHubs/bgpConnections",
                virtual_hub_name=virtual_hub_name,
                peer_asn=getattr(conn, "peer_asn", None),
                peer_ip=getattr(conn, "peer_ip", None),
                connection_state=getattr(conn, "connection_state", None),
            )
        )
    return result


def get_hub_bgp_connection_routes(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_hub_name: str,
    connection_name: str,
    direction: str,
) -> list[PeerRoute]:
    """Call VirtualHubBgpConnectionsOperations.begin_list_advertised_routes
    or .begin_list_learned_routes -- the routes one hub BGP connection has
    advertised to, or learned from, its peer. Read-only despite the
    ``begin_`` prefix; see security/guardrails.py's module docstring.
    ``direction`` is ``"advertised"`` or ``"learned"``.
    """
    client = client_factory.get_network_client(subscription_id)
    method_name = (
        "begin_list_advertised_routes" if direction == "advertised" else "begin_list_learned_routes"
    )
    result: dict[str, Any] = call_readonly_lro(
        client.virtual_hub_bgp_connections,
        method_name,
        resource_group_name=resource_group,
        hub_name=virtual_hub_name,
        connection_name=connection_name,
    )
    routes: list[PeerRoute] = []
    for peer_routes in (result or {}).values():
        for r in peer_routes:
            routes.append(
                PeerRoute(
                    network=getattr(r, "network", None),
                    next_hop=getattr(r, "next_hop", None),
                    source_peer=getattr(r, "source_peer", None),
                    origin=getattr(r, "origin", None),
                    as_path=getattr(r, "as_path", None),
                    weight=getattr(r, "weight", None),
                )
            )
    return routes


def list_route_maps(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_hub_name: str,
) -> list[RouteMap]:
    """Call RouteMapsOperations.list -- a Virtual Hub's routing-intent policies."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.route_maps,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_hub_name=virtual_hub_name,
    )
    result = []
    for rm in raw:
        parsed = parse_resource_id(rm.id)
        result.append(
            RouteMap(
                resource_id=rm.id,
                name=rm.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(rm, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualHubs/routeMaps",
                virtual_hub_name=virtual_hub_name,
                associated_inbound_connection_ids=list(
                    getattr(rm, "associated_inbound_connections", None) or []
                ),
                associated_outbound_connection_ids=list(
                    getattr(rm, "associated_outbound_connections", None) or []
                ),
                rules=[
                    RouteMapRuleSummary(
                        name=r.name, next_step_if_matched=getattr(r, "next_step_if_matched", None)
                    )
                    for r in (rm.rules or [])
                ],
            )
        )
    return result


__all__ = [
    "get_hub_bgp_connection_routes",
    "list_hub_route_tables",
    "list_hub_virtual_network_connections",
    "list_route_maps",
    "list_virtual_hub_bgp_connections",
    "list_virtual_hubs",
    "list_virtual_wans",
]
