"""The 21 canonical resource-type models -- one per ``ResourceType`` enum
value (see ``enums.py``) -- that a future federation layer normalizes
AWS/Azure/GCP network data onto.

**How these were designed.** Every field on every model below was
decided against a verbatim, three-provider field inventory (AWS's own
Pydantic models, Azure's own Pydantic models, and GCP's own Pydantic
models from this session's ``gcp-network-mcp`` build) using one rule: a
field only becomes first-class here if at least two of the three
providers have a genuinely corresponding concept AND that concept is a
vendor-neutral fact (a CIDR, a state, a port, a protocol) rather than a
provider-specific mechanism. Everything else -- provider-specific
mechanism fields, nested structures unique to one provider, raw
provider identifiers beyond what ``urn``/``native_id`` already capture
-- belongs in the inherited ``extensions[provider_slug]`` bag at
adapter-write time, never invented as a false first-class equivalence.

**Enum-typing rule** (see ``enums.py``'s module docstring -- followed
here without exception): ``Provider`` and ``IpVersion`` are structural
enums, so fields using them are strictly enum-typed
(``provider: Provider``, ``ip_version: IpVersion``). Every other closed
vocabulary referenced below (``ResourceType``, ``RouteOrigin``,
``RouteState``, ``FirewallAction``, ``FirewallDirection``, ``Protocol``,
``ObservedState``, and this module's own informal vocabularies like
``next_hop_type``/``gateway_type``/``attached_resource_type``/
``endpoint_type``/``observability_type``) is a normalization target that
may grow in a future contract minor version, so every field carrying one
is typed as plain ``str`` -- never the enum class -- even though the
enum classes remain construction-time sugar and the documented source of
truth for "known" values.

**Redaction guarantee.** ``VpnTunnel``, ``Interconnect``, and
``InterconnectAttachment`` each carry ``redacted: bool = True`` as a
permanent, non-configurable guarantee that this contract never carries a
pre-shared key, pairing key, authorization key, or service key. None of
the three source repos this contract unifies ever read such a field into
their own models either -- there is no field here to populate even by
mistake.
"""

from __future__ import annotations

from pydantic import Field

from multicloud_network_mcp.contracts.models.common import CloudScope, ExtensibleModel, Tags
from multicloud_network_mcp.contracts.models.enums import IpVersion, Provider


class CanonicalResource(ExtensibleModel):
    """Shared spine every one of the 21 canonical resource models
    extends. Carries identity (``urn``/``native_id``/``resource_type``/
    ``provider``/``scope``), the light descriptive metadata essentially
    every provider resource has (``name``/``tags``), and collection
    provenance (``observed_at``/``source_api``/
    ``collection_completeness``). Inherits ``extensions`` from
    ``ExtensibleModel`` -- every subclass gets provider-namespaced
    overflow storage for free, without redeclaring it.

    ``resource_type`` is plain ``str`` (not the strict ``ResourceType``
    enum) per this contract's normalization-target typing rule, even
    though in practice every concrete subclass populates it with a fixed
    matching ``ResourceType.value``. ``collection_completeness`` is
    likewise plain ``str`` -- it is a per-record flag (was this one
    resource's own data fully collected, e.g. did a nested describe-call
    time out) distinct from the graph-level ``Completeness`` enum used on
    ``TopologyGraph``/``PartialResultMetadata``, so forcing it onto that
    same structural enum would conflate two different completeness
    concepts that happen to share two value names today.
    """

    urn: str
    native_id: str
    resource_type: str
    provider: Provider
    scope: CloudScope
    name: str | None = None
    tags: Tags = Field(default_factory=dict)
    observed_at: str
    source_api: str | None = None
    collection_completeness: str = "complete"


