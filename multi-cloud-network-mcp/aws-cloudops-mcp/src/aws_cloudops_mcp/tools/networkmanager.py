"""MCP tools: Network Manager and Cloud WAN."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.networkmanager import (
    list_core_networks,
    list_global_networks,
    list_network_manager_connections,
    list_network_manager_devices,
    list_network_manager_links,
    list_network_manager_sites,
    list_transit_gateway_registrations,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_CORE_NETWORKS = "aws_list_core_networks"
_LIST_GLOBAL_NETWORKS = "aws_list_global_networks"
_LIST_SITES = "aws_list_network_manager_sites"
_LIST_DEVICES = "aws_list_network_manager_devices"
_LIST_LINKS = "aws_list_network_manager_links"
_LIST_CONNECTIONS = "aws_list_network_manager_connections"
_LIST_TGW_REGISTRATIONS = "aws_list_transit_gateway_registrations"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_CORE_NETWORKS,
        description=(
            "List Cloud WAN core networks, optionally with segment/edge "
            "details and policy document (networkmanager:ListCoreNetworks"
            "+GetCoreNetwork+GetCoreNetworkPolicy). An account with no Cloud "
            "WAN usage returns an empty list, not an error; unsupported "
            "enrichment degrades to a warning."
        ),
        meta=capability_meta(resource_types=["core_network"]),
    )
    def aws_list_core_networks(
        region: str, include_details: bool = False, include_policy: bool = False
    ) -> dict[str, Any]:
        """List Cloud WAN core networks.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            include_details: If true, also fetch each core network's
                segments/edges (1 extra API call per core network, bounded
                and best-effort).
            include_policy: If true, also fetch each core network's policy
                document (1 extra API call per core network, bounded,
                best-effort, and size-capped).
        """
        return execute_tool(
            tool_name=_LIST_CORE_NETWORKS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_core_networks(
                client_factory,
                region=region,
                include_details=include_details,
                include_policy=include_policy,
            ),
        )

    @mcp.tool(
        name=_LIST_GLOBAL_NETWORKS,
        description="List Network Manager global networks (networkmanager:DescribeGlobalNetworks).",
        meta=capability_meta(resource_types=["global_network"]),
    )
    def aws_list_global_networks(
        region: str, global_network_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List global networks.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_ids: Optional list of global network IDs.
        """
        return execute_tool(
            tool_name=_LIST_GLOBAL_NETWORKS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_global_networks(
                client_factory, region=region, global_network_ids=global_network_ids
            ),
        )

    @mcp.tool(
        name=_LIST_SITES,
        description="List Network Manager sites for a global network (networkmanager:GetSites).",
        meta=capability_meta(resource_types=["network_manager_site"]),
    )
    def aws_list_network_manager_sites(region: str, global_network_id: str) -> dict[str, Any]:
        """List Network Manager sites.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_id: The global network to list sites for.
        """
        return execute_tool(
            tool_name=_LIST_SITES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_manager_sites(
                client_factory, region=region, global_network_id=global_network_id
            ),
        )

    @mcp.tool(
        name=_LIST_DEVICES,
        description=(
            "List Network Manager devices for a global network (networkmanager:GetDevices)."
        ),
        meta=capability_meta(resource_types=["network_manager_device"]),
    )
    def aws_list_network_manager_devices(region: str, global_network_id: str) -> dict[str, Any]:
        """List Network Manager devices.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_id: The global network to list devices for.
        """
        return execute_tool(
            tool_name=_LIST_DEVICES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_manager_devices(
                client_factory, region=region, global_network_id=global_network_id
            ),
        )

    @mcp.tool(
        name=_LIST_LINKS,
        description="List Network Manager links for a global network (networkmanager:GetLinks).",
        meta=capability_meta(resource_types=["network_manager_link"]),
    )
    def aws_list_network_manager_links(region: str, global_network_id: str) -> dict[str, Any]:
        """List Network Manager links.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_id: The global network to list links for.
        """
        return execute_tool(
            tool_name=_LIST_LINKS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_manager_links(
                client_factory, region=region, global_network_id=global_network_id
            ),
        )

    @mcp.tool(
        name=_LIST_CONNECTIONS,
        description=(
            "List Network Manager connections for a global network (networkmanager:GetConnections)."
        ),
        meta=capability_meta(resource_types=["network_manager_connection"]),
    )
    def aws_list_network_manager_connections(region: str, global_network_id: str) -> dict[str, Any]:
        """List Network Manager connections.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_id: The global network to list connections for.
        """
        return execute_tool(
            tool_name=_LIST_CONNECTIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_manager_connections(
                client_factory, region=region, global_network_id=global_network_id
            ),
        )

    @mcp.tool(
        name=_LIST_TGW_REGISTRATIONS,
        description=(
            "List Transit Gateway registrations to a Network Manager global "
            "network (networkmanager:GetTransitGatewayRegistrations)."
        ),
        meta=capability_meta(resource_types=["transit_gateway_registration"]),
    )
    def aws_list_transit_gateway_registrations(
        region: str, global_network_id: str
    ) -> dict[str, Any]:
        """List Transit Gateway registrations.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            global_network_id: The global network to list registrations for.
        """
        return execute_tool(
            tool_name=_LIST_TGW_REGISTRATIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_transit_gateway_registrations(
                client_factory, region=region, global_network_id=global_network_id
            ),
        )
