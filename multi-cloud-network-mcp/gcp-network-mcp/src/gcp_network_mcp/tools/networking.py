"""MCP tools: gcp_list_networks, gcp_list_subnetworks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.networking import list_networks, list_subnetworks
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_NETWORKS = "gcp_list_networks"
_LIST_SUBNETWORKS = "gcp_list_subnetworks"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_NETWORKS,
        description=(
            "List VPC networks in a project, including auto/custom subnet "
            "creation mode, MTU, peering names, and firewall policy "
            "associations."
        ),
        meta=capability_meta(resource_types=["network"]),
    )
    def gcp_list_networks(project_id: str | None = None) -> dict[str, Any]:
        """List VPC networks.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_NETWORKS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_networks(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_SUBNETWORKS,
        description=(
            "List subnetworks across every region in a project, including "
            "primary/secondary IP ranges, Private Google Access, and flow log "
            "settings."
        ),
        meta=capability_meta(resource_types=["subnetwork"]),
    )
    def gcp_list_subnetworks(project_id: str | None = None) -> dict[str, Any]:
        """List subnetworks.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_SUBNETWORKS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_subnetworks(client_factory, project_id=resolved),
        )