class Network(CanonicalResource):
    """Unifies AWS ``Vpc``, Azure ``VirtualNetwork``, and GCP ``Network``.

    Semantic gap: GCP networks (in both auto and custom subnet-creation
    mode) have no network-level CIDR block of their own -- address space
    exists only at the ``Subnetwork`` level, unlike AWS's
    ``Vpc.cidr_block``/``cidr_block_associations`` or Azure
    ``VirtualNetwork.address_space``. A GCP adapter populating
    ``cidr_blocks`` on this model must therefore synthesize it (e.g. by
    unioning the network's subnetworks' CIDRs) rather than reading a
    single native field -- document that synthesis at the adapter layer,
    not here.
    """

    cidr_blocks: list[str] = Field(default_factory=list)
    ipv6_cidr_blocks: list[str] = Field(default_factory=list)
    dns_servers: list[str] = Field(default_factory=list)
    mtu: int | None = None
    state: str


class Subnet(CanonicalResource):
    """Unifies AWS ``Subnet``, Azure ``Subnet``, and GCP ``Subnetwork``.

    Semantic gap: only AWS pins a subnet to a single availability zone
    (``availability_zone``). Azure subnets have no AZ concept at all, and
    GCP subnetworks are regional (spanning all zones in the region), so
    ``region_or_zone`` is deliberately generic -- an AWS adapter puts an
    AZ there, Azure/GCP put a region, and AWS's AZ-pinning detail (which
    has no Azure/GCP counterpart) stays in ``extensions["aws"]``.
    """

    cidr_block: str
    ipv6_cidr_blocks: list[str] = Field(default_factory=list)
    network_urn: str
    region_or_zone: str | None = None
    available_ip_count: int | None = None
    state: str


class NetworkInterface(CanonicalResource):
    """Unifies AWS ``NetworkInterface``, Azure ``NetworkInterface``, and
    a GCP Compute instance's embedded network interface.

    ``firewall_rule_group_urns`` is deliberately named for a *group* of
    rules, not individual ``FIREWALL_RULE`` resources: AWS security
    groups and Azure NSGs are both rule-group resources attached here,
    while GCP firewall rules attach to a network (via target tags/service
    accounts) rather than to an individual NIC -- a GCP adapter may leave
    this field empty and rely on ``FirewallRule.associated_resource_urns``
    pointing back at this interface's URN instead, which is the more
    semantically honest direction for GCP's attachment model.
    """

    subnet_urn: str | None = None
    network_urn: str | None = None
    private_ip_addresses: list[str] = Field(default_factory=list)
    mac_address: str | None = None
    associated_resource_urn: str | None = None
    firewall_rule_group_urns: list[str] = Field(default_factory=list)
    state: str


class Address(CanonicalResource):
    """Unifies Azure ``PublicIpAddress`` and GCP ``Address`` as
    first-class resources.

    Semantic gap: AWS has no first-class Elastic IP resource type in its
    own model set -- an Elastic IP only appears nested inside
    ``NatGatewayAddress``/``NetworkInterface.public_ip``. This canonical
    type still exists (Azure and GCP both warrant it as a first-class
    resource), but an AWS adapter must *synthesize* an ``Address`` record
    from those nested fields; that synthesis is an adapter-layer decision
    and is not, and cannot be, a lossless 1:1 export the way it is for
    Azure/GCP.
    """

    ip_address: str | None = None
    ip_version: IpVersion
    allocation_method: str
    associated_resource_urn: str | None = None
    is_public: bool


class RouteTable(CanonicalResource):
    """Unifies AWS ``RouteTable`` and Azure ``RouteTable``.

    Semantic gap: GCP has no route-table resource at all -- routes are
    directly project-scoped (``Route.network`` points straight at a
    ``Network``, with no intermediate table). This contract's decision:
    GCP ``ROUTE`` resources are emitted directly with their own
    ``network_urn`` and no owning ``RouteTable``; a GCP adapter either
    omits ``ROUTE_TABLE`` entirely (preferred, since synthesizing a fake
    implicit table per network would misrepresent GCP's actual model) or,
    if a consumer specifically needs one node per network for topology
    convenience, may synthesize a single implicit ``RouteTable`` per
    network -- that synthesis, if used, is documented as an adapter
    choice, not a contract requirement.

    Routes are referenced by URN (``route_urns``) rather than embedded
    inline, even though AWS/Azure's own native models both embed their
    route lists directly on the route table -- keeping ``Route`` as its
    own independently addressable canonical resource is more consistent
    with the rest of this contract's URN-referenced graph model.
    """

    network_urn: str | None = None
    subnet_association_urns: list[str] = Field(default_factory=list)
    route_urns: list[str] = Field(default_factory=list)


