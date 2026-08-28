"""MCP tools: gcp_list_firewall_rules, gcp_list_hierarchical_firewall_policies,
gcp_list_network_firewall_policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.firewall import (
    list_firewall_rules,
    list_hierarchical_firewall_policies,
    list_network_firewall_policies,
)
from gcp_network_mcp.gcp.networking import list_networks
from gcp_network_mcp.models.firewall import implied_firewall_rules
from gcp_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_RULES = "gcp_list_firewall_rules"
_LIST_HIERARCHICAL_POLICIES = "gcp_list_hierarchical_firewall_policies"
_LIST_NETWORK_POLICIES = "gcp_list_network_firewall_policies"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_RULES,
        description=(
            "List network-level firewall rules in a project, including "
            "allow/deny protocol+port entries, direction, priority, and "
            "source/target tags or service accounts. Also returns GCP's two "
            "unlisted implied default rules (allow-all egress, deny-all "
            "ingress, priority 65535) for every network in the project -- "
            "these never appear in the raw GCP API response but apply to "
            "every VPC network."
        ),
        meta=capability_meta(resource_types=["firewall_rule"]),
    )
    def gcp_list_firewall_rules(
        project_id: str | None = None, include_implied: bool = True
    ) -> dict[str, Any]:
        """List firewall rules.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
            include_implied: Include GCP's two unlisted implied default
                rules for every network in the project. Defaults to true.
        """

        def _run(resolved: str) -> Any:
            rules = list_firewall_rules(client_factory, project_id=resolved)
            if include_implied:
                for network in list_networks(client_factory, project_id=resolved):
                    if network.self_link:
                        rules.extend(
                            implied_firewall_rules(
                                network_self_link=network.self_link, network_name=network.name
                            )
                        )
            return rules

        return execute_tool_with_resolved_project(
            tool_name=_LIST_RULES,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )

    @mcp.tool(
        name=_LIST_HIERARCHICAL_POLICIES,
        description=(
            "List hierarchical Firewall Policies attached under one "
            "organization or folder, including rules and their "
            "attachment-target associations. Org/folder-scoped, not "
            "project-scoped -- pass an organization or folder ID, not a "
            "project ID."
        ),
        meta=capability_meta(resource_types=["firewall_policy"]),
    )
    def gcp_list_hierarchical_firewall_policies(parent_id: str) -> dict[str, Any]:
        """List hierarchical firewall policies.

        Args:
            parent_id: Organization or folder ID (numeric) to list
                firewall policies under.
        """
        return execute_tool(
            tool_name=_LIST_HIERARCHICAL_POLICIES,
            project_id=None,
            func=lambda: list_hierarchical_firewall_policies(client_factory, parent_id=parent_id),
        )

    @mcp.tool(
        name=_LIST_NETWORK_POLICIES,
        description=(
            "List network-scoped Firewall Policies in a project, including "
            "rules and their VPC network attachment associations."
        ),
        meta=capability_meta(resource_types=["firewall_policy"]),
    )
    def gcp_list_network_firewall_policies(project_id: str | None = None) -> dict[str, Any]:
        """List network-scoped firewall policies.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_NETWORK_POLICIES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_network_firewall_policies(
                client_factory, project_id=resolved
            ),
        )
