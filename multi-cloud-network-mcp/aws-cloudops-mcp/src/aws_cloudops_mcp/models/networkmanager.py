"""Normalized models for AWS Network Manager and Cloud WAN.

Both share the same ``networkmanager`` boto3 client -- Cloud WAN's core
networks are a Network Manager resource type, not a separate service.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource

# --- Cloud WAN ---------------------------------------------------------------


class CoreNetworkSegment(BaseModel):
    """A named routing domain within a core network's policy -- the
    closest Cloud WAN concept to a Transit Gateway route table, though it
    is not addressable via its own describe/route-search API the way a
    TGW route table is. Route-table summaries beyond segment/edge
    membership are not retrievable through a single read-only call."""

    name: str | None = None
    edge_locations: list[str] = Field(default_factory=list)


class CoreNetworkEdge(BaseModel):
    edge_location: str | None = None
    asn: int | None = None


class CoreNetwork(AwsResource):
    """Normalized entry from networkmanager:ListCoreNetworks, optionally
    enriched with segments/edges from networkmanager:GetCoreNetwork
    (opt-in, one extra call per core network) and a policy document from
    networkmanager:GetCoreNetworkPolicy (further opt-in, size-capped).

    ``policy_document``/``segments``/``edges`` are ``None`` unless the
    corresponding enrichment succeeded; a failure (including the API
    being entirely unavailable for this account/SDK combination) sets
    ``collection_completeness="partial"`` with a matching
    ``CollectionWarning`` rather than failing the whole tool call.
    """

    core_network_id: str
    core_network_arn: str | None = None
    global_network_id: str | None = None
    owner_account_id: str | None = None
    state: str
    description: str | None = None
    segments: list[CoreNetworkSegment] | None = None
    edges: list[CoreNetworkEdge] | None = None
    policy_document: str | None = None
    policy_document_truncated: bool = False


# --- Network Manager -----------------------------------------------------


class GlobalNetwork(AwsResource):
    """Normalized entry from networkmanager:DescribeGlobalNetworks."""

    global_network_id: str
    global_network_arn: str | None = None
    description: str | None = None
    state: str


class SiteLocation(BaseModel):
    address: str | None = None
    latitude: str | None = None
    longitude: str | None = None


class NetworkManagerSite(AwsResource):
    """Normalized entry from networkmanager:GetSites."""

    site_id: str
    global_network_id: str
    description: str | None = None
    location: SiteLocation | None = None
    state: str


class NetworkManagerDevice(AwsResource):
    """Normalized entry from networkmanager:GetDevices."""

    device_id: str
    global_network_id: str
    site_id: str | None = None
    description: str | None = None
    device_type: str | None = None
    vendor: str | None = None
    model: str | None = None
    state: str


class LinkBandwidth(BaseModel):
    upload_speed: int | None = None
    download_speed: int | None = None


class NetworkManagerLink(AwsResource):
    """Normalized entry from networkmanager:GetLinks."""

    link_id: str
    global_network_id: str
    site_id: str | None = None
    description: str | None = None
    link_type: str | None = None
    bandwidth: LinkBandwidth | None = None
    provider: str | None = None
    state: str


class NetworkManagerConnection(AwsResource):
    """Normalized entry from networkmanager:GetConnections."""

    connection_id: str
    global_network_id: str
    device_id: str | None = None
    connected_device_id: str | None = None
    link_id: str | None = None
    connected_link_id: str | None = None
    description: str | None = None
    state: str


class TransitGatewayRegistration(AwsResource):
    """Normalized entry from networkmanager:GetTransitGatewayRegistrations
    -- the link between a classic Transit Gateway and a Network Manager
    global network."""

    global_network_id: str
    transit_gateway_arn: str
    state: str
    state_message: str | None = None


__all__ = [
    "CoreNetwork",
    "CoreNetworkEdge",
    "CoreNetworkSegment",
    "GlobalNetwork",
    "LinkBandwidth",
    "NetworkManagerConnection",
    "NetworkManagerDevice",
    "NetworkManagerLink",
    "NetworkManagerSite",
    "SiteLocation",
    "TransitGatewayRegistration",
]