class Route(CanonicalResource):
    """Unifies AWS ``Route``, Azure ``Route``/``EffectiveRoute``, and GCP
    ``Route``.

    Semantic gap: GCP routes carry an explicit ``priority`` integer used
    to break ties between routes with equally specific destinations.
    AWS and Azure have no equivalent explicit-priority field -- route
    selection there is longest-prefix-match only, with no documented
    tie-break beyond implementation-defined behavior. ``priority`` is
    therefore populated for GCP and left ``None`` for AWS/Azure rather
    than defaulted to a fabricated value that would imply a tie-break
    guarantee those providers don't actually make.
    """

    destination_cidr: str | None = None
    destination_ipv6_cidr: str | None = None
    next_hop_type: str
    """Normalization-target vocabulary describing what kind of thing the
    next hop is: ``internet-gateway``, ``nat-gateway``, ``instance``,
    ``vpn-tunnel``, ``peering``, ``transit-hub``, ``interconnect``,
    ``local``, ``blackhole``, ``other``."""
    next_hop_target: str | None = None
    """A URN when the next hop resolves to a known resource, otherwise a
    raw IP/CIDR (e.g. an on-premises next-hop address)."""
    origin: str
    state: str
    priority: int | None = None


class FirewallRule(CanonicalResource):
    """Unifies AWS ``SecurityGroupRule`` *and* ``NetworkAclEntry``, Azure
    NSG ``SecurityRule``, and GCP ``Firewall`` rule -- the most
    semantically divergent canonical type in this contract.

    Semantic gap (documented deliberately, not smoothed over): AWS alone
    has *two* distinct filtering mechanisms that both map onto this one
    canonical type -- stateful Security Group rules (no explicit rule
    ordering, evaluated as a permissive union) and stateless NACL entries
    (explicitly ordered by ``rule_number``, evaluated first-match,
    allow-or-deny). Azure NSG rules and GCP firewall rules are each a
    single, stateful, priority-ordered mechanism. The ``stateful`` field
    is what actually carries this distinction: ``True`` for every AWS
    Security Group rule, every Azure NSG rule, and every GCP firewall
    rule; ``False`` only for an AWS NACL entry. A consumer must branch on
    ``stateful`` before assuming return traffic is implicitly allowed.
    GCP additionally has two *implied* default rules per network (implied
    allow-egress, implied deny-ingress) with no explicit native resource
    backing them -- an adapter emitting those must still mint a URN/
    ``native_id`` for them (a synthetic but stable one), documented as
    synthesized rather than observed.
    """

    direction: str
    action: str
    protocol: str
    port_range: str | None = None
    """A normalized ``"80"``, ``"80-443"``, or ``None`` for all ports."""
    source_ranges: list[str] = Field(default_factory=list)
    destination_ranges: list[str] = Field(default_factory=list)
    priority: int | None = None
    stateful: bool
    network_urn: str | None = None
    associated_resource_urns: list[str] = Field(default_factory=list)


