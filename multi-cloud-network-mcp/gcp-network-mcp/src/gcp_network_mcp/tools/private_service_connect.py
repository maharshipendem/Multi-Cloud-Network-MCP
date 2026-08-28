"""MCP tools: gcp_list_service_attachments, gcp_list_psc_endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.private_service_connect import list_psc_endpoints, list_service_attachments
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_SERVICE_ATTACHMENTS = "gcp_list_service_attachments"
_LIST_PSC_ENDPOINTS = "gcp_list_psc_endpoints"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_SERVICE_ATTACHMENTS,
        description=(
            "List Private Service Connect published services (producer side) across "
            "every region in a project."
        ),
        meta=capability_meta(resource_types=["service_attachment"]),
    )
    def gcp_list_service_attachments(project_id: str | None = None) -> dict[str, Any]:
        """List PSC service attachments.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_SERVICE_ATTACHMENTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_service_attachments(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_PSC_ENDPOINTS,
        description=(
            "List Private Service Connect consumer endpoints (forwarding rules "
            "targeting a service attachment) in a project."
        ),
        meta=capability_meta(resource_types=["psc_endpoint"]),
    )
    def gcp_list_psc_endpoints(project_id: str | None = None) -> dict[str, Any]:
        """List PSC consumer endpoints.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_PSC_ENDPOINTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_psc_endpoints(client_factory, project_id=resolved),
        )
