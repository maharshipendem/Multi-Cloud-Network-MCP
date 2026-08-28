"""Normalized models for Virtual WAN/Virtual Hub, VPN (vWAN-scoped and
classic), and ExpressRoute -- the hybrid connectivity surface Milestone 6
covers.

Several underlying Azure SDK models embed secret-shaped fields directly as
flattened attributes (``VpnConnection.shared_key``,
``VpnSiteLinkConnection.shared_key``, ``VpnSite.site_key``,
``ExpressRouteCircuit.authorization_key``/``service_key``,
``ExpressRouteCircuitPeering.shared_key``,
``ExpressRouteCircuitConnection.authorization_key``,
``ExpressRouteConnection.authorization_key``,
``VirtualNetworkGatewayConnection.authorization_key``/``shared_key``) --
none of those fields are read by any normalizer in ``arm/vpn.py`` or
``arm/expressroute.py``. This is redaction *by omission*, the same pattern
this milestone's own AWS-sibling precedent (VPN pre-shared keys, Direct
Connect BGP auth keys) established: a field that is never read cannot leak
regardless of what the raw SDK response contains. Every model below that
corresponds to a resource type carrying such a field is stamped
``redacted: bool = True`` so a client can tell the record is intentionally
incomplete rather than assume it saw everything. See
docs/security.md#redaction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource

# --- Virtual WAN / Virtual Hub ------------------------------------------------


class VirtualWan(AzureResource):
    """Normalized entry from VirtualWansOperations.list/list_by_resource_group/get."""

    disable_vpn_encryption: bool | None = None
    allow_branch_to_branch_traffic: bool | None = None
    office365_local_breakout_category: str | None = None
    virtual_hub_ids: list[str] = Field(default_factory=list)
    vpn_site_ids: list[str] = Field(default_factory=list)


class HubRoute(BaseModel):
    """One static route within a Virtual Hub's route table."""

    name: str | None = None
    destination_type: str | None = None
    destinations: list[str] = Field(default_factory=list)
    next_hop_type: str | None = None
    next_hop: str | None = None


class HubRouteTable(AzureResource):
    """Normalized entry from HubRouteTablesOperations.list/get."""

    virtual_hub_name: str | None = None
    routes: list[HubRoute] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    associated_connection_ids: list[str] = Field(default_factory=list)
    propagating_connection_ids: list[str] = Field(default_factory=list)


class HubVirtualNetworkConnection(AzureResource):
    """Normalized entry from HubVirtualNetworkConnectionsOperations.list/get --
    a VNet's connection into a Virtual Hub."""

    virtual_hub_name: str | None = None
    remote_virtual_network_id: str | None = None
    allow_hub_to_remote_vnet_transit: bool | None = None
    allow_remote_vnet_to_use_hub_vnet_gateways: bool | None = None
    enable_internet_security: bool | None = None
    associated_route_table_id: str | None = None
    propagated_route_table_ids: list[str] = Field(default_factory=list)


class BgpHubConnection(AzureResource):
    """Normalized entry from VirtualHubBgpConnectionsOperations.list --
    a BGP peer of a Virtual Hub (used both for a vWAN hub's own routing and
    for a standalone Azure Route Server, which is modeled as a Virtual Hub
    with no ``virtual_wan`` reference).
    """

    virtual_hub_name: str | None = None
    peer_asn: int | None = None
    peer_ip: str | None = None
    connection_state: str | None = None


class PeerRoute(BaseModel):
    """One route entry from
    VirtualHubBgpConnectionsOperations.begin_list_advertised_routes/
    begin_list_learned_routes -- a route a hub BGP connection has
    advertised to, or learned from, its peer. Read-only despite the
    ``begin_`` prefix; see security/guardrails.py's module docstring."""

    network: str | None = None
    next_hop: str | None = None
    source_peer: str | None = None
    origin: str | None = None
    as_path: str | None = None
    weight: int | None = None


class RouteMapRuleSummary(BaseModel):
    name: str | None = None
    next_step_if_matched: str | None = None


class RouteMap(AzureResource):
    """Normalized entry from RouteMapsOperations.list/get -- a vWAN
    routing-intent policy applied to a Virtual Hub's route propagation."""

    virtual_hub_name: str | None = None
    associated_inbound_connection_ids: list[str] = Field(default_factory=list)
    associated_outbound_connection_ids: list[str] = Field(default_factory=list)
    rules: list[RouteMapRuleSummary] = Field(default_factory=list)


