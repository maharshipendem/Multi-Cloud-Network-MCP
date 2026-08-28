"""MCP tools: gcp_list_interconnects, gcp_list_interconnect_attachments,
gcp_list_interconnect_locations, gcp_get_interconnect_diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.interconnect import (
    get_interconnect_diagnostics,
    list_interconnect_attachments,
    list_interconnect_locations,
    list_interconnects,
)
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_INTERCONNECTS = "gcp_list_interconnects"
_LIST_ATTACHMENTS = "gcp_list_interconnect_attachments"
_LIST_LOCATIONS = "gcp_list_interconnect_locations"
_GET_DIAGNOSTICS = "gcp_get_interconnect_diagnostics"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_INTERCONNECTS,
        description="List Dedicated Interconnects visible to this identity in a project.",
        meta=capability_meta(resource_types=["interconnect"]),
    )
    def gcp_list_interconnects(project_id: str | None = None) -> dict[str, Any]:
        """List Interconnects.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_INTERCONNECTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_interconnects(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_ATTACHMENTS,
        description=(
            "List Interconnect attachments (Dedicated and Partner) across every region in a "
            "project. Never carries a Partner Interconnect pairing key -- that field is never "
            "read by this server."
        ),
        meta=capability_meta(resource_types=["interconnect_attachment"]),
    )
    def gcp_list_interconnect_attachments(project_id: str | None = None) -> dict[str, Any]:
        """List Interconnect attachments.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_ATTACHMENTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_interconnect_attachments(
                client_factory, project_id=resolved
            ),
        )

    @mcp.tool(
        name=_LIST_LOCATIONS,
        description=(
            "List Interconnect colocation facilities available for Dedicated "
            "Interconnect provisioning."
        ),
        meta=capability_meta(resource_types=["interconnect_location"]),
    )
    def gcp_list_interconnect_locations(project_id: str | None = None) -> dict[str, Any]:
        """List Interconnect locations (global metadata).

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_LOCATIONS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_interconnect_locations(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_GET_DIAGNOSTICS,
        description=(
            "Return the read-only computed physical-link diagnostics for one Interconnect: "
            "per-link operational status and optical power readings."
        ),
        meta=capability_meta(resource_types=["interconnect"]),
    )
    def gcp_get_interconnect_diagnostics(
        interconnect_name: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Get Interconnect diagnostics.

        Args:
            interconnect_name: Name of the Interconnect.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_GET_DIAGNOSTICS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_interconnect_diagnostics(
                client_factory, project_id=resolved, interconnect_name=interconnect_name
            ),
        )
