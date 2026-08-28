"""ARM service layer: VPN connectivity, both vWAN-scoped (VpnGateway,
VpnSite, VpnConnection) and classic/VNet-attached (VirtualNetworkGateway,
LocalNetworkGateway, VirtualNetworkGatewayConnection).

Never reads ``shared_key``, ``site_key``, or ``authorization_key`` from
any SDK response -- see models/hybrid_connectivity.py's module docstring
for the full redaction-by-omission rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly_lro
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.hybrid_connectivity import (
    BgpPeerStatusEntry,
    BgpSettingsSummary,
    LocalNetworkGateway,
    VirtualNetworkGateway,
    VirtualNetworkGatewayConnection,
    VpnConnection,
    VpnGateway,
    VpnSite,
    VpnSiteLinkSummary,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _bgp_settings_summary(bgp: Any) -> BgpSettingsSummary | None:
    if bgp is None:
        return None
    return BgpSettingsSummary(
        asn=getattr(bgp, "asn", None),
        bgp_peering_address=getattr(bgp, "bgp_peering_address", None),
        peer_weight=getattr(bgp, "peer_weight", None),
    )


# --- vWAN-scoped VPN -----------------------------------------------------------


def list_vpn_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VpnGateway]:
    """Call VpnGatewaysOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.vpn_gateways,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.vpn_gateways, "list", max_items=settings.max_page_results)

    result = []
    for gw in raw:
        parsed = parse_resource_id(gw.id)
        result.append(
            VpnGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/vpnGateways",
                virtual_hub_id=(gw.virtual_hub.id if getattr(gw, "virtual_hub", None) else None),
                bgp_settings=_bgp_settings_summary(getattr(gw, "bgp_settings", None)),
                vpn_gateway_scale_unit=getattr(gw, "vpn_gateway_scale_unit", None),
                connection_ids=[c.id for c in (gw.connections or []) if getattr(c, "id", None)],
            )
        )
    return result


def list_vpn_sites(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VpnSite]:
    """Call VpnSitesOperations.list (whole subscription) or
    .list_by_resource_group (one resource group). Never reads ``site_key``."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.vpn_sites,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.vpn_sites, "list", max_items=settings.max_page_results)

    result = []
    for site in raw:
        parsed = parse_resource_id(site.id)
        device = getattr(site, "device_properties", None)
        address_space = getattr(site, "address_space", None)
        result.append(
            VpnSite(
                resource_id=site.id,
                name=site.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=site.location,
                provisioning_state=getattr(site, "provisioning_state", None),
                tags=normalize_tags(site.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/vpnSites",
                virtual_wan_id=(
                    site.virtual_wan.id if getattr(site, "virtual_wan", None) else None
                ),
                device_vendor=getattr(device, "device_vendor", None) if device else None,
                device_model=getattr(device, "device_model", None) if device else None,
                address_space=list((address_space.address_prefixes or []) if address_space else []),
                is_security_site=getattr(site, "is_security_site", None),
                links=[
                    VpnSiteLinkSummary(
                        name=link.name,
                        ip_address=getattr(link, "ip_address", None),
                        link_speed_in_mbps=(
                            getattr(link.link_properties, "link_speed_in_mbps", None)
                            if getattr(link, "link_properties", None)
                            else None
                        ),
                        provider_name=(
                            getattr(link.link_properties, "link_provider_name", None)
                            if getattr(link, "link_properties", None)
                            else None
                        ),
                    )
                    for link in (getattr(site, "vpn_site_links", None) or [])
                ],
            )
        )
    return result


def list_vpn_connections(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    vpn_gateway_name: str,
) -> list[VpnConnection]:
    """Call VpnConnectionsOperations.list_by_vpn_gateway. Never reads
    ``shared_key``."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.vpn_connections,
        "list_by_vpn_gateway",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        gateway_name=vpn_gateway_name,
    )
    result = []
    for conn in raw:
        parsed = parse_resource_id(conn.id)
        result.append(
            VpnConnection(
                resource_id=conn.id,
                name=conn.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(conn, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/vpnGateways/vpnConnections",
                vpn_gateway_name=vpn_gateway_name,
                remote_vpn_site_id=(
                    conn.remote_vpn_site.id if getattr(conn, "remote_vpn_site", None) else None
                ),
                connection_status=getattr(conn, "connection_status", None),
                vpn_connection_protocol_type=getattr(conn, "vpn_connection_protocol_type", None),
                enable_bgp=getattr(conn, "enable_bgp", None),
                routing_weight=getattr(conn, "routing_weight", None),
                ingress_bytes_transferred=getattr(conn, "ingress_bytes_transferred", None),
                egress_bytes_transferred=getattr(conn, "egress_bytes_transferred", None),
            )
        )
    return result


# --- Classic / VNet-attached gateways -------------------------------------------


def list_virtual_network_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str
) -> list[VirtualNetworkGateway]:
    """Call VirtualNetworkGatewaysOperations.list. This operation is
    scoped to one resource group -- the SDK has no whole-subscription
    list for this resource type."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_network_gateways,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
    )
    result = []
    for gw in raw:
        parsed = parse_resource_id(gw.id)
        sku = getattr(gw, "sku", None)
        result.append(
            VirtualNetworkGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualNetworkGateways",
                gateway_type=getattr(gw, "gateway_type", None),
                vpn_type=getattr(gw, "vpn_type", None),
                sku_name=(getattr(sku, "name", None) if sku else None),
                sku_tier=(getattr(sku, "tier", None) if sku else None),
                active_active=getattr(gw, "active_active", None),
                enable_bgp=getattr(gw, "enable_bgp", None),
                bgp_settings=_bgp_settings_summary(getattr(gw, "bgp_settings", None)),
            )
        )
    return result


def list_local_network_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str
) -> list[LocalNetworkGateway]:
    """Call LocalNetworkGatewaysOperations.list. Resource-group-scoped only."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.local_network_gateways,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
    )
    result = []
    for gw in raw:
        parsed = parse_resource_id(gw.id)
        address_space = getattr(gw, "local_network_address_space", None)
        result.append(
            LocalNetworkGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/localNetworkGateways",
                gateway_ip_address=getattr(gw, "gateway_ip_address", None),
                fqdn=getattr(gw, "fqdn", None),
                local_network_address_space=list(
                    (address_space.address_prefixes or []) if address_space else []
                ),
                bgp_settings=_bgp_settings_summary(getattr(gw, "bgp_settings", None)),
            )
        )
    return result