class VirtualHub(AzureResource):
    """Normalized entry from VirtualHubsOperations.list/list_by_resource_group/get.

    ``is_route_server`` is derived (not an Azure API field): true when
    ``sku == "Standard"`` and ``virtual_wan_id`` is unset, the pattern
    Azure itself uses to represent a standalone Route Server as a Virtual
    Hub resource -- see ``arm/route_server.py``.
    """

    virtual_wan_id: str | None = None
    address_prefix: str | None = None
    sku: str | None = None
    routing_state: str | None = None
    virtual_router_asn: int | None = None
    virtual_router_ips: list[str] = Field(default_factory=list)
    allow_branch_to_branch_traffic: bool | None = None
    hub_routing_preference: str | None = None
    is_route_server: bool = False


# --- VPN (vWAN-scoped) --------------------------------------------------------


class BgpSettingsSummary(BaseModel):
    asn: int | None = None
    bgp_peering_address: str | None = None
    peer_weight: int | None = None


class VpnSiteLinkSummary(BaseModel):
    """A VPN site's individual physical link (embedded on the site, not
    the SDK's separately-fetchable VpnSiteLink resource)."""

    name: str | None = None
    ip_address: str | None = None
    link_speed_in_mbps: int | None = None
    provider_name: str | None = None


class VpnSite(AzureResource):
    """Normalized entry from VpnSitesOperations.list/list_by_resource_group/get.

    Never reads ``site_key`` -- see this module's docstring.
    """

    virtual_wan_id: str | None = None
    device_vendor: str | None = None
    device_model: str | None = None
    address_space: list[str] = Field(default_factory=list)
    is_security_site: bool | None = None
    links: list[VpnSiteLinkSummary] = Field(default_factory=list)
    redacted: bool = True


class VpnGateway(AzureResource):
    """Normalized entry from VpnGatewaysOperations.list/list_by_resource_group/get."""

    virtual_hub_id: str | None = None
    bgp_settings: BgpSettingsSummary | None = None
    vpn_gateway_scale_unit: int | None = None
    connection_ids: list[str] = Field(default_factory=list)


class VpnConnection(AzureResource):
    """Normalized entry from VpnConnectionsOperations.list_by_vpn_gateway/get
    -- a vWAN VPN gateway's connection to one VPN site.

    Never reads ``shared_key`` -- see this module's docstring.
    """

    vpn_gateway_name: str | None = None
    remote_vpn_site_id: str | None = None
    connection_status: str | None = None
    vpn_connection_protocol_type: str | None = None
    enable_bgp: bool | None = None
    routing_weight: int | None = None
    ingress_bytes_transferred: int | None = None
    egress_bytes_transferred: int | None = None
    redacted: bool = True


# --- Virtual Network Gateway (classic) ----------------------------------------


class VirtualNetworkGateway(AzureResource):
    """Normalized entry from VirtualNetworkGatewaysOperations.list/get --
    a classic (non-vWAN) VPN or ExpressRoute gateway attached directly to
    a VNet."""

    gateway_type: str | None = None
    vpn_type: str | None = None
    sku_name: str | None = None
    sku_tier: str | None = None
    active_active: bool | None = None
    enable_bgp: bool | None = None
    bgp_settings: BgpSettingsSummary | None = None


class LocalNetworkGateway(AzureResource):
    """Normalized entry from LocalNetworkGatewaysOperations.list/get -- the
    on-premises side of a classic Site-to-Site VPN connection."""

    gateway_ip_address: str | None = None
    fqdn: str | None = None
    local_network_address_space: list[str] = Field(default_factory=list)
    bgp_settings: BgpSettingsSummary | None = None


class VirtualNetworkGatewayConnection(AzureResource):
    """Normalized entry from VirtualNetworkGatewayConnectionsOperations.list/get
    -- a classic Site-to-Site, VNet-to-VNet, or ExpressRoute connection.

    Never reads ``authorization_key`` or ``shared_key`` -- see this
    module's docstring.
    """

    virtual_network_gateway1_id: str | None = None
    virtual_network_gateway2_id: str | None = None
    local_network_gateway2_id: str | None = None
    connection_type: str | None = None
    connection_status: str | None = None
    enable_bgp: bool | None = None
    routing_weight: int | None = None
    ingress_bytes_transferred: int | None = None
    egress_bytes_transferred: int | None = None
    redacted: bool = True


class BgpPeerStatusEntry(BaseModel):
    """One entry from
    VirtualNetworkGatewaysOperations.begin_get_bgp_peer_status -- the
    current BGP session state Azure observes for one configured peer.
    Read-only despite the ``begin_`` prefix; see
    security/guardrails.py's module docstring."""

    neighbor: str | None = None
    asn: int | None = None
    state: str | None = None
    connected_duration: str | None = None
    routes_received: int | None = None
    messages_sent: int | None = None
    messages_received: int | None = None