class Gateway(CanonicalResource):
    """Unifies AWS ``InternetGateway``/``NatGateway``/
    ``EgressOnlyInternetGateway`` as one generic gateway type.

    Semantic gap: Azure has no exact equivalent resource -- Azure's
    internet/NAT egress behavior folds into other constructs (a
    ``NatGateway`` resource does exist on Azure but attaches directly to
    subnets rather than sitting in a route's next hop the way AWS's does;
    default internet egress otherwise requires no explicit resource at
    all). GCP is implicit-only for the default-internet-route case -- a
    GCP network's default route to the internet has no backing gateway
    resource whatsoever, only a route with ``next_hop_type ==
    "internet-gateway"`` and no resolvable ``next_hop_target`` URN. An
    adapter for either provider may therefore emit zero ``Gateway``
    resources for a given scope even when internet egress is fully
    functional -- that is not itself an omission to flag.
    """

    gateway_type: str
    """Normalization-target vocabulary: ``internet``, ``nat``,
    ``egress-only``, ``other``."""
    network_urn: str | None = None
    subnet_urn: str | None = None
    """For a NAT gateway, the subnet it is deployed in."""
    public_ip_urns: list[str] = Field(default_factory=list)
    state: str


class TransitHub(CanonicalResource):
    """Unifies AWS ``TransitGateway``, Azure ``VirtualHub``, and GCP
    Network Connectivity Center ``Hub``.

    Semantic gap: only Azure's ``VirtualHub`` carries its own address
    prefix (``cidr_blocks``). Neither an AWS Transit Gateway nor a GCP
    NCC Hub has CIDR space of its own -- both are pure routing/attachment
    fabrics with address space living entirely in the attached
    networks/spokes. ``cidr_blocks`` is therefore populated only for
    Azure and left empty for AWS/GCP, not defaulted from an attached
    network's range (which would misrepresent the hub's own identity).
    """

    asn: int | None = None
    state: str
    route_table_urns: list[str] = Field(default_factory=list)
    """A transit hub's own route table(s) -- distinct from a VPC/VNet-
    level ``RouteTable``."""
    cidr_blocks: list[str] = Field(default_factory=list)


class Attachment(CanonicalResource):
    """Unifies an AWS ``TransitGatewayAttachment``, an Azure
    ``HubVirtualNetworkConnection``, and a GCP NCC ``Spoke``.

    Semantic gap: GCP NCC spokes report a structured inactive-reason
    (e.g. why a spoke isn't propagating routes) that neither AWS transit
    gateway attachments nor Azure hub connections expose as a distinct
    field -- their state model is comparatively coarse (a handful of
    lifecycle states with no separate "why inactive" slot).
    ``state_reason`` is therefore ``None`` for the overwhelming majority
    of AWS/Azure attachments, populated mainly for GCP.
    """

    transit_hub_urn: str
    attached_resource_urn: str | None = None
    """The VPC/VNet/on-premises-connection/etc. being attached, when it
    resolves to a known resource in this collection's scope."""
    attached_resource_type: str
    """Normalization-target vocabulary: ``network``, ``vpn-tunnel``,
    ``interconnect-attachment``, ``peering``, ``other``."""
    state: str
    state_reason: str | None = None


class Peering(CanonicalResource):
    """Unifies an AWS ``VpcPeeringConnection``, an Azure
    ``VirtualNetworkPeering``, and a GCP ``NetworkPeering``.

    Semantic gap: AWS models route propagation for a peering connection
    implicitly (a peering-targeted route simply exists, or doesn't, in
    each side's own route table) with no single boolean toggle, whereas
    Azure exposes ``allow_virtual_network_access``/route-related flags
    directly on the peering resource and GCP exposes
    ``exchange_subnet_routes``/``import_custom_routes``/
    ``export_custom_routes`` directly. ``exchange_subnet_routes`` and the
    two custom-route flags are therefore ``None`` (not ``False``) for an
    AWS-sourced ``Peering`` -- there is no native AWS field to read a
    real value from, and defaulting to ``False`` would falsely assert
    route exchange is disabled when AWS's actual behavior is
    route-table-driven and not represented by any single flag at all.
    """

    local_network_urn: str
    remote_network_urn: str | None = None
    """``None`` when the peer network is in a scope this collection
    can't resolve -- pair with a topology ``UNRESOLVED`` node rather than
    silently omitting the peering."""
    remote_native_id: str | None = None
    """Populated when ``remote_network_urn`` can't be built (the peer's
    own scope/identifiers weren't collectible)."""
    state: str
    allow_forwarded_traffic: bool | None = None
    exchange_subnet_routes: bool | None = None
    import_custom_routes: bool | None = None
    export_custom_routes: bool | None = None


