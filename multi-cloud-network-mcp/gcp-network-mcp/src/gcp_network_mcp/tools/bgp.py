"""MCP tool: gcp_get_router_bgp_status."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.bgp import get_router_status
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_get_router_bgp_status"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Return the read-only computed BGP status for one Cloud Router: per-peer "
            "session state, learned-route counts, and the router's own best-route "
            "selections. Distinct from the router's static BGP peer configuration "
            "(see gcp_list_routers)."
        ),
        meta=capability_meta(resource_types=["router", "bgp"]),
    )
    def gcp_get_router_bgp_status(
        region: str, router_name: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Get a router's BGP status.

        Args:
            region: Region the router is in.
            router_name: Name of the router.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_router_status(
                client_factory, project_id=resolved, region=region, router_name=router_name
            ),
        )
