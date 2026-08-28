"""MCP tools: gcp_list_dns_zones, gcp_list_dns_zone_records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.dns import list_dns_zone_records, list_dns_zones
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_ZONES = "gcp_list_dns_zones"
_LIST_RECORDS = "gcp_list_dns_zone_records"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_ZONES,
        description=(
            "List Cloud DNS managed zones in a project. Visibility/forwarding/peering/Policy "
            "configuration is not available -- see docs/limitations.md#cloud-dns."
        ),
        meta=capability_meta(resource_types=["dns_zone"]),
    )
    def gcp_list_dns_zones(project_id: str | None = None) -> dict[str, Any]:
        """List DNS managed zones.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_ZONES,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_dns_zones(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_RECORDS,
        description="List resource record sets in one Cloud DNS managed zone.",
        meta=capability_meta(resource_types=["dns_record_set"]),
    )
    def gcp_list_dns_zone_records(zone_name: str, project_id: str | None = None) -> dict[str, Any]:
        """List DNS zone records.

        Args:
            zone_name: Name of the managed zone.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_RECORDS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_dns_zone_records(
                client_factory, project_id=resolved, zone_name=zone_name
            ),
        )
