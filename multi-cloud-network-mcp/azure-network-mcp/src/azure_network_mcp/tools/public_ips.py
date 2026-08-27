"""MCP tool: azure_list_public_ip_addresses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.public_ips import list_public_ip_addresses
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_list_public_ip_addresses"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List public IP addresses (whole subscription, or one resource group), "
            "including the resource each one is associated with, if any."
        ),
        meta=capability_meta(resource_types=["public_ip_address"]),
    )
    def azure_list_public_ip_addresses(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List public IP addresses.

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
            func=lambda resolved: list_public_ip_addresses(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )
