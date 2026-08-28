"""MCP tools: gcp_list_vpn_gateways, gcp_list_vpn_tunnels,
gcp_list_external_vpn_gateways, gcp_get_vpn_gateway_status."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.vpn import (
    get_vpn_gateway_status,
    list_external_vpn_gateways,
    list_vpn_gateways,
    list_vpn_tunnels,
)
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_GATEWAYS = "gcp_list_vpn_gateways"
_LIST_TUNNELS = "gcp_list_vpn_tunnels"
_LIST_EXTERNAL_GATEWAYS = "gcp_list_external_vpn_gateways"
_GET_GATEWAY_STATUS = "gcp_get_vpn_gateway_status"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_GATEWAYS,
        description="List HA Cloud VPN gateways across every region in a project.",
        meta=capability_meta(resource_types=["vpn_gateway"]),
    )
    def gcp_list_vpn_gateways(project_id: str | None = None) -> dict[str, Any]:
        """List HA VPN gateways.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_GATEWAYS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_vpn_gateways(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_TUNNELS,
        description=(
            "List VPN tunnels across every region in a project. Never carries the IKE "
            "pre-shared key -- that field is never read by this server."
        ),
        meta=capability_meta(resource_types=["vpn_tunnel"]),
    )
    def gcp_list_vpn_tunnels(project_id: str | None = None) -> dict[str, Any]:
        """List VPN tunnels.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_TUNNELS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_vpn_tunnels(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_LIST_EXTERNAL_GATEWAYS,
        description="List external (on-premises/other-cloud) VPN gateway definitions in a project.",
        meta=capability_meta(resource_types=["external_vpn_gateway"]),
    )
    def gcp_list_external_vpn_gateways(project_id: str | None = None) -> dict[str, Any]:
        """List external VPN gateways.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_EXTERNAL_GATEWAYS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_external_vpn_gateways(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_GET_GATEWAY_STATUS,
        description=(
            "Return the read-only computed HA-redundancy status for one VPN gateway: "
            "each peer connection's tunnels and whether GCP's HA redundancy requirement is met."
        ),
        meta=capability_meta(resource_types=["vpn_gateway"]),
    )
    def gcp_get_vpn_gateway_status(
        region: str, vpn_gateway_name: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Get a VPN gateway's HA status.

        Args:
            region: Region the VPN gateway is in.
            vpn_gateway_name: Name of the VPN gateway.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_GET_GATEWAY_STATUS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_vpn_gateway_status(
                client_factory,
                project_id=resolved,
                region=region,
                vpn_gateway_name=vpn_gateway_name,
            ),
        )