class VpnGateway(CanonicalResource):
    """Unifies AWS ``VpnGateway``, Azure ``VirtualNetworkGateway``/
    ``VpnGateway``, and GCP ``VpnGateway``.

    Semantic gap: ``is_ha`` normalizes GCP's explicit HA VPN (redundant,
    always-two-interface) vs. Classic VPN distinction and Azure's
    active-active gateway SKU flag onto one boolean; AWS has no directly
    corresponding concept (an AWS VPN Gateway's redundancy is inherent to
    how its VPN Connections attach, not a property of the gateway
    resource itself) -- an AWS adapter populates this as a best-effort
    inference (e.g. based on the number of attached tunnels) rather than
    a directly observed native field, and should still preserve the raw
    facts it inferred from under ``extensions["aws"]``.
    """

    network_urn: str | None = None
    asn: int | None = None
    is_ha: bool
    interface_ip_addresses: list[str] = Field(default_factory=list)
    state: str


class VpnTunnel(CanonicalResource):
    """Unifies an AWS ``VpnConnection``'s nested ``VpnTunnel``, an Azure
    ``VpnConnection``/``VirtualNetworkGatewayConnection``, and a GCP
    ``VpnTunnel``.

    ``redacted: bool = True`` is a permanent guarantee, not a toggle: no
    pre-shared key/shared-secret field exists anywhere on this model, and
    none of the three source repos this contract unifies ever reads that
    value into their own models either.

    Semantic gap: ``status`` is this contract's coarse, cross-provider
    ``ObservedState`` vocabulary (``up``/``down``/``degraded``/
    ``provisioning``/``unknown``); ``native_status`` preserves each
    provider's actual, much richer status string verbatim (GCP's
    ``ESTABLISHED``, Azure's ``Connected``, AWS's ``UP``) since the
    ``status`` mapping is lossy by design -- a consumer that needs the
    exact provider semantics reads ``native_status``, not ``status``.
    """

    gateway_urn: str
    peer_gateway_urn: str | None = None
    peer_ip: str | None = None
    status: str
    native_status: str | None = None
    bgp_enabled: bool | None = None
    bgp_asn: int | None = None
    redacted: bool = True


class Interconnect(CanonicalResource):
    """Unifies an AWS Direct Connect ``Connection``, an Azure
    ``ExpressRouteCircuit``, and a GCP ``Interconnect``.

    ``redacted: bool = True`` is a permanent guarantee: no
    authorization-key/pairing-key field exists on this model.

    Semantic gap: ``bandwidth`` is deliberately a free-text ``str``
    (e.g. ``"10Gbps"``, ``"1Gbps"``) rather than a normalized integer,
    because the three providers report it in genuinely different units
    and increments (AWS's fixed port-speed tiers, Azure's circuit
    bandwidth-in-Mbps SKU field, GCP's ``link_type``-derived capacity) and
    coercing them onto one numeric scale here would imply a precision
    and comparability across providers that the raw values don't
    actually support.
    """

    interconnect_type: str | None = None
    """``dedicated`` or ``partner``."""
    bandwidth: str | None = None
    location: str | None = None
    """The colocation facility, when reported."""
    state: str
    redacted: bool = True


