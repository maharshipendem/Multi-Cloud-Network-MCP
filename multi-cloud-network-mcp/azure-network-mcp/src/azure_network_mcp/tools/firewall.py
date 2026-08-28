"""MCP tools: Azure Firewall inventory and firewall policy rule collection
group summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.firewall import (
    list_azure_firewalls,
    list_firewall_policies,
    list_firewall_policy_rule_collection_groups,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_FIREWALLS = "azure_list_azure_firewalls"
_LIST_POLICIES = "azure_list_firewall_policies"
_LIST_RULE_COLLECTION_GROUPS = "azure_list_firewall_policy_rule_collection_groups"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_FIREWALLS,
        description=(
            "List Azure Firewalls (whole subscription, or one resource group), "
            "including SKU, threat intel mode, and hub/policy association."
        ),
        meta=capability_meta(resource_types=["azure_firewall"]),
    )
    def azure_list_azure_firewalls(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Azure Firewalls.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_FIREWALLS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_azure_firewalls(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_POLICIES,
        description=(
            "List firewall policies (whole subscription, or one resource "
            "group), including base/child policy and rule collection group "
            "references."
        ),
        meta=capability_meta(resource_types=["firewall_policy"]),
    )
    def azure_list_firewall_policies(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List firewall policies.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_POLICIES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_firewall_policies(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_RULE_COLLECTION_GROUPS,
        description=(
            "List one firewall policy's rule collection groups. Individual "
            "rules are summarized to a count per collection, not enumerated, "
            "per this server's response-size limits."
        ),
        meta=capability_meta(resource_types=["firewall_policy"]),
    )
    def azure_list_firewall_policy_rule_collection_groups(
        resource_group: str, firewall_policy_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List firewall policy rule collection groups.

        Args:
            resource_group: Resource group containing the policy.
            firewall_policy_name: Name of the firewall policy.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RULE_COLLECTION_GROUPS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_firewall_policy_rule_collection_groups(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                firewall_policy_name=firewall_policy_name,
            ),
        )
