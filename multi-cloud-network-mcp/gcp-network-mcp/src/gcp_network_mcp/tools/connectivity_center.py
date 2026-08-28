"""MCP tools: gcp_list_ncc_hubs, gcp_list_ncc_spokes, gcp_list_ncc_groups,
gcp_list_ncc_route_tables, gcp_list_ncc_routes, gcp_get_ncc_hub_status."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.connectivity_center import (
    get_hub_status,
    list_groups,
    list_hubs,
    list_ncc_routes,
    list_route_tables,
    list_spokes,
)
from gcp_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_HUBS = "gcp_list_ncc_hubs"
_LIST_SPOKES = "gcp_list_ncc_spokes"
_LIST_GROUPS = "gcp_list_ncc_groups"
_LIST_ROUTE_TABLES = "gcp_list_ncc_route_tables"
_LIST_ROUTES = "gcp_list_ncc_routes"
_GET_HUB_STATUS = "gcp_get_ncc_hub_status"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_HUBS,
        description="List Network Connectivity Center hubs in a project (global resources).",
        meta=capability_meta(resource_types=["ncc_hub"]),
    )
    def gcp_list_ncc_hubs(project_id: str | None = None) -> dict[str, Any]:
        """List NCC hubs.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_HUBS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_hubs(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_SPOKES,
        description="List Network Connectivity Center spokes across every region in a project.",
        meta=capability_meta(resource_types=["ncc_spoke"]),
    )
    def gcp_list_ncc_spokes(project_id: str | None = None) -> dict[str, Any]:
        """List NCC spokes.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_SPOKES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_spokes(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_GROUPS,
        description="List the groups defined under one Network Connectivity Center hub.",
        meta=capability_meta(resource_types=["ncc_group"]),
    )
    def gcp_list_ncc_groups(hub_name: str, project_id: str | None = None) -> dict[str, Any]:
        """List NCC groups under a hub.

        Args:
            hub_name: Full hub resource name (projects/{p}/locations/global/hubs/{hub}).
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_GROUPS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_groups(
                client_factory, hub_name=hub_name, project_id=resolved
            ),
        )

    @mcp.tool(
        name=_LIST_ROUTE_TABLES,
        description="List the route tables defined under one Network Connectivity Center hub.",
        meta=capability_meta(resource_types=["ncc_route_table"]),
    )
    def gcp_list_ncc_route_tables(hub_name: str, project_id: str | None = None) -> dict[str, Any]:
        """List NCC route tables under a hub.

        Args:
            hub_name: Full hub resource name (projects/{p}/locations/global/hubs/{hub}).
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_ROUTE_TABLES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_route_tables(
                client_factory, hub_name=hub_name, project_id=resolved
            ),
        )

    @mcp.tool(
        name=_LIST_ROUTES,
        description="List the routes in one Network Connectivity Center route table.",
        meta=capability_meta(resource_types=["ncc_route"]),
    )
    def gcp_list_ncc_routes(route_table_name: str, project_id: str | None = None) -> dict[str, Any]:
        """List NCC routes in a route table.

        Args:
            route_table_name: Full route table resource name
                (projects/{p}/locations/global/hubs/{hub}/routeTables/{rt}).
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_ROUTES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_ncc_routes(
                client_factory, route_table_name=route_table_name, project_id=resolved
            ),
        )

    @mcp.tool(
        name=_GET_HUB_STATUS,
        description=(
            "Return the read-only computed status view for one Network Connectivity Center "
            "hub: PSC propagation status entries. Never triggers propagation itself."
        ),
        meta=capability_meta(resource_types=["ncc_hub"]),
    )
    def gcp_get_ncc_hub_status(hub_name: str) -> dict[str, Any]:
        """Get NCC hub status.

        Args:
            hub_name: Full hub resource name (projects/{p}/locations/global/hubs/{hub}).
        """
        return execute_tool(
            tool_name=_GET_HUB_STATUS,
            project_id=None,
            func=lambda: get_hub_status(client_factory, hub_name=hub_name),
        )