def list_virtual_network_gateway_connections(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str
) -> list[VirtualNetworkGatewayConnection]:
    """Call VirtualNetworkGatewayConnectionsOperations.list. Never reads
    ``authorization_key`` or ``shared_key``. Resource-group-scoped only."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_network_gateway_connections,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
    )
    result = []
    for conn in raw:
        parsed = parse_resource_id(conn.id)
        result.append(
            VirtualNetworkGatewayConnection(
                resource_id=conn.id,
                name=conn.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=conn.location,
                provisioning_state=getattr(conn, "provisioning_state", None),
                tags=normalize_tags(conn.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/connections",
                virtual_network_gateway1_id=(
                    conn.virtual_network_gateway1.id
                    if getattr(conn, "virtual_network_gateway1", None)
                    else None
                ),
                virtual_network_gateway2_id=(
                    conn.virtual_network_gateway2.id
                    if getattr(conn, "virtual_network_gateway2", None)
                    else None
                ),
                local_network_gateway2_id=(
                    conn.local_network_gateway2.id
                    if getattr(conn, "local_network_gateway2", None)
                    else None
                ),
                connection_type=getattr(conn, "connection_type", None),
                connection_status=getattr(conn, "connection_status", None),
                enable_bgp=getattr(conn, "enable_bgp", None),
                routing_weight=getattr(conn, "routing_weight", None),
                ingress_bytes_transferred=getattr(conn, "ingress_bytes_transferred", None),
                egress_bytes_transferred=getattr(conn, "egress_bytes_transferred", None),
            )
        )
    return result


def get_bgp_peer_status(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_network_gateway_name: str,
) -> list[BgpPeerStatusEntry]:
    """Call VirtualNetworkGatewaysOperations.begin_get_bgp_peer_status --
    the current BGP session state for a classic gateway's configured
    peers. Read-only despite the ``begin_`` prefix; see
    security/guardrails.py's module docstring.
    """
    client = client_factory.get_network_client(subscription_id)
    result = call_readonly_lro(
        client.virtual_network_gateways,
        "begin_get_bgp_peer_status",
        resource_group_name=resource_group,
        virtual_network_gateway_name=virtual_network_gateway_name,
    )
    return [
        BgpPeerStatusEntry(
            neighbor=getattr(p, "neighbor", None),
            asn=getattr(p, "asn", None),
            state=getattr(p, "state", None),
            connected_duration=getattr(p, "connected_duration", None),
            routes_received=getattr(p, "routes_received", None),
            messages_sent=getattr(p, "messages_sent", None),
            messages_received=getattr(p, "messages_received", None),
        )
        for p in (getattr(result, "value", None) or [])
    ]


__all__ = [
    "get_bgp_peer_status",
    "list_local_network_gateways",
    "list_virtual_network_gateway_connections",
    "list_virtual_network_gateways",
    "list_vpn_connections",
    "list_vpn_gateways",
    "list_vpn_sites",
]
