"""Unit tests for ``diagnostics.hybrid_topology.build_hybrid_topology`` --
a pure function of an already-collected ``HybridNetworkSnapshot``, tested
here via directly-constructed snapshots (no GCP client mocking)."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.connectivity_center import NccHub, NccSpoke
from gcp_network_mcp.models.networking import Network, Subnetwork
from gcp_network_mcp.models.vpn import VpnGateway, VpnTunnel

PROJECT_ID = "test-project-1"
NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
SUBNET_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "subnetworks/subnet-1"
)
VPN_GATEWAY_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "vpnGateways/vpn-gw-1"
)
VPN_TUNNEL_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "vpnTunnels/vpn-tunnel-1"
)
HUB_NAME = f"projects/{PROJECT_ID}/locations/global/hubs/hub-1"
SPOKE_NAME = f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-1"


def _empty_snapshot(**overrides: object) -> HybridNetworkSnapshot:
    return HybridNetworkSnapshot(
        project_id=PROJECT_ID, observed_at="2026-01-01T00:00:00Z", **overrides
    )


def _network() -> Network:
    return Network(
        self_link=NETWORK_SELF_LINK,
        name="vpc-1",
        project_id=PROJECT_ID,
        mode="auto",
        observed_at="2026-01-01T00:00:00Z",
    )


def _subnetwork() -> Subnetwork:
    return Subnetwork(
        self_link=SUBNET_SELF_LINK,
        name="subnet-1",
        project_id=PROJECT_ID,
        region="us-central1",
        network_self_link=NETWORK_SELF_LINK,
        ip_cidr_range="10.0.0.0/24",
        observed_at="2026-01-01T00:00:00Z",
    )


def _vpn_gateway() -> VpnGateway:
    return VpnGateway(
        self_link=VPN_GATEWAY_SELF_LINK,
        name="vpn-gw-1",
        project_id=PROJECT_ID,
        region="us-central1",
        network_self_link=NETWORK_SELF_LINK,
        observed_at="2026-01-01T00:00:00Z",
    )


def _vpn_tunnel() -> VpnTunnel:
    return VpnTunnel(
        self_link=VPN_TUNNEL_SELF_LINK,
        name="vpn-tunnel-1",
        project_id=PROJECT_ID,
        region="us-central1",
        vpn_gateway_self_link=VPN_GATEWAY_SELF_LINK,
        observed_at="2026-01-01T00:00:00Z",
    )


def _ncc_hub() -> NccHub:
    return NccHub(name=HUB_NAME, project_id=PROJECT_ID, observed_at="2026-01-01T00:00:00Z")


def _ncc_spoke(*, hub: str = HUB_NAME) -> NccSpoke:
    return NccSpoke(
        name=SPOKE_NAME,
        project_id=PROJECT_ID,
        region="us-central1",
        hub=hub,
        spoke_type="VPC_NETWORK",
        linked_resource_uris=[NETWORK_SELF_LINK],
        observed_at="2026-01-01T00:00:00Z",
    )


def test_empty_snapshot_yields_empty_complete_topology() -> None:
    topology = build_hybrid_topology(_empty_snapshot())
    assert topology.nodes == []
    assert topology.edges == []
    assert topology.warnings == []
    assert topology.completeness == "complete"
    assert topology.project_id == PROJECT_ID


def test_topology_joins_network_subnetwork_vpn_tunnel_and_ncc_hub_spoke() -> None:
    snapshot = _empty_snapshot(
        networks=[_network()],
        subnetworks=[_subnetwork()],
        vpn_gateways=[_vpn_gateway()],
        vpn_tunnels=[_vpn_tunnel()],
        ncc_hubs=[_ncc_hub()],
        ncc_spokes=[_ncc_spoke()],
    )

    topology = build_hybrid_topology(snapshot)

    assert topology.completeness == "complete"
    assert topology.warnings == []
    node_types = {n.node_type for n in topology.nodes}
    assert node_types == {
        "network",
        "subnetwork",
        "vpn_gateway",
        "vpn_tunnel",
        "ncc_hub",
        "ncc_spoke",
    }

    node_ids = {n.node_id for n in topology.nodes}
    assert NETWORK_SELF_LINK in node_ids
    assert SUBNET_SELF_LINK in node_ids
    assert VPN_GATEWAY_SELF_LINK in node_ids
    assert VPN_TUNNEL_SELF_LINK in node_ids
    assert HUB_NAME in node_ids
    assert SPOKE_NAME in node_ids

    relationships = {e.relationship for e in topology.edges}
    assert "belongs_to_network" in relationships
    assert "attached_to_network" in relationships
    assert "terminates_on_gateway" in relationships
    assert "attached_to_hub" in relationships
    assert "links_vpc_network" in relationships

    # deterministic ordering: nodes sorted by (node_type, node_id)
    assert [n.node_type for n in topology.nodes] == sorted(n.node_type for n in topology.nodes)
    assert [(e.source_id, e.target_id, e.relationship) for e in topology.edges] == sorted(
        (e.source_id, e.target_id, e.relationship) for e in topology.edges
    )


def test_out_of_scope_target_warning_when_subnetwork_references_missing_network() -> None:
    """A Subnetwork whose ``network_self_link`` isn't present in the
    snapshot's own ``networks`` list flags an ``OUT_OF_SCOPE_TARGET``
    warning and marks the topology ``partial`` -- but the edge to the
    unresolved target still exists (never silently dropped), and no
    node is fabricated for it (unlike the peering case)."""
    snapshot = _empty_snapshot(subnetworks=[_subnetwork()])  # no matching network

    topology = build_hybrid_topology(snapshot)

    assert topology.completeness == "partial"
    assert any(
        w.code == "OUT_OF_SCOPE_TARGET" and w.resource_type == "network" for w in topology.warnings
    )
    assert any(e.target_id == NETWORK_SELF_LINK for e in topology.edges)
    assert not any(n.node_id == NETWORK_SELF_LINK for n in topology.nodes)


def test_out_of_scope_target_warning_when_ncc_spoke_references_missing_hub() -> None:
    snapshot = _empty_snapshot(
        ncc_spokes=[_ncc_spoke(hub="projects/x/locations/global/hubs/ghost")]
    )

    topology = build_hybrid_topology(snapshot)

    assert topology.completeness == "partial"
    assert any(
        w.code == "OUT_OF_SCOPE_TARGET" and w.resource_type == "ncc_hub" for w in topology.warnings
    )


def test_peering_to_unresolvable_network_adds_external_node() -> None:
    """Unlike a plain missing-target reference, a peering to a network not
    present in the snapshot gets a synthetic ``external_network`` node --
    the one case in this module where a missing target still gets a node."""
    from gcp_network_mcp.models.peering import NetworkPeering

    other_network = (
        "https://www.googleapis.com/compute/v1/projects/other-proj/global/networks/vpc-x"
    )
    snapshot = _empty_snapshot(
        networks=[_network()],
        peerings=[
            NetworkPeering(
                name="peer-1",
                owning_network_self_link=NETWORK_SELF_LINK,
                network=other_network,
                state="ACTIVE",
            )
        ],
    )

    topology = build_hybrid_topology(snapshot)

    assert topology.completeness == "partial"
    external_node = next(n for n in topology.nodes if n.node_type == "external_network")
    assert external_node.node_id == other_network
    assert any(
        e.relationship == "peered_with" and e.target_id == other_network for e in topology.edges
    )


def test_preexisting_snapshot_warnings_are_carried_forward() -> None:
    """Any ``CollectionWarning`` already on the snapshot (e.g. from a
    partial ``collect_hybrid_snapshot`` collection) must survive into the
    topology's own ``warnings`` list, not be dropped in favor of only the
    topology-assembly-time ones."""
    from gcp_network_mcp.models.common import CollectionWarning

    snapshot = _empty_snapshot(
        warnings=[
            CollectionWarning(
                resource_type="ncc_hub",
                code="COLLECTION_FAILED",
                message="boom",
                project_id=PROJECT_ID,
            )
        ]
    )

    topology = build_hybrid_topology(snapshot)

    assert topology.completeness == "partial"
    assert any(w.code == "COLLECTION_FAILED" for w in topology.warnings)
