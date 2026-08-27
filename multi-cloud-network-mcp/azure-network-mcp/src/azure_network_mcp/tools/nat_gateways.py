"""MCP tool: azure_list_nat_gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.nat_gateways import list_nat_gateways
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_list_nat_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List NAT gateways (whole subscription, or one resource group), "
            "including attached public IPs and subnets."
        ),
        meta=capability_meta(resource_types=["nat_gateway"]),
    )
    def azure_list_nat_gateways(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List NAT gateways.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_nat_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )
