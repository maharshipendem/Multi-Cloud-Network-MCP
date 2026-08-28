"""MCP tool: gcp_list_packet_mirroring_policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.packet_mirroring import list_packet_mirroring_policies
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_packet_mirroring_policies"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List Packet Mirroring policy configuration across every region in a project -- "
            "configuration only, never mirrored packet content."
        ),
        meta=capability_meta(resource_types=["packet_mirroring_policy"]),
    )
    def gcp_list_packet_mirroring_policies(project_id: str | None = None) -> dict[str, Any]:
        """List Packet Mirroring policies.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_packet_mirroring_policies(
                client_factory, project_id=resolved
            ),
        )
