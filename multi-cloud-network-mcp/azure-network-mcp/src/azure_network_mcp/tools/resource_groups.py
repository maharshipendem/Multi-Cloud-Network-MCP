"""MCP tool: azure_list_resource_groups."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.resource_groups import list_resource_groups
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_list_resource_groups"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List resource groups in a subscription, with optional name substring "
            "filter and an optional network-focused filter that keeps only groups "
            "containing at least one Microsoft.Network resource (bounded fan-out, "
            "capped by max_fanout_calls)."
        ),
        meta=capability_meta(resource_types=["resource_group"]),
    )
    def azure_list_resource_groups(
        subscription_id: str | None = None,
        name_contains: str | None = None,
        only_with_network_resources: bool = False,
    ) -> dict[str, Any]:
        """List resource groups.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            name_contains: Optional case-insensitive substring filter on
                the resource group name.
            only_with_network_resources: If true, keep only resource
                groups containing at least one Microsoft.Network
                resource (one extra API call per group, bounded by
                max_fanout_calls -- see warnings in the response
                metadata if the cap is reached).
        """
        return execute_tool_with_resolved_subscription(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            func=lambda resolved: list_resource_groups(
                client_factory,
                subscription_id=resolved,
                name_contains=name_contains,
                only_with_network_resources=only_with_network_resources,
            ),
        )
