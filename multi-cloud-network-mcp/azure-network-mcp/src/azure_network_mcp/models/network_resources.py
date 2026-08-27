"""Normalized models for VNets, subnets, route tables, NSGs, NICs,
public IPs, peerings, NAT gateways, and load balancers/application
gateways -- the network resource surface this milestone covers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource

# --- Virtual networks / subnets --------------------------------------------


class SubnetServiceEndpoint(BaseModel):
    service: str | None = None
    locations: list[str] = Field(default_factory=list)


class SubnetDelegation(BaseModel):
    name: str | None = None
    service_name: str | None = None
    actions: list[str] = Field(default_factory=list)


class Subnet(AzureResource):
    """Normalized entry from SubnetsOperations.list/get.

    A subnet is a child resource of a VNet -- it has no ``location`` or
    ``tags`` of its own in the Azure API (both stay ``None``/empty on
    the inherited ``AzureResource`` fields); ``subscription_id``/
    ``resource_group`` are decoded from its resource ID via
    ``parse_resource_id`` since Azure doesn't return them directly.
    """

    virtual_network_name: str | None = None
    address_prefix: str | None = None
    address_prefixes: list[str] = Field(default_factory=list)
    network_security_group_id: str | None = None
    route_table_id: str | None = None
    nat_gateway_id: str | None = None
    service_endpoints: list[SubnetServiceEndpoint] = Field(default_factory=list)
    delegations: list[SubnetDelegation] = Field(default_factory=list)


class VirtualNetworkPeeringSummary(BaseModel):
    """A lightweight peering reference embedded on the VNet itself
    (``VirtualNetwork.virtual_network_peerings``) -- the full peering
    record, with state/sync-level/gateway-transit detail, is
    ``VirtualNetworkPeering`` below, returned by its own tool."""

    name: str | None = None
    remote_virtual_network_id: str | None = None
    peering_state: str | None = None


class VirtualNetwork(AzureResource):
    """Normalized entry from VirtualNetworksOperations.list_all/list/get."""

    address_space: list[str] = Field(default_factory=list)
    dns_servers: list[str] = Field(default_factory=list)
    subnet_ids: list[str] = Field(default_factory=list)
    peerings: list[VirtualNetworkPeeringSummary] = Field(default_factory=list)
    enable_ddos_protection: bool | None = None


# --- Route tables ------------------------------------------------------------


class Route(BaseModel):
    """A single normalized route within a route table.

    ``next_hop_type`` is the UDR next-hop type Azure documents:
    ``VirtualAppliance``, ``VnetLocal``, ``Internet``, ``None`` (the
    literal string, meaning "drop" -- Azure's UDR equivalent of a
    blackhole), ``VirtualNetworkGateway``, or ``HyperNetGateway``.
    """

    name: str | None = None
    address_prefix: str | None = None
    next_hop_type: str | None = None
    next_hop_ip_address: str | None = None
    provisioning_state: str | None = None


class RouteTable(AzureResource):
    """Normalized entry from RouteTablesOperations.list_all/list/get."""

    routes: list[Route] = Field(default_factory=list)
    subnet_ids: list[str] = Field(default_factory=list)
    disable_bgp_route_propagation: bool | None = None


class EffectiveRoute(BaseModel):
    """A single normalized entry from
    NetworkInterfacesOperations.begin_get_effective_route_table -- the
    route Azure actually applies, merged from system routes, UDRs, and
    BGP-propagated routes, not just what's explicitly configured."""

    name: str | None = None
    address_prefixes: list[str] = Field(default_factory=list)
    next_hop_type: str | None = None
    next_hop_ip_addresses: list[str] = Field(default_factory=list)
    source: str | None = None  # "Default" | "User" | "VirtualNetworkGateway" | ...
    state: str | None = None  # "Active" | "Invalid"


# --- Network security groups -------------------------------------------------


