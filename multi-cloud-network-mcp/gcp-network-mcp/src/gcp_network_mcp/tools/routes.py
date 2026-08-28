"""MCP tool: gcp_list_routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.routes import list_routes
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_routes"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List VPC routes in a project, with each route's next-hop type "
            "(instance, IP address, internet gateway, VPN tunnel, interconnect "
            "attachment, ILB, peering, or network connectivity hub) resolved "
            "from whichever next-hop field GCP populated."
        ),
        meta=capability_meta(resource_types=["route"]),
    )
    def gcp_list_routes(project_id: str | None = None) -> dict[str, Any]:
        """List VPC routes.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_routes(client_factory, project_id=resolved),
        )
