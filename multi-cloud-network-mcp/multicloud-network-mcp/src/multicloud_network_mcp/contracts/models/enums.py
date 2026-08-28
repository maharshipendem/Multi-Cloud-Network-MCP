"""Closed vocabularies shared by every model in this contract.

Every value here is a Python ``StrEnum``, but **not every model field
that uses one of these vocabularies is typed as the enum itself.**
Two categories, deliberately handled differently:

- **Structural enums** (``Provider``, ``NodeKind``, ``Completeness``,
  ``IpVersion``): fixed by this contract's own grammar, not by what any
  provider does -- there will always be exactly three ``NodeKind``
  values by design, not because AWS/Azure/GCP happen to agree on three.
  Fields using these ARE typed as the strict enum: an unrecognized value
  here signals a genuine structural incompatibility (a major-version
  change), not a forward-compatible extension.
- **Normalization-target enums** (everything else: ``ResourceType``,
  ``RouteOrigin``, ``RouteState``, ``FirewallAction``,
  ``FirewallDirection``, ``Protocol``, ``ObservedState``, ``Severity``,
  ``Confidence``, ``PathVerdict``): the categories THIS contract maps
  provider-native values onto, which may grow in a future minor version
  (a new resource type, a new confidence tier). Model fields using these
  are typed as plain ``str`` (not the enum class) specifically so an
  older consumer parsing data produced under a newer contract minor
  doesn't hard-fail on a value it doesn't recognize yet -- both at the
  Pydantic layer (no strict enum validation) and at the JSON Schema
  layer (``type: string`` with no ``enum`` constraint, only a
  documented recommended value set) -- see
  ``tests/contracts/test_unknown_enum_forward_compat.py`` and
  ``docs/versioning.md``. The enum classes below remain the single
  source of truth for what "known" values are, for construction
  convenience (a ``StrEnum`` member IS a ``str``, so
  ``Route(origin=RouteOrigin.STATIC, ...)`` still works against a
  ``str``-typed field) and for generating each schema's documented
  value list.
"""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class ResourceType(StrEnum):
    """The canonical, kebab-case resource-type vocabulary every URN's
    ``<resource-type>`` field and every ``TopologyNode.kind``/
    ``Finding.affected_resources`` entry draws from. See
    ``docs/normalization.md`` for the full per-provider mapping table
    (e.g. AWS Security Group Rule / Azure NSG Security Rule / GCP
    Firewall Rule all map to ``FIREWALL_RULE``)."""

    NETWORK = "network"
    SUBNET = "subnet"
    NETWORK_INTERFACE = "network-interface"
    ADDRESS = "address"
    ROUTE_TABLE = "route-table"
    ROUTE = "route"
    FIREWALL_RULE = "firewall-rule"
    GATEWAY = "gateway"
    TRANSIT_HUB = "transit-hub"
    ATTACHMENT = "attachment"
    PEERING = "peering"
    VPN_GATEWAY = "vpn-gateway"
    VPN_TUNNEL = "vpn-tunnel"
    INTERCONNECT = "interconnect"
    INTERCONNECT_ATTACHMENT = "interconnect-attachment"
    DNS_ZONE = "dns-zone"
    DNS_RESOLVER = "dns-resolver"
    DNS_RULE = "dns-rule"
    LOAD_BALANCER = "load-balancer"
    ENDPOINT = "endpoint"
    OBSERVABILITY_REFERENCE = "observability-reference"


