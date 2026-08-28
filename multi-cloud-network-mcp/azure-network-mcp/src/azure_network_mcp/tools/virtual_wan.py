"""MCP tools: Virtual WAN, Virtual Hub, hub route tables/routes, hub VNet
connections, hub BGP connections/routes, and routing-intent route maps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.virtual_wan import (
    get_hub_bgp_connection_routes,
    list_hub_route_tables,
    list_hub_virtual_network_connections,
    list_route_maps,
    list_virtual_hub_bgp_connections,
    list_virtual_hubs,
    list_virtual_wans,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_WANS = "azure_list_virtual_wans"
_LIST_HUBS = "azure_list_virtual_hubs"
_LIST_HUB_ROUTE_TABLES = "azure_list_hub_route_tables"
_LIST_HUB_VNET_CONNECTIONS = "azure_list_hub_virtual_network_connections"
_LIST_HUB_BGP_CONNECTIONS = "azure_list_virtual_hub_bgp_connections"
_GET_HUB_BGP_CONNECTION_ROUTES = "azure_get_hub_bgp_connection_routes"
_LIST_ROUTE_MAPS = "azure_list_route_maps"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_WANS,
        description=(
            "List Virtual WANs (whole subscription, or one resource group), including "
            "member virtual hubs and VPN sites."
        ),
        meta=capability_meta(resource_types=["virtual_wan"]),
    )
    def azure_list_virtual_wans(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Virtual WANs.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_WANS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_wans(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_HUBS,
        description=(
            "List Virtual Hubs (whole subscription, or one resource group), including "
            "routing state and router ASN/IPs. A hub with sku='Standard' and no "
            "Virtual WAN association is a standalone Azure Route Server -- see "
            "azure_list_route_servers for a filtered view."
        ),
        meta=capability_meta(resource_types=["virtual_hub"]),
    )
    def azure_list_virtual_hubs(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Virtual Hubs.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_HUBS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_hubs(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_HUB_ROUTE_TABLES,
        description="List a Virtual Hub's route tables and their routes.",
        meta=capability_meta(resource_types=["virtual_hub", "route_table"]),
    )
    def azure_list_hub_route_tables(
        resource_group: str, virtual_hub_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List hub route tables.

        Args:
            resource_group: Resource group containing the Virtual Hub.
            virtual_hub_name: Name of the Virtual Hub.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_HUB_ROUTE_TABLES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_hub_route_tables(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_hub_name=virtual_hub_name,
            ),
        )

    @mcp.tool(
        name=_LIST_HUB_VNET_CONNECTIONS,
        description="List a Virtual Hub's VNet connections.",
        meta=capability_meta(resource_types=["virtual_hub", "virtual_network"]),
    )
    def azure_list_hub_virtual_network_connections(
        resource_group: str, virtual_hub_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List hub VNet connections.

        Args:
            resource_group: Resource group containing the Virtual Hub.
            virtual_hub_name: Name of the Virtual Hub.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_HUB_VNET_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_hub_virtual_network_connections(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_hub_name=virtual_hub_name,
            ),
        )

    @mcp.tool(
        name=_LIST_HUB_BGP_CONNECTIONS,
        description=(
            "List a Virtual Hub's BGP connections (peers) -- also used for a "
            "standalone Azure Route Server's peers."
        ),
        meta=capability_meta(resource_types=["virtual_hub"]),
    )
    def azure_list_virtual_hub_bgp_connections(
        resource_group: str, virtual_hub_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List hub BGP connections.

        Args:
            resource_group: Resource group containing the Virtual Hub.
            virtual_hub_name: Name of the Virtual Hub.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_HUB_BGP_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_hub_bgp_connections(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_hub_name=virtual_hub_name,
            ),
        )

    @mcp.tool(
        name=_GET_HUB_BGP_CONNECTION_ROUTES,
        description=(
            "Get the routes one Virtual Hub BGP connection has advertised to, or "
            "learned from, its peer. A read-only computation despite the SDK's "
            "'begin_' method prefix."
        ),
        meta=capability_meta(resource_types=["virtual_hub"]),
    )
    def azure_get_hub_bgp_connection_routes(
        resource_group: str,
        virtual_hub_name: str,
        connection_name: str,
        direction: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one hub BGP connection's advertised or learned routes.

        Args:
            resource_group: Resource group containing the Virtual Hub.
            virtual_hub_name: Name of the Virtual Hub.
            connection_name: Name of the BGP connection.
            direction: "advertised" or "learned".
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_HUB_BGP_CONNECTION_ROUTES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_hub_bgp_connection_routes(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_hub_name=virtual_hub_name,
                connection_name=connection_name,
                direction=direction,
            ),
        )

    @mcp.tool(
        name=_LIST_ROUTE_MAPS,
        description="List a Virtual Hub's routing-intent route maps.",
        meta=capability_meta(resource_types=["virtual_hub"]),
    )
    def azure_list_route_maps(
        resource_group: str, virtual_hub_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List route maps.

        Args:
            resource_group: Resource group containing the Virtual Hub.
            virtual_hub_name: Name of the Virtual Hub.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ROUTE_MAPS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_route_maps(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_hub_name=virtual_hub_name,
            ),
        )
