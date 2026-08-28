from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID

from gcp_network_mcp.gcp.bgp import get_router_status, normalize_bgp_peer_config

_ROUTER_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
    "us-central1/routers/router-1"
)


def test_normalize_bgp_peer_config_full_fields() -> None:
    peer = compute_v1.RouterBgpPeer(
        name="peer-1",
        interface_name="if-1",
        peer_asn=65001,
        peer_ip_address="169.254.0.1",
        ip_address="169.254.0.2",
        enable="TRUE",
        advertise_mode="CUSTOM",
        advertised_route_priority=100,
        management_type="MANAGED_BY_USER",
        router_appliance_instance="https://www.googleapis.com/compute/v1/projects/p/zones/z/instances/i",
    )
    normalized = normalize_bgp_peer_config(peer)

    assert normalized.name == "peer-1"
    assert normalized.interface_name == "if-1"
    assert normalized.peer_asn == 65001
    assert normalized.peer_ip_address == "169.254.0.1"
    assert normalized.ip_address == "169.254.0.2"
    assert normalized.enable == "TRUE"
    assert normalized.advertise_mode == "CUSTOM"
    assert normalized.advertised_route_priority == 100
    assert normalized.management_type == "MANAGED_BY_USER"
    assert normalized.router_appliance_instance == (
        "https://www.googleapis.com/compute/v1/projects/p/zones/z/instances/i"
    )


def test_normalize_bgp_peer_config_only_required_name_set() -> None:
    """Only ``name`` is a required field on ``RouterBgpPeerConfig`` --
    every other field must fall back to ``None`` rather than an
    empty-string/zero sentinel when the peer leaves it unset."""
    peer = compute_v1.RouterBgpPeer(name="peer-2")
    normalized = normalize_bgp_peer_config(peer)

    assert normalized.name == "peer-2"
    assert normalized.interface_name is None
    assert normalized.peer_asn is None
    assert normalized.peer_ip_address is None
    assert normalized.ip_address is None
    assert normalized.enable is None
    assert normalized.advertise_mode is None
    assert normalized.advertised_route_priority is None
    assert normalized.management_type is None
    assert normalized.router_appliance_instance is None


def test_get_router_status_builds_self_link_and_normalizes_peers_and_routes(
    client_factory,
) -> None:
    raw_response = compute_v1.RouterStatusResponse(
        result=compute_v1.RouterStatus(
            network=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
            ),
            bgp_peer_status=[
                compute_v1.RouterStatusBgpPeerStatus(
                    name="peer-1",
                    ip_address="169.254.0.2",
                    peer_ip_address="169.254.0.1",
                    state="Established",
                    status="UP",
                    status_reason="",
                    uptime="2d10h",
                    num_learned_routes=5,
                    linked_vpn_tunnel=(
                        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
                        "us-central1/vpnTunnels/tunnel-1"
                    ),
                )
            ],
            best_routes=[
                compute_v1.Route(
                    dest_range="10.0.0.0/24",
                    next_hop_ip="169.254.0.1",
                    priority=100,
                    route_type="BGP",
                )
            ],
            best_routes_for_router=[
                compute_v1.Route(
                    dest_range="10.1.0.0/24",
                    next_hop_vpn_tunnel=(
                        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
                        "us-central1/vpnTunnels/tunnel-1"
                    ),
                    priority=50,
                    route_type="BGP",
                )
            ],
        )
    )
    client_factory.routers().get_router_status.return_value = raw_response

    status = get_router_status(
        client_factory, project_id=PROJECT_ID, region="us-central1", router_name="router-1"
    )

    assert status.router_self_link == _ROUTER_SELF_LINK
    assert status.network_self_link == (
        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
    )

    assert len(status.bgp_peer_status) == 1
    peer_status = status.bgp_peer_status[0]
    assert peer_status.name == "peer-1"
    assert peer_status.state == "Established"
    assert peer_status.status == "UP"
    assert peer_status.num_learned_routes == 5
    assert peer_status.uptime == "2d10h"
    assert peer_status.linked_vpn_tunnel is not None

    assert len(status.best_routes) == 1
    assert status.best_routes[0].dest_range == "10.0.0.0/24"
    assert status.best_routes[0].next_hop_type == "ip_address"
    assert status.best_routes[0].next_hop_target == "169.254.0.1"
    assert status.best_routes[0].priority == 100

    assert len(status.best_routes_for_router) == 1
    assert status.best_routes_for_router[0].dest_range == "10.1.0.0/24"
    assert status.best_routes_for_router[0].next_hop_type == "vpn_tunnel"
    assert status.best_routes_for_router[0].priority == 50

    assert status.observed_at


def test_get_router_status_empty_peers_and_routes(client_factory) -> None:
    raw_response = compute_v1.RouterStatusResponse(result=compute_v1.RouterStatus())
    client_factory.routers().get_router_status.return_value = raw_response

    status = get_router_status(
        client_factory, project_id=PROJECT_ID, region="us-central1", router_name="router-1"
    )

    assert status.router_self_link == _ROUTER_SELF_LINK
    assert status.network_self_link is None
    assert status.bgp_peer_status == []
    assert status.best_routes == []
    assert status.best_routes_for_router == []
