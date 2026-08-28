"""MCP tools: gcp_list_forwarding_rules, gcp_list_target_proxies,
gcp_list_backend_services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.load_balancing import (
    list_backend_services,
    list_forwarding_rules,
    list_target_proxies,
)
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_FORWARDING_RULES = "gcp_list_forwarding_rules"
_LIST_TARGET_PROXIES = "gcp_list_target_proxies"
_LIST_BACKEND_SERVICES = "gcp_list_backend_services"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_FORWARDING_RULES,
        description=(
            "List forwarding rules (regional and global) in a project, "
            "including IP address/protocol, load balancing scheme, and the "
            "target proxy or backend service each one forwards to."
        ),
        meta=capability_meta(resource_types=["forwarding_rule"]),
    )
    def gcp_list_forwarding_rules(project_id: str | None = None) -> dict[str, Any]:
        """List forwarding rules.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_FORWARDING_RULES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_forwarding_rules(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_TARGET_PROXIES,
        description="List target HTTP(S) proxies in a project, including their URL map.",
        meta=capability_meta(resource_types=["target_proxy"]),
    )
    def gcp_list_target_proxies(project_id: str | None = None) -> dict[str, Any]:
        """List target HTTP(S) proxies.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_TARGET_PROXIES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_target_proxies(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_BACKEND_SERVICES,
        description=(
            "List backend services (regional and global) in a project, "
            "including their backend groups and, for each backend group, a "
            "health summary from GCP's own get_health computation."
        ),
        meta=capability_meta(resource_types=["backend_service"]),
    )
    def gcp_list_backend_services(
        project_id: str | None = None, include_health: bool = True
    ) -> dict[str, Any]:
        """List backend services.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
            include_health: Fetch a health summary for each backend group.
                Defaults to true; set false to skip the extra API calls.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_BACKEND_SERVICES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_backend_services(
                client_factory, project_id=resolved, include_health=include_health
            ),
        )
