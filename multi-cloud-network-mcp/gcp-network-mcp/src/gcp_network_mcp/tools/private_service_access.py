"""MCP tool: gcp_list_private_service_access_ranges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.private_service_access import list_private_service_access_ranges
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_private_service_access_ranges"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List private services access allocated IP ranges (GlobalAddresses with "
            "purpose=VPC_PEERING) in a project. The Service Networking connection linking "
            "a range to a service producer's network is not covered -- no available "
            "Google-published Python client library exposes it (see docs/limitations.md)."
        ),
        meta=capability_meta(resource_types=["private_service_access_range"]),
    )
    def gcp_list_private_service_access_ranges(project_id: str | None = None) -> dict[str, Any]:
        """List private services access ranges.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_private_service_access_ranges(
                client_factory, project_id=resolved
            ),
        )