class InterconnectAttachment(CanonicalResource):
    """Unifies an AWS Direct Connect ``VirtualInterface``, an Azure
    ``ExpressRouteCircuitPeering``, and a GCP ``InterconnectAttachment``.

    ``redacted: bool = True`` is a permanent guarantee, matching
    ``Interconnect``: no per-attachment secret/key field exists here.

    Semantic gap: AWS Virtual Interfaces are explicitly typed (private/
    transit/public VIF) with materially different routing behavior per
    type, while Azure ExpressRoute circuit peerings (private/Microsoft
    peering) and GCP interconnect attachments (VLAN vs. partner) each
    have their own, differently-shaped type taxonomies. This canonical
    model does not attempt a unified ``attachment_type`` field for that
    reason -- the type taxonomies don't correspond closely enough across
    providers to avoid misrepresenting one provider's semantics in
    another's vocabulary; each provider's own type string is preserved
    verbatim in ``extensions[provider]`` instead.
    """

    interconnect_urn: str
    vlan_id: int | None = None
    asn: int | None = None
    router_urn: str | None = None
    state: str
    redacted: bool = True


class DnsZone(CanonicalResource):
    """Unifies an AWS Route 53 ``HostedZone``, an Azure
    ``PrivateDnsZone``, and a GCP ``DnsZone``.

    Semantic gap: ``name_servers`` is the one fact GCP's own DNS
    diagnostic rules already depend on at full confidence (GCP always
    returns its assigned name servers for a managed zone), but AWS/Azure
    private zones frequently have no meaningful delegated name-server set
    to report (a private zone is resolved via VPC/VNet association, not
    public NS delegation) -- an AWS/Azure-sourced record may legitimately
    leave this list empty rather than that being a collection gap.
    """

    dns_name: str
    is_private: bool
    record_set_count: int | None = None
    linked_network_urns: list[str] = Field(default_factory=list)
    name_servers: list[str] = Field(default_factory=list)


class DnsResolver(CanonicalResource):
    """Unifies an AWS Route 53 Resolver ``ResolverEndpoint`` and an
    Azure DNS ``DnsResolver`` (with its Inbound/Outbound endpoints).

    Semantic gap: GCP has no equivalent resolver-endpoint resource at
    all -- Cloud DNS forwarding/peering is configured directly on a
    ``DnsZone``/policy rather than through a distinct inbound/outbound
    resolver endpoint resource. A GCP adapter therefore never emits a
    ``DnsResolver`` record; this is a structural provider gap, not a
    collection failure.
    """

    direction: str | None = None
    """``inbound`` or ``outbound``."""
    ip_addresses: list[str] = Field(default_factory=list)
    network_urn: str | None = None
    state: str


class DnsRule(CanonicalResource):
    """Unifies an AWS Route 53 Resolver ``ResolverRule`` and an Azure DNS
    ``DnsForwardingRule``.

    Semantic gap: GCP has no equivalent conditional-forwarding rule
    resource -- as with ``DnsResolver``, this is a structural gap in
    GCP's own DNS product surface (forwarding behavior lives on the zone/
    policy itself), not something a GCP adapter is expected to
    synthesize a placeholder for.
    """

    domain_name: str | None = None
    rule_type: str | None = None
    target_ips: list[str] = Field(default_factory=list)
    resolver_urn: str | None = None
    state: str


class LoadBalancer(CanonicalResource):
    """Unifies an AWS ELBv2 ``LoadBalancer``, an Azure ``LoadBalancer``/
    ``ApplicationGateway``, and GCP's forwarding-rule/backend-service
    load-balancing model.

    Semantic gap: AWS and Azure both model a load balancer as one whole
    resource with its own listeners; GCP instead models the same concept
    as a set of loosely-coupled resources at finer granularity
    (``ForwardingRule`` + ``TargetProxy`` + ``BackendService``, per
    GCP's own ``gcp_network_mcp.models.load_balancing`` shapes) with no
    single native resource matching "the load balancer" as one object. A
    GCP adapter populating this canonical type must aggregate across a
    forwarding rule and its target proxy/backend service chain into one
    synthesized ``LoadBalancer`` record -- ``listener_ports`` in
    particular is assembled from the forwarding rule's port range/ports
    rather than read from a single native field.
    """

    lb_type: str | None = None
    """Normalization-target vocabulary: ``application``, ``network``,
    ``gateway``."""
    scheme: str
    """Normalization-target vocabulary: ``internal``, ``external``."""
    ip_addresses: list[str] = Field(default_factory=list)
    network_urn: str | None = None
    listener_ports: list[int] = Field(default_factory=list)
    state: str