class SecurityRule(AzureResource):
    """Normalized entry from SecurityRulesOperations.list/get (also used
    for a NetworkSecurityGroup's embedded ``default_security_rules``).
    """

    protocol: str | None = None
    source_port_range: str | None = None
    source_port_ranges: list[str] = Field(default_factory=list)
    destination_port_range: str | None = None
    destination_port_ranges: list[str] = Field(default_factory=list)
    source_address_prefix: str | None = None
    source_address_prefixes: list[str] = Field(default_factory=list)
    destination_address_prefix: str | None = None
    destination_address_prefixes: list[str] = Field(default_factory=list)
    access: str | None = None  # "Allow" | "Deny"
    priority: int | None = None
    direction: str | None = None  # "Inbound" | "Outbound"
    description: str | None = None


class NetworkSecurityGroup(AzureResource):
    """Normalized entry from NetworkSecurityGroupsOperations.list_all/list/get.

    ``security_rules`` are the account's own custom rules;
    ``default_security_rules`` are Azure's built-in, always-present
    rules (e.g. AllowVnetInBound, DenyAllInBound) -- kept separate since
    conflating them would misrepresent which rules an operator actually
    configured versus which are Azure platform defaults.
    """

    security_rules: list[SecurityRule] = Field(default_factory=list)
    default_security_rules: list[SecurityRule] = Field(default_factory=list)
    network_interface_ids: list[str] = Field(default_factory=list)
    subnet_ids: list[str] = Field(default_factory=list)


class EffectiveSecurityRule(BaseModel):
    """A single normalized entry from
    NetworkInterfacesOperations.begin_list_effective_network_security_groups
    -- the rule Azure actually applies to a NIC, after expanding any
    Application Security Group references into their concrete IP
    prefixes (``expanded_*_address_prefix``)."""

    name: str | None = None
    protocol: str | None = None
    source_port_ranges: list[str] = Field(default_factory=list)
    destination_port_ranges: list[str] = Field(default_factory=list)
    source_address_prefixes: list[str] = Field(default_factory=list)
    destination_address_prefixes: list[str] = Field(default_factory=list)
    expanded_source_address_prefix: list[str] = Field(default_factory=list)
    expanded_destination_address_prefix: list[str] = Field(default_factory=list)
    access: str | None = None
    priority: int | None = None
    direction: str | None = None


class EffectiveNetworkSecurityGroup(BaseModel):
    network_security_group_id: str | None = None
    effective_security_rules: list[EffectiveSecurityRule] = Field(default_factory=list)


# --- Network interfaces / IP configurations ----------------------------------


class NetworkInterfaceIpConfiguration(BaseModel):
    name: str | None = None
    private_ip_address: str | None = None
    private_ip_allocation_method: str | None = None  # "Static" | "Dynamic"
    subnet_id: str | None = None
    public_ip_address_id: str | None = None
    primary: bool | None = None


class NetworkInterface(AzureResource):
    """Normalized entry from NetworkInterfacesOperations.list_all/list/get."""

    ip_configurations: list[NetworkInterfaceIpConfiguration] = Field(default_factory=list)
    network_security_group_id: str | None = None
    mac_address: str | None = None
    primary: bool | None = None
    enable_ip_forwarding: bool | None = None
    enable_accelerated_networking: bool | None = None
    virtual_machine_id: str | None = None


# --- Public IP addresses ------------------------------------------------------


class PublicIpAddress(AzureResource):
    """Normalized entry from PublicIPAddressesOperations.list_all/list/get."""

    ip_address: str | None = None
    public_ip_allocation_method: str | None = None  # "Static" | "Dynamic"
    public_ip_address_version: str | None = None  # "IPv4" | "IPv6"
    sku_name: str | None = None
    idle_timeout_in_minutes: int | None = None
    associated_resource_id: str | None = (
        None  # NIC IP config, LB frontend, etc. -- ip_configuration.id
    )


# --- VNet peerings -------------------------------------------------------------


