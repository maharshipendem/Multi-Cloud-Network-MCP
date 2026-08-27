"""MCP tool: azure_get_vnet_topology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.topology import get_vnet_topology
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_get_vnet_topology"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Build a deterministic topology graph for one virtual network: typed "
            "nodes (VNet, subnets, NSGs, route tables, NAT gateways, NICs, public "
            "IPs, peerings) and typed edges with evidence, scoped to the VNet's own "
            "resource group. References to resources outside that resource group "
            "produce an edge plus a completeness warning rather than a silent gap. "
            "Node and edge ordering is stable across calls."
        ),
        meta=capability_meta(resource_types=["virtual_network", "topology"]),
    )
    def azure_get_vnet_topology(
        resource_group: str,
        virtual_network_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a VNet's topology graph.

        Args:
            resource_group: Resource group containing the virtual network.
            virtual_network_name: Name of the virtual network to map.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_vnet_topology(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_name=virtual_network_name,
            ),
        )