# --- ExpressRoute --------------------------------------------------------------


class ExpressRouteCircuitPeering(AzureResource):
    """Normalized entry from ExpressRouteCircuitPeeringsOperations.list/get.

    Never reads ``shared_key`` -- see this module's docstring.
    """

    circuit_name: str | None = None
    peering_type: str | None = None
    state: str | None = None
    azure_asn: int | None = None
    peer_asn: int | None = None
    primary_peer_address_prefix: str | None = None
    secondary_peer_address_prefix: str | None = None
    vlan_id: int | None = None
    redacted: bool = True


class ExpressRouteCircuit(AzureResource):
    """Normalized entry from ExpressRouteCircuitsOperations.list/list_all/get.

    Never reads ``authorization_key``, ``service_key``, or
    ``authorization_status`` -- see this module's docstring.
    """

    sku_name: str | None = None
    sku_tier: str | None = None
    sku_family: str | None = None
    circuit_provisioning_state: str | None = None
    service_provider_provisioning_state: str | None = None
    service_provider_name: str | None = None
    peering_location: str | None = None
    bandwidth_in_mbps: int | None = None
    express_route_port_id: str | None = None
    global_reach_enabled: bool | None = None
    peerings: list[ExpressRouteCircuitPeering] = Field(default_factory=list)
    redacted: bool = True


class ExpressRouteCircuitConnection(AzureResource):
    """Normalized entry from ExpressRouteCircuitConnectionsOperations.list/get
    -- a circuit-to-circuit connection (Global Reach).

    Never reads ``authorization_key`` -- see this module's docstring.
    """

    circuit_name: str | None = None
    peering_name: str | None = None
    express_route_circuit_peering_id: str | None = None
    peer_express_route_circuit_peering_id: str | None = None
    address_prefix: str | None = None
    circuit_connection_status: str | None = None
    redacted: bool = True


class ExpressRouteGateway(AzureResource):
    """Normalized entry from ExpressRouteGatewaysOperations.list_by_resource_group/
    list_by_subscription/get -- a vWAN ExpressRoute gateway."""

    virtual_hub_id: str | None = None
    min_scale_units: int | None = None
    max_scale_units: int | None = None
    allow_non_virtual_wan_traffic: bool | None = None


class ExpressRouteConnection(AzureResource):
    """Normalized entry from ExpressRouteConnectionsOperations.list/get -- a
    vWAN ExpressRoute gateway's connection to one circuit peering.

    Never reads ``authorization_key`` -- see this module's docstring.
    """

    express_route_gateway_name: str | None = None
    express_route_circuit_peering_id: str | None = None
    routing_weight: int | None = None
    enable_internet_security: bool | None = None
    redacted: bool = True


class ExpressRoutePort(AzureResource):
    """Normalized entry from ExpressRoutePortsOperations.list/list_by_resource_group/get."""

    peering_location: str | None = None
    bandwidth_in_gbps: int | None = None
    provisioned_bandwidth_in_gbps: float | None = None
    encapsulation: str | None = None
    ether_type: str | None = None
    link_ids: list[str] = Field(default_factory=list)
    circuit_ids: list[str] = Field(default_factory=list)


class ExpressRouteLink(AzureResource):
    """Normalized entry from ExpressRouteLinksOperations.list/get -- one
    physical fiber link within an ExpressRoute Direct port."""

    port_name: str | None = None
    router_name: str | None = None
    interface_name: str | None = None
    colo_location: str | None = None
    admin_state: str | None = None


__all__ = [
    "BgpHubConnection",
    "BgpPeerStatusEntry",
    "BgpSettingsSummary",
    "ExpressRouteCircuit",
    "ExpressRouteCircuitConnection",
    "ExpressRouteCircuitPeering",
    "ExpressRouteConnection",
    "ExpressRouteGateway",
    "ExpressRouteLink",
    "ExpressRoutePort",
    "HubRoute",
    "HubRouteTable",
    "HubVirtualNetworkConnection",
    "LocalNetworkGateway",
    "PeerRoute",
    "RouteMap",
    "RouteMapRuleSummary",
    "VirtualHub",
    "VirtualNetworkGateway",
    "VirtualNetworkGatewayConnection",
    "VirtualWan",
    "VpnConnection",
    "VpnGateway",
    "VpnSite",
    "VpnSiteLinkSummary",
]