class VirtualNetworkPeering(AzureResource):
    """Normalized entry from VirtualNetworkPeeringsOperations.list/get.

    ``peering_state`` is Azure's own peering-connection state:
    ``Initiated``, ``Connected``, or ``Disconnected`` -- a peering only
    passes traffic when both sides show ``Connected``, which this model
    surfaces directly rather than requiring a caller to infer it.
    """

    virtual_network_name: str | None = None
    remote_virtual_network_id: str | None = None
    remote_address_space: list[str] = Field(default_factory=list)
    peering_state: str | None = None
    peering_sync_level: str | None = None
    allow_virtual_network_access: bool | None = None
    allow_forwarded_traffic: bool | None = None
    allow_gateway_transit: bool | None = None
    use_remote_gateways: bool | None = None


# --- NAT gateways --------------------------------------------------------------


class NatGateway(AzureResource):
    """Normalized entry from NatGatewaysOperations.list_all/list/get."""

    sku_name: str | None = None
    idle_timeout_in_minutes: int | None = None
    public_ip_address_ids: list[str] = Field(default_factory=list)
    subnet_ids: list[str] = Field(default_factory=list)


# --- Load balancers ------------------------------------------------------------


class FrontendIpConfiguration(BaseModel):
    name: str | None = None
    private_ip_address: str | None = None
    public_ip_address_id: str | None = None
    subnet_id: str | None = None


class BackendAddressPool(BaseModel):
    name: str | None = None
    backend_ip_configuration_ids: list[str] = Field(default_factory=list)


class LoadBalancingRule(BaseModel):
    name: str | None = None
    protocol: str | None = None
    frontend_port: int | None = None
    backend_port: int | None = None
    frontend_ip_configuration_id: str | None = None
    backend_address_pool_id: str | None = None


class Probe(BaseModel):
    name: str | None = None
    protocol: str | None = None
    port: int | None = None
    request_path: str | None = None


class LoadBalancer(AzureResource):
    """Normalized entry from LoadBalancersOperations.list_all/list/get.

    ``sku_name`` distinguishes ``Basic`` from ``Standard`` (materially
    different default behaviors -- e.g. Standard requires an explicit
    NSG/outbound rule for internet access).
    """

    sku_name: str | None = None
    sku_tier: str | None = None
    frontend_ip_configurations: list[FrontendIpConfiguration] = Field(default_factory=list)
    backend_address_pools: list[BackendAddressPool] = Field(default_factory=list)
    load_balancing_rules: list[LoadBalancingRule] = Field(default_factory=list)
    probes: list[Probe] = Field(default_factory=list)


class ApplicationGatewayListener(BaseModel):
    name: str | None = None
    protocol: str | None = None
    frontend_ip_configuration_id: str | None = None
    frontend_port_id: str | None = None


class ApplicationGateway(AzureResource):
    """Normalized entry from ApplicationGatewaysOperations.list_all/list/get.

    ``operational_state`` (Running/Stopped/Starting/Stopping) is Azure's
    own runtime-health field for an Application Gateway, kept distinct
    from ``provisioning_state`` (the deployment/configuration state) per
    this milestone's "distinguish provisioning state from operational
    state" requirement -- this is the one resource type in this
    milestone's scope where Azure exposes both explicitly.
    """

    sku_name: str | None = None
    sku_tier: str | None = None
    sku_capacity: int | None = None
    operational_state: str | None = None
    listeners: list[ApplicationGatewayListener] = Field(default_factory=list)
    backend_address_pool_names: list[str] = Field(default_factory=list)


__all__ = [
    "ApplicationGateway",
    "ApplicationGatewayListener",
    "BackendAddressPool",
    "EffectiveNetworkSecurityGroup",
    "EffectiveRoute",
    "EffectiveSecurityRule",
    "FrontendIpConfiguration",
    "LoadBalancer",
    "LoadBalancingRule",
    "NatGateway",
    "NetworkInterface",
    "NetworkInterfaceIpConfiguration",
    "NetworkSecurityGroup",
    "Probe",
    "PublicIpAddress",
    "Route",
    "RouteTable",
    "SecurityRule",
    "Subnet",
    "SubnetDelegation",
    "SubnetServiceEndpoint",
    "VirtualNetwork",
    "VirtualNetworkPeering",
    "VirtualNetworkPeeringSummary",
]
