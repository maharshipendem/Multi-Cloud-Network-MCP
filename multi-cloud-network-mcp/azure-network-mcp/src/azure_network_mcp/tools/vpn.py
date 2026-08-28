"""MCP tools: VPN connectivity, both vWAN-scoped (VpnGateway, VpnSite,
VpnConnection) and classic/VNet-attached (VirtualNetworkGateway,
LocalNetworkGateway, VirtualNetworkGatewayConnection)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.vpn import (
    get_bgp_peer_status,
    list_local_network_gateways,
    list_virtual_network_gateway_connections,
    list_virtual_network_gateways,
    list_vpn_connections,
    list_vpn_gateways,
    list_vpn_sites,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_VPN_GATEWAYS = "azure_list_vpn_gateways"
_LIST_VPN_SITES = "azure_list_vpn_sites"
_LIST_VPN_CONNECTIONS = "azure_list_vpn_connections"
_LIST_VNET_GATEWAYS = "azure_list_virtual_network_gateways"
_LIST_LOCAL_GATEWAYS = "azure_list_local_network_gateways"
_LIST_VNET_GATEWAY_CONNECTIONS = "azure_list_virtual_network_gateway_connections"
_GET_BGP_PEER_STATUS = "azure_get_bgp_peer_status"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VPN_GATEWAYS,
        description=(
            "List vWAN-scoped VPN gateways (whole subscription, or one resource "
            "group), including BGP settings and connection references."
        ),
        meta=capability_meta(resource_types=["vpn_gateway"]),
    )
    def azure_list_vpn_gateways(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List VPN gateways.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VPN_GATEWAYS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_vpn_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_VPN_SITES,
        description=(
            "List VPN sites (on-premises endpoints, whole subscription or one "
            "resource group). Never includes the site's pre-shared key."
        ),
        meta=capability_meta(resource_types=["vpn_site"]),
    )
    def azure_list_vpn_sites(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List VPN sites.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VPN_SITES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_vpn_sites(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_VPN_CONNECTIONS,
        description=(
            "List a vWAN VPN gateway's connections to its sites, including "
            "connection status and traffic counters. Never includes the "
            "connection's pre-shared key."
        ),
        meta=capability_meta(resource_types=["vpn_connection"]),
    )
    def azure_list_vpn_connections(
        resource_group: str, vpn_gateway_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List VPN connections.

        Args:
            resource_group: Resource group containing the VPN gateway.
            vpn_gateway_name: Name of the VPN gateway.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VPN_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_vpn_connections(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                vpn_gateway_name=vpn_gateway_name,
            ),
        )

    @mcp.tool(
        name=_LIST_VNET_GATEWAYS,
        description=(
            "List classic (non-vWAN) Virtual Network Gateways in one resource "
            "group -- VPN or ExpressRoute gateways attached directly to a VNet."
        ),
        meta=capability_meta(resource_types=["virtual_network_gateway"]),
    )
    def azure_list_virtual_network_gateways(
        resource_group: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Virtual Network Gateways.

        Args:
            resource_group: Resource group to list gateways in (required --
                the Azure SDK has no whole-subscription list for this type).
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VNET_GATEWAYS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_network_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_LOCAL_GATEWAYS,
        description=(
            "List Local Network Gateways in one resource group -- the "
            "on-premises side of a classic Site-to-Site VPN connection."
        ),
        meta=capability_meta(resource_types=["local_network_gateway"]),
    )
    def azure_list_local_network_gateways(
        resource_group: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Local Network Gateways.

        Args:
            resource_group: Resource group to list gateways in (required).
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_LOCAL_GATEWAYS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_local_network_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_VNET_GATEWAY_CONNECTIONS,
        description=(
            "List classic Site-to-Site, VNet-to-VNet, or ExpressRoute "
            "connections in one resource group. Never includes the connection's "
            "authorization key or pre-shared key."
        ),
        meta=capability_meta(resource_types=["virtual_network_gateway_connection"]),
    )
    def azure_list_virtual_network_gateway_connections(
        resource_group: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Virtual Network Gateway connections.

        Args:
            resource_group: Resource group to list connections in (required).
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_VNET_GATEWAY_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_virtual_network_gateway_connections(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_GET_BGP_PEER_STATUS,
        description=(
            "Get the current BGP session state for a classic Virtual Network "
            "Gateway's configured peers. A read-only computation despite the "
            "SDK's 'begin_' method prefix."
        ),
        meta=capability_meta(resource_types=["virtual_network_gateway"]),
    )
    def azure_get_bgp_peer_status(
        resource_group: str,
        virtual_network_gateway_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a Virtual Network Gateway's BGP peer status.

        Args:
            resource_group: Resource group containing the gateway.
            virtual_network_gateway_name: Name of the Virtual Network Gateway.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_BGP_PEER_STATUS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_bgp_peer_status(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_gateway_name=virtual_network_gateway_name,
            ),
        )
