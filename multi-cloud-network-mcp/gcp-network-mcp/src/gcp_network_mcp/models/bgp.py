"""Normalized models for Cloud Router BGP configuration and status --
BGP peers (static configuration, from ``Router.bgp_peers``) and the
read-only computed status view (``RoutersClient.get_router_status``):
per-peer session state, learned-route counts, and the router's own
best-route selections."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RouterBgpPeerConfig(BaseModel):
    """One statically-configured BGP peer, from ``Router.bgp_peers``."""

    name: str
    interface_name: str | None = None
    peer_asn: int | None = None
    peer_ip_address: str | None = None
    ip_address: str | None = None
    enable: str | None = None
    advertise_mode: str | None = None
    advertised_route_priority: int | None = None
    management_type: str | None = None
    router_appliance_instance: str | None = None


class RouterBestRoute(BaseModel):
    """One entry from ``RouterStatus.best_routes``/``best_routes_for_router``
    -- the router's own best-path selection, not this server's inference."""

    dest_range: str | None = None
    next_hop_type: str | None = None
    next_hop_target: str | None = None
    priority: int | None = None
    route_type: str | None = None


class RouterBgpPeerStatus(BaseModel):
    """One entry from ``RouterStatus.bgp_peer_status`` -- the read-only
    computed session-state view for one BGP peer."""

    name: str | None = None
    ip_address: str | None = None
    peer_ip_address: str | None = None
    state: str | None = None
    status: str | None = None
    status_reason: str | None = None
    uptime: str | None = None
    num_learned_routes: int | None = None
    linked_vpn_tunnel: str | None = None


class RouterStatusSummary(BaseModel):
    """From ``RoutersClient.get_router_status`` -- the router's full
    computed BGP status: best routes plus per-peer session state."""

    router_self_link: str
    network_self_link: str | None = None
    bgp_peer_status: list[RouterBgpPeerStatus] = Field(default_factory=list)
    best_routes: list[RouterBestRoute] = Field(default_factory=list)
    best_routes_for_router: list[RouterBestRoute] = Field(default_factory=list)
    observed_at: str
    source_api: str = "RoutersClient.get_router_status"


__all__ = [
    "RouterBestRoute",
    "RouterBgpPeerConfig",
    "RouterBgpPeerStatus",
    "RouterStatusSummary",
]
