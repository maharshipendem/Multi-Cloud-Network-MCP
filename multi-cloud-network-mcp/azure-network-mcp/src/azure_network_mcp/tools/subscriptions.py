"""MCP tools: azure_list_subscriptions, azure_list_tenants, azure_list_locations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.subscriptions import list_locations, list_subscriptions, list_tenants
from azure_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_SUBSCRIPTIONS = "azure_list_subscriptions"
_LIST_TENANTS = "azure_list_tenants"
_LIST_LOCATIONS = "azure_list_locations"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_SUBSCRIPTIONS,
        description=(
            "List subscriptions visible to the configured identity, filtered to the "
            "configured subscription allowlist (if any)."
        ),
        meta=capability_meta(resource_types=["subscription"]),
    )
    def azure_list_subscriptions() -> dict[str, Any]:
        return execute_tool(
            tool_name=_LIST_SUBSCRIPTIONS,
            subscription_id=None,
            func=lambda: list_subscriptions(client_factory),
        )

    @mcp.tool(
        name=_LIST_TENANTS,
        description=(
            "List tenants visible to the configured identity, filtered to the "
            "configured tenant allowlist (if any)."
        ),
        meta=capability_meta(resource_types=["tenant"]),
    )
    def azure_list_tenants() -> dict[str, Any]:
        return execute_tool(
            tool_name=_LIST_TENANTS,
            subscription_id=None,
            func=lambda: list_tenants(client_factory),
        )

    @mcp.tool(
        name=_LIST_LOCATIONS,
        description="List Azure regions (locations) available to a subscription.",
        meta=capability_meta(resource_types=["location"]),
    )
    def azure_list_locations(subscription_id: str | None = None) -> dict[str, Any]:
        """List locations.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_LOCATIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            func=lambda resolved: list_locations(client_factory, subscription_id=resolved),
        )
