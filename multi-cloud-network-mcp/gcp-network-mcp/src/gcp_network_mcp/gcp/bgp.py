"""Service-layer functions for Cloud Router BGP configuration and the
read-only computed BGP status view."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import now_iso
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.gcp.routes import derive_next_hop
from gcp_network_mcp.models.bgp import (
    RouterBestRoute,
    RouterBgpPeerConfig,
    RouterBgpPeerStatus,
    RouterStatusSummary,
)


def normalize_bgp_peer_config(peer: compute_v1.RouterBgpPeer) -> RouterBgpPeerConfig:
    return RouterBgpPeerConfig(
        name=peer.name,
        interface_name=peer.interface_name or None,
        peer_asn=peer.peer_asn or None,
        peer_ip_address=peer.peer_ip_address or None,
        ip_address=peer.ip_address or None,
        enable=peer.enable or None,
        advertise_mode=peer.advertise_mode or None,
        advertised_route_priority=peer.advertised_route_priority or None,
        management_type=peer.management_type or None,
        router_appliance_instance=peer.router_appliance_instance or None,
    )


def _normalize_best_route(route: compute_v1.Route) -> RouterBestRoute:
    next_hop_type, next_hop_target = derive_next_hop(route)
    return RouterBestRoute(
        dest_range=route.dest_range or None,
        next_hop_type=next_hop_type,
        next_hop_target=next_hop_target,
        priority=route.priority or None,
        route_type=route.route_type or None,
    )


def _normalize_peer_status(status: compute_v1.RouterStatusBgpPeerStatus) -> RouterBgpPeerStatus:
    return RouterBgpPeerStatus(
        name=status.name or None,
        ip_address=status.ip_address or None,
        peer_ip_address=status.peer_ip_address or None,
        state=status.state or None,
        status=status.status or None,
        status_reason=status.status_reason or None,
        uptime=status.uptime or None,
        num_learned_routes=status.num_learned_routes or None,
        linked_vpn_tunnel=status.linked_vpn_tunnel or None,
    )


def get_router_status(
    client_factory: ClientFactory, *, project_id: str, region: str, router_name: str
) -> RouterStatusSummary:
    """The read-only computed BGP status for one router: per-peer session
    state (learned-route counts, uptime, session state) and the router's
    own best-route selections -- distinct from the router's static
    ``bgp_peers`` configuration."""
    result = call_readonly(
        client_factory.routers(),
        "get_router_status",
        project=project_id,
        region=region,
        router=router_name,
    )
    status = result.result
    router_self_link = (
        f"https://www.googleapis.com/compute/v1/projects/{project_id}/regions/"
        f"{region}/routers/{router_name}"
    )
    return RouterStatusSummary(
        router_self_link=router_self_link,
        network_self_link=status.network or None,
        bgp_peer_status=[_normalize_peer_status(p) for p in status.bgp_peer_status],
        best_routes=[_normalize_best_route(r) for r in status.best_routes],
        best_routes_for_router=[_normalize_best_route(r) for r in status.best_routes_for_router],
        observed_at=now_iso(),
    )


__all__ = ["get_router_status", "normalize_bgp_peer_config"]
