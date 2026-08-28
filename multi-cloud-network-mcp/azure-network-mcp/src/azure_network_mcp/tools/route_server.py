"""MCP tools: Azure Route Server (a standalone Virtual Hub) and its BGP peers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.route_server import (
    get_route_server_peer_routes,
    list_route_server_peers,
    list_route_servers,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_ROUTE_SERVERS = "azure_list_route_servers"
_LIST_ROUTE_SERVER_PEERS = "azure_list_route_server_peers"
_GET_ROUTE_SERVER_PEER_ROUTES = "azure_get_route_server_peer_routes"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_ROUTE_SERVERS,
        description=(
            "List standalone Azure Route Servers (Virtual Hubs with sku='Standard' "
            "and no Virtual WAN association) in a subscription or resource group."
        ),
        meta=capability_meta(resource_types=["route_server"]),
    )
    def azure_list_route_servers(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Route Servers.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ROUTE_SERVERS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_route_servers(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_ROUTE_SERVER_PEERS,
        description="List a Route Server's BGP peers.",
        meta=capability_meta(resource_types=["route_server"]),
    )
    def azure_list_route_server_peers(
        resource_group: str, route_server_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Route Server peers.

        Args:
            resource_group: Resource group containing the Route Server.
            route_server_name: Name of the Route Server (Virtual Hub).
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ROUTE_SERVER_PEERS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_route_server_peers(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                route_server_name=route_server_name,
            ),
        )

    @mcp.tool(
        name=_GET_ROUTE_SERVER_PEER_ROUTES,
        description=(
            "Get the routes one Route Server peer has advertised to, or learned "
            "from, the Route Server. A read-only computation despite the SDK's "
            "'begin_' method prefix."
        ),
        meta=capability_meta(resource_types=["route_server"]),
    )
    def azure_get_route_server_peer_routes(
        resource_group: str,
        route_server_name: str,
        peer_connection_name: str,
        direction: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one Route Server peer's advertised or learned routes.

        Args:
            resource_group: Resource group containing the Route Server.
            route_server_name: Name of the Route Server (Virtual Hub).
            peer_connection_name: Name of the peer's BGP connection.
            direction: "advertised" or "learned".
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_ROUTE_SERVER_PEER_ROUTES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_route_server_peer_routes(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                route_server_name=route_server_name,
                peer_connection_name=peer_connection_name,
                direction=direction,
            ),
        )
