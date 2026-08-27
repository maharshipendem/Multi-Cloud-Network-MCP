"""MCP tool: azure_list_virtual_network_peerings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.peerings import list_virtual_network_peerings
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_list_virtual_network_peerings"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List VNet peerings for one virtual network, including peering state "
            "(Initiated/Connected/Disconnected), remote address space, and gateway "
            "transit settings."
        ),
        meta=capability_meta(resource_types=["virtual_network_peering"]),
    )
    def azure_list_virtual_network_peerings(
        resource_group: str,
        virtual_network_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """List VNet peerings.

        Args:
            resource_group: Resource group containing the virtual network.
            virtual_network_name: Name of the virtual network to list peerings for.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_network_peerings(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_name=virtual_network_name,
            ),
        )
