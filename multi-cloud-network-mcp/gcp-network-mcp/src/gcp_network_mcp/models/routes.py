"""Normalized models for VPC Routes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource

# The GCP Route message carries the next hop as one of several mutually
# exclusive flattened fields rather than a single tagged union; this maps
# each field name to the stable next-hop-type label this server returns.
NEXT_HOP_FIELD_TYPES: dict[str, str] = {
    "next_hop_gateway": "internet_gateway",
    "next_hop_hub": "network_connectivity_hub",
    "next_hop_ilb": "internal_load_balancer",
    "next_hop_instance": "instance",
    "next_hop_interconnect_attachment": "interconnect_attachment",
    "next_hop_ip": "ip_address",
    "next_hop_network": "network_default_internet_gateway",
    "next_hop_peering": "vpc_peering",
    "next_hop_vpn_tunnel": "vpn_tunnel",
}


class Route(GcpResource):
    """Normalized entry from ``RoutesClient.list``/``get``.

    ``next_hop_type``/``next_hop_target`` are derived by
    ``gcp.routes.normalize_route`` from whichever ``next_hop_*`` field GCP
    populated -- see ``NEXT_HOP_FIELD_TYPES``.
    """

    network_self_link: str
    dest_range: str
    priority: int
    next_hop_type: str
    next_hop_target: str | None = None
    route_type: str | None = None
    route_status: str | None = None
    tags: list[str] = Field(default_factory=list)


class RouteWarning(BaseModel):
    """A GCP-reported warning attached to a specific route (e.g. an
    unreachable next hop instance)."""

    code: str
    message: str


__all__ = ["NEXT_HOP_FIELD_TYPES", "Route", "RouteWarning"]
