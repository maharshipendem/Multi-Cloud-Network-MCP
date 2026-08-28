"""MCP tool: gcp_list_permitted_projects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.projects import list_permitted_projects
from gcp_network_mcp.tools._shared import execute_tool
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_permitted_projects"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List the GCP projects this server is permitted to operate against: "
            "the configured GCP_PROJECT_ALLOWLIST if set, otherwise every "
            "project the authenticated identity's IAM bindings expose."
        ),
        meta=capability_meta(resource_types=["project"]),
    )
    def gcp_list_permitted_projects() -> dict[str, Any]:
        return execute_tool(
            tool_name=TOOL_NAME,
            project_id=None,
            func=lambda: list_permitted_projects(client_factory),
        )
