"""ARM service layer: Azure Route Server.

Azure has no dedicated "Route Server" ARM resource type or operation
group -- a standalone Route Server is a ``Microsoft.Network/virtualHubs``
resource with ``sku == "Standard"`` and no ``virtual_wan`` reference (the
same resource type a vWAN hub uses). This module is a thin, filtered view
over ``arm/virtual_wan.py``'s own collectors rather than a new ARM
surface, so a Route Server's peers/routes reuse the exact same guardrail
exceptions already justified there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.virtual_wan import (
    get_hub_bgp_connection_routes,
    list_virtual_hub_bgp_connections,
    list_virtual_hubs,
)
from azure_network_mcp.models.hybrid_connectivity import BgpHubConnection, PeerRoute, VirtualHub

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_route_servers(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VirtualHub]:
    """List standalone Route Servers (Virtual Hubs with sku="Standard" and
    no vWAN association) in a subscription or resource group."""
    hubs = list_virtual_hubs(
        client_factory, subscription_id=subscription_id, resource_group=resource_group
    )
    return [h for h in hubs if h.is_route_server]


def list_route_server_peers(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    route_server_name: str,
) -> list[BgpHubConnection]:
    """List a Route Server's BGP peers (its hub BGP connections)."""
    return list_virtual_hub_bgp_connections(
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
        virtual_hub_name=route_server_name,
    )


def get_route_server_peer_routes(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    route_server_name: str,
    peer_connection_name: str,
    direction: str,
) -> list[PeerRoute]:
    """Get the routes advertised to, or learned from, one Route Server
    peer. ``direction`` is ``"advertised"`` or ``"learned"``."""
    return get_hub_bgp_connection_routes(
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
        virtual_hub_name=route_server_name,
        connection_name=peer_connection_name,
        direction=direction,
    )


__all__ = ["get_route_server_peer_routes", "list_route_server_peers", "list_route_servers"]
