"""MCP tool: gcp_get_vpc_topology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.topology import get_vpc_topology
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_get_vpc_topology"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Return a deterministic, typed node/edge graph of one project's VPC "
            "networking -- networks, subnetworks, instance network interfaces, "
            "Cloud Routers/NAT, and VPC peerings -- joined from every other "
            "tool this server exposes. Every edge carries the specific "
            "observed field value it was derived from. A reference this "
            "server couldn't resolve (a different project, a permission gap) "
            "still produces an edge, plus a warning, rather than being "
            "silently dropped; when any such warning is present, the result's "
            "completeness is reported as 'partial', never silently 'complete'."
        ),
        meta=capability_meta(resource_types=["topology"]),
    )
    def gcp_get_vpc_topology(project_id: str | None = None) -> dict[str, Any]:
        """Get the VPC topology graph for one project.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_vpc_topology(client_factory, project_id=resolved),
        )
