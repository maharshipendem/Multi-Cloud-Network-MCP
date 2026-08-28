"""MCP tool: gcp_list_instance_network_interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.instances import list_instances
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_instance_network_interfaces"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List Compute Engine instances' connectivity metadata across every "
            "zone in a project: network interfaces, internal/external "
            "addresses, alias IP ranges, tags, and service accounts. Does not "
            "return full instance inventory (disks, machine config)."
        ),
        meta=capability_meta(resource_types=["instance"]),
    )
    def gcp_list_instance_network_interfaces(project_id: str | None = None) -> dict[str, Any]:
        """List instance network interfaces.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_instances(client_factory, project_id=resolved),
        )