class Endpoint(CanonicalResource):
    """Unifies an AWS ``VpcEndpoint``, an Azure ``PrivateEndpoint``/
    ``PrivateLinkService``, and a GCP Private Service Connect
    ``ServiceAttachment``/``PscEndpoint`` pair.

    Semantic gap: ``endpoint_type`` distinguishes the consumer side
    (connecting *to* a published service -- AWS interface/gateway
    ``VpcEndpoint``, Azure ``PrivateEndpoint``, GCP ``PscEndpoint``) from
    the producer side (*publishing* a service -- Azure
    ``PrivateLinkService``, GCP ``ServiceAttachment``; AWS has no
    distinct producer-side resource of its own, VPC endpoint services are
    configured on the underlying load balancer instead). An AWS
    producer-side record is therefore synthesized by an adapter from the
    underlying ``LoadBalancer``'s endpoint-service configuration rather
    than read from a first-class AWS "endpoint service" resource, mirroring
    the same kind of best-effort synthesis already documented on
    ``Address`` for AWS.
    """

    endpoint_type: str
    """Normalization-target vocabulary: ``consumer``, ``producer``."""
    service_name: str | None = None
    network_urn: str | None = None
    subnet_urn: str | None = None
    private_ip_addresses: list[str] = Field(default_factory=list)
    state: str


class ObservabilityReference(CanonicalResource):
    """Unifies an AWS ``FlowLogConfig``, an Azure ``FlowLogConfig``/
    ``ConnectionMonitor``, and a GCP ``VpcFlowLogsConfigSummary``/
    ``PacketMirroringPolicy`` -- configuration and delivery *metadata*
    only. This model, and every conformant adapter populating it, MUST
    NEVER carry actual log record contents or packet contents/payloads --
    only the fact that a flow-log/packet-mirror/connection-monitor/
    metric-query configuration exists, whether it's enabled, and where
    its output is delivered.

    Semantic gap: ``observability_type`` spans four genuinely different
    mechanisms (flow logs, packet mirroring, connection monitoring,
    metric queries) that no single provider implements all four of --
    AWS and Azure both have flow logs and connection-monitor-like
    resources, GCP has flow logs and packet mirroring but no direct
    connection-monitor equivalent, and none of the three exposes a
    metric-query *resource* in quite the same shape a consumer would
    expect from the other two mechanisms. ``destination`` is
    deliberately free text (a log group name, a storage account, a
    Pub/Sub topic) since the delivery-target vocabulary is entirely
    provider-specific and not worth normalizing further here.
    """

    observability_type: str
    """Normalization-target vocabulary: ``flow-log``, ``packet-mirror``,
    ``connection-monitor``, ``metric-query``."""
    target_resource_urn: str | None = None
    enabled: bool | None = None
    destination: str | None = None
    """Where logs/data are delivered -- free text; provider-specific
    delivery detail beyond this stays in ``extensions``."""
    state: str | None = None


__all__ = [
    "Address",
    "Attachment",
    "CanonicalResource",
    "DnsResolver",
    "DnsRule",
    "DnsZone",
    "Endpoint",
    "FirewallRule",
    "Gateway",
    "Interconnect",
    "InterconnectAttachment",
    "LoadBalancer",
    "Network",
    "NetworkInterface",
    "ObservabilityReference",
    "Peering",
    "Route",
    "RouteTable",
    "Subnet",
    "TransitHub",
    "VpnGateway",
    "VpnTunnel",
]
