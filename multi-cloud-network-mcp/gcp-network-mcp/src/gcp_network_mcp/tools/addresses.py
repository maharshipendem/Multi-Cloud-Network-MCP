"""MCP tool: gcp_list_addresses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.addresses import list_global_addresses, list_regional_addresses
from gcp_network_mcp.gcp.collection import CollectionResult
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

TOOL_NAME = "gcp_list_addresses"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List reserved IP addresses in a project -- both regional "
            "(every region) and global -- including address type, status, "
            "purpose, and the network/subnetwork/resources using each one."
        ),
        meta=capability_meta(resource_types=["address"]),
    )
    def gcp_list_addresses(project_id: str | None = None) -> dict[str, Any]:
        """List reserved IP addresses.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """

        def _run(resolved: str) -> Any:
            regional = list_regional_addresses(client_factory, project_id=resolved)
            global_addresses = list_global_addresses(client_factory, project_id=resolved)
            return CollectionResult(
                data=[*regional.data, *global_addresses], warnings=regional.warnings
            )

        return execute_tool_with_resolved_project(
            tool_name=TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )
