"""The canonical, versioned public API surface of this contract's typed
models. Every model a consumer should import is re-exported here --
`from multicloud_network_mcp.contracts.models import Network, Finding,
TopologyGraph` -- rather than requiring a submodule-path import.

This fills a gap all three cloud repos' own `models/__init__.py` share
today (confirmed empty/docstring-only in each, per this milestone's own
research): none of them declares a single stable top-level public API
list, only per-submodule `__all__`. This package's `__init__.py`
intentionally does declare one, since a versioned cross-cloud contract
needs a place where "this is the whole public surface, and a Milestone
9-onward diff of this file's `__all__` tells you exactly what changed."
"""

from __future__ import annotations

from multicloud_network_mcp.contracts.models.capability import (
    NegotiationResult,
    ProviderCapabilityManifest,
    ResourceTypeSupport,
    negotiate,
)
from multicloud_network_mcp.contracts.models.common import (
    CloudScope,
    ExtensibleModel,
    Ownership,
    SourceEvidence,
    Tags,
)
from multicloud_network_mcp.contracts.models.diagnostics import (
    Finding,
    PathExplanation,
    ReasoningStep,
)
from multicloud_network_mcp.contracts.models.enums import (
    Completeness,
    Confidence,
    FirewallAction,
    FirewallDirection,
    IpVersion,
    NodeKind,
    ObservedState,
    PathVerdict,
    Protocol,
    Provider,
    ResourceType,
    RouteOrigin,
    RouteState,
    Severity,
)
from multicloud_network_mcp.contracts.models.envelope import (
    CollectionWarning,
    ErrorDetail,
    PaginationMetadata,
    PartialResultMetadata,
    ResponseEnvelope,
)
from multicloud_network_mcp.contracts.models.resources import (
    Address,
    Attachment,
    CanonicalResource,
    DnsResolver,
    DnsRule,
    DnsZone,
    Endpoint,
    FirewallRule,
    Gateway,
    Interconnect,
    InterconnectAttachment,
    LoadBalancer,
    Network,
    NetworkInterface,
    ObservabilityReference,
    Peering,
    Route,
    RouteTable,
    Subnet,
    TransitHub,
    VpnGateway,
    VpnTunnel,
)
from multicloud_network_mcp.contracts.models.topology import (
    TopologyEdge,
    TopologyGraph,
    TopologyNode,
)

__all__ = [
    "Address",
    "Attachment",
    "CanonicalResource",
    "CloudScope",
    "CollectionWarning",
    "Completeness",
    "Confidence",
    "DnsResolver",
    "DnsRule",
    "DnsZone",
    "Endpoint",
    "ErrorDetail",
    "ExtensibleModel",
    "Finding",
    "FirewallAction",
    "FirewallDirection",
    "FirewallRule",
    "Gateway",
    "Interconnect",
    "InterconnectAttachment",
    "IpVersion",
    "LoadBalancer",
    "NegotiationResult",
    "Network",
    "NetworkInterface",
    "NodeKind",
    "ObservabilityReference",
    "ObservedState",
    "Ownership",
    "PaginationMetadata",
    "PartialResultMetadata",
    "PathExplanation",
    "PathVerdict",
    "Peering",
    "Protocol",
    "Provider",
    "ProviderCapabilityManifest",
    "ReasoningStep",
    "ResourceType",
    "ResourceTypeSupport",
    "ResponseEnvelope",
    "Route",
    "RouteOrigin",
    "RouteState",
    "RouteTable",
    "Severity",
    "SourceEvidence",
    "Subnet",
    "Tags",
    "TopologyEdge",
    "TopologyGraph",
    "TopologyNode",
    "TransitHub",
    "VpnGateway",
    "VpnTunnel",
    "negotiate",
]
