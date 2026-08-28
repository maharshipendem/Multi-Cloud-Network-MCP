"""MCP tools: gcp_get_shared_vpc_host_status, gcp_list_shared_vpc_service_projects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.shared_vpc import (
    get_shared_vpc_host_relationship,
    get_shared_vpc_host_status,
)
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_GET_HOST_STATUS = "gcp_get_shared_vpc_host_status"
_LIST_SERVICE_PROJECTS = "gcp_list_shared_vpc_service_projects"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_GET_HOST_STATUS,
        description=(
            "Report whether a project is a Shared VPC host, service, or standalone project."
        ),
        meta=capability_meta(resource_types=["shared_vpc"]),
    )
    def gcp_get_shared_vpc_host_status(project_id: str | None = None) -> dict[str, Any]:
        """Get Shared VPC host status.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_GET_HOST_STATUS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_shared_vpc_host_status(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_SERVICE_PROJECTS,
        description=(
            "List the service projects attached to a Shared VPC host project. "
            "Only meaningful when the given project is actually a Shared VPC "
            "host -- check gcp_get_shared_vpc_host_status first."
        ),
        meta=capability_meta(resource_types=["shared_vpc"]),
    )
    def gcp_list_shared_vpc_service_projects(project_id: str | None = None) -> dict[str, Any]:
        """List Shared VPC service projects attached to a host project.

        Args:
            project_id: Host project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_SERVICE_PROJECTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_shared_vpc_host_relationship(
                client_factory, host_project_id=resolved
            ),
        )
