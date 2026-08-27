"""MCP tools: azure_list_route_tables, azure_get_effective_route_table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.route_tables import get_effective_route_table, list_route_tables
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_ROUTE_TABLES = "azure_list_route_tables"
_GET_EFFECTIVE_ROUTE_TABLE = "azure_get_effective_route_table"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_ROUTE_TABLES,
        description=(
            "List route tables (whole subscription, or one resource group), "
            "including their configured routes and subnet associations."
        ),
        meta=capability_meta(resource_types=["route_table"]),
    )
    def azure_list_route_tables(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List route tables.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ROUTE_TABLES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_route_tables(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_GET_EFFECTIVE_ROUTE_TABLE,
        description=(
            "Get the effective route table Azure actually applies to a network "
            "interface -- merged from system routes, user-defined routes, and "
            "BGP-propagated routes. A read-only computation despite the SDK's "
            "'begin_' method prefix."
        ),
        meta=capability_meta(resource_types=["route_table", "network_interface"]),
    )
    def azure_get_effective_route_table(
        resource_group: str,
        network_interface_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a NIC's effective route table.

        Args:
            resource_group: Resource group containing the network interface.
            network_interface_name: Name of the network interface.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_EFFECTIVE_ROUTE_TABLE,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_effective_route_table(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_interface_name=network_interface_name,
            ),
        )
