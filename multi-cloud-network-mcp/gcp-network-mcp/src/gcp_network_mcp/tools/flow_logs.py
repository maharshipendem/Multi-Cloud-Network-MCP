"""MCP tool: gcp_list_vpc_flow_logs_configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.flow_logs import list_vpc_flow_logs_configs
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_vpc_flow_logs_configs"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List VPC Flow Logs configuration (project-level) -- configuration only, never "
            "log records/content."
        ),
        meta=capability_meta(resource_types=["vpc_flow_logs_config"]),
    )
    def gcp_list_vpc_flow_logs_configs(project_id: str | None = None) -> dict[str, Any]:
        """List VPC Flow Logs configs.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_vpc_flow_logs_configs(client_factory, project_id=resolved),
        )
