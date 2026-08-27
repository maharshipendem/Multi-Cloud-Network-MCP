"""MCP tools: azure_list_network_security_groups, azure_list_security_rules,
azure_get_effective_network_security_groups."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.network_security_groups import (
    get_effective_network_security_groups,
    list_network_security_groups,
    list_security_rules,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_NSGS = "azure_list_network_security_groups"
_LIST_SECURITY_RULES = "azure_list_security_rules"
_GET_EFFECTIVE_NSGS = "azure_get_effective_network_security_groups"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_NSGS,
        description=(
            "List network security groups (whole subscription, or one resource "
            "group), including custom security rules and Azure's built-in default "
            "rules as separate fields."
        ),
        meta=capability_meta(resource_types=["network_security_group"]),
    )
    def azure_list_network_security_groups(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List network security groups.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_NSGS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_network_security_groups(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_SECURITY_RULES,
        description="List the custom security rules configured on one network security group.",
        meta=capability_meta(resource_types=["network_security_group"]),
    )
    def azure_list_security_rules(
        resource_group: str,
        network_security_group_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """List security rules.

        Args:
            resource_group: Resource group containing the network security group.
            network_security_group_name: Name of the network security group.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_SECURITY_RULES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_security_rules(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_security_group_name=network_security_group_name,
            ),
        )

    @mcp.tool(
        name=_GET_EFFECTIVE_NSGS,
        description=(
            "Get the network security groups and rules Azure actually applies to a "
            "network interface, across subnet- and NIC-level associations, with "
            "Application Security Group references expanded into concrete IP "
            "prefixes. A read-only computation despite the SDK's 'begin_' method "
            "prefix."
        ),
        meta=capability_meta(resource_types=["network_security_group", "network_interface"]),
    )
    def azure_get_effective_network_security_groups(
        resource_group: str,
        network_interface_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a NIC's effective network security groups.

        Args:
            resource_group: Resource group containing the network interface.
            network_interface_name: Name of the network interface.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_EFFECTIVE_NSGS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_effective_network_security_groups(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_interface_name=network_interface_name,
            ),
        )
