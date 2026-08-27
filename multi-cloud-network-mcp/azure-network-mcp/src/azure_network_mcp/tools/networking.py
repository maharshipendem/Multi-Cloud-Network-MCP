"""MCP tools: azure_list_virtual_networks, azure_list_subnets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.networking import list_subnets, list_virtual_networks
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_VNETS = "azure_list_virtual_networks"
_LIST_SUBNETS = "azure_list_subnets"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VNETS,
        description=(
            "List virtual networks in a subscription (whole subscription, or one "
            "resource group), including address space, DNS servers, and peering "
            "summaries."
        ),
        meta=capability_meta(resource_types=["virtual_network"]),
    )
    def azure_list_virtual_networks(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List virtual networks.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VNETS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_networks(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_SUBNETS,
        description=(
            "List subnets in one virtual network, including address prefixes, "
            "NSG/route-table/NAT-gateway associations, service endpoints, and "
            "delegations."
        ),
        meta=capability_meta(resource_types=["subnet"]),
    )
    def azure_list_subnets(
        resource_group: str,
        virtual_network_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """List subnets.

        Args:
            resource_group: Resource group containing the virtual network.
            virtual_network_name: Name of the virtual network to list subnets for.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_SUBNETS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_subnets(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_name=virtual_network_name,
            ),
        )