class NodeKind(StrEnum):
    """A topology node's resolution state. Formalizes what every cloud
    repo today represents only informally (AWS: an ``external_endpoint``
    node-type string plus an undeclared "orphan edge" convention; Azure:
    a free-form ``node_type`` string plus a ``CollectionWarning``; GCP: a
    dedicated ``OUT_OF_SCOPE_TARGET`` warning code with no node at all)
    into one explicit, schema-enforced field."""

    RESOURCE = "resource"
    """A real, in-scope resource this provider's own collector observed
    directly -- ``native_id``/``urn`` both resolve to something the
    collecting call actually returned."""

    EXTERNAL = "external"
    """A genuinely non-cloud (or definitively out-of-provider) endpoint
    the graph can name but never further resolve -- an on-premises
    device's public IP terminating a VPN tunnel, a static route's
    destination network. Present on purpose so the boundary is visible,
    not merely dropped."""

    UNRESOLVED = "unresolved"
    """An in-scope-domain reference this particular collection couldn't
    resolve to a node -- a cross-account peer resource, a resource
    outside the collected scope/region, or one hidden by a permission
    gap. Always paired with a ``CollectionWarning`` explaining why."""


class RouteOrigin(StrEnum):
    """Normalizes AWS ``Route.origin`` (``CreateRouteTable``/
    ``CreateRoute``/``EnableVgwRoutePropagation``), Azure
    ``EffectiveRoute.source`` (``Default``/``User``/
    ``VirtualNetworkGateway``), and GCP's absence of an explicit origin
    field (inferred from route type) into one vocabulary."""

    SYSTEM = "system"
    """Auto-created by the platform (a VPC's default local route, a
    subnet's implicit default)."""

    STATIC = "static"
    """User-created static/custom route."""

    DYNAMIC = "dynamic"
    """Learned dynamically (BGP propagation from a VPN/Interconnect/
    Direct Connect/ExpressRoute/Transit Gateway/vWAN Hub peer)."""

    UNKNOWN = "unknown"


class RouteState(StrEnum):
    """Normalizes AWS ``Route.state`` (``active``/``blackhole``), Azure
    ``EffectiveRoute.state`` (``Active``/``Invalid``), and GCP's absence
    of a per-route state field (a GCP route with no valid next hop is
    represented as ``BLACKHOLE`` by the adapter, inferred rather than
    observed -- see ``docs/normalization.md``)."""

    ACTIVE = "active"
    BLACKHOLE = "blackhole"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class FirewallAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class FirewallDirection(StrEnum):
    INGRESS = "ingress"
    EGRESS = "egress"


class IpVersion(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class Protocol(StrEnum):
    """A closed set of the protocol keywords that actually appear across
    AWS/Azure/GCP firewall and route models. ``ALL`` normalizes AWS's
    ``"-1"``, Azure's ``"*"``, and GCP's ``"all"``. An IANA protocol
    number with no keyword in this set (e.g. a raw ``50`` for ESP that a
    provider returned as a bare number) is preserved verbatim in
    ``extensions["native_protocol"]`` rather than forced into ``OTHER``
    silently -- see ``normalization/protocol.py``."""

    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ICMPV6 = "icmpv6"
    ESP = "esp"
    AH = "ah"
    GRE = "gre"
    ALL = "all"
    OTHER = "other"


class ObservedState(StrEnum):
    """A coarse, cross-provider operational-state vocabulary for
    gateways/tunnels/attachments/interconnects -- every provider's own
    much richer state string (GCP's ``ESTABLISHED``, Azure's
    ``Connected``, AWS's ``UP``) is preserved verbatim in
    ``native_state``; this field is the adapter's best-effort mapping of
    that string onto one shared axis for a consumer that just wants
    "is this healthy" without knowing all three providers' vocabularies."""

    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    PROVISIONING = "provisioning"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(StrEnum):
    """Carries an explicit ``INDETERMINATE`` value -- a finding that
    cannot reach a conclusion because required evidence is missing must
    say so, never silently omit itself. Identical across all three cloud
    repos' own diagnostics engines already; this contract's
    ``Finding`` model is the canonical version they converge to."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INDETERMINATE = "indeterminate"


class PathVerdict(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PARTIALLY_EVALUATED = "partially_evaluated"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


__all__ = [
    "Completeness",
    "Confidence",
    "FirewallAction",
    "FirewallDirection",
    "IpVersion",
    "NodeKind",
    "ObservedState",
    "PathVerdict",
    "Protocol",
    "Provider",
    "ResourceType",
    "RouteOrigin",
    "RouteState",
    "Severity",
]
