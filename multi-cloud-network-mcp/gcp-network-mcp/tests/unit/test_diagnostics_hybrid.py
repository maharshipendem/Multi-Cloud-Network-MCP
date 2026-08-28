from __future__ import annotations

from gcp_network_mcp.diagnostics.hybrid import (
    evaluate_bgp_peer,
    evaluate_interconnect,
    evaluate_interconnect_diagnostics,
    evaluate_vpn_gateway_status,
    evaluate_vpn_tunnel,
)
from gcp_network_mcp.models.bgp import RouterBgpPeerStatus
from gcp_network_mcp.models.interconnect import (
    Interconnect,
    InterconnectDiagnostics,
    InterconnectDiagnosticsLinkStatus,
)
from gcp_network_mcp.models.vpn import VpnGatewayConnectionStatus, VpnGatewayStatus, VpnTunnel

FRESHNESS = "2026-08-27T00:00:00Z"
ROUTER_SELF_LINK = "https://www.googleapis.com/compute/v1/projects/p/regions/us-central1/routers/r1"


# --------------------------------------------------------------------------
# evaluate_vpn_tunnel (HYBRID-001)
# --------------------------------------------------------------------------


def _tunnel(*, status: str | None = "ESTABLISHED", detailed_status: str | None = None) -> VpnTunnel:
    return VpnTunnel(
        name="tunnel-1",
        project_id="p",
        observed_at=FRESHNESS,
        status=status,
        detailed_status=detailed_status,
    )


def test_established_tunnel_returns_none() -> None:
    assert evaluate_vpn_tunnel(tunnel=_tunnel(status="ESTABLISHED"), freshness=FRESHNESS) is None


def test_tunnel_with_no_status_returns_none() -> None:
    assert evaluate_vpn_tunnel(tunnel=_tunnel(status=None), freshness=FRESHNESS) is None


def test_non_established_tunnel_is_flagged() -> None:
    finding = evaluate_vpn_tunnel(
        tunnel=_tunnel(status="FAILED", detailed_status="IKE negotiation failed"),
        freshness=FRESHNESS,
    )
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "FAILED" in finding.summary
    assert "IKE negotiation failed" in finding.summary
    assert finding.evidence
    assert finding.remediation is not None


# --------------------------------------------------------------------------
# evaluate_vpn_gateway_status (HYBRID-001)
# --------------------------------------------------------------------------


def _gateway_status(connections: list[VpnGatewayConnectionStatus]) -> VpnGatewayStatus:
    return VpnGatewayStatus(
        vpn_gateway_self_link="https://www.googleapis.com/compute/v1/projects/p/regions/us-central1/vpnGateways/gw-1",
        connections=connections,
        observed_at=FRESHNESS,
    )


def test_ha_requirement_met_produces_no_findings() -> None:
    connections = [
        VpnGatewayConnectionStatus(
            peer_gcp_gateway="peer-gw", ha_requirement_state="CONNECTION_REDUNDANCY_MET"
        )
    ]
    findings = evaluate_vpn_gateway_status(status=_gateway_status(connections), freshness=FRESHNESS)
    assert findings == []


def test_missing_ha_requirement_state_is_skipped() -> None:
    connections = [
        VpnGatewayConnectionStatus(peer_gcp_gateway="peer-gw", ha_requirement_state=None)
    ]
    findings = evaluate_vpn_gateway_status(status=_gateway_status(connections), freshness=FRESHNESS)
    assert findings == []


def test_ha_requirement_unmet_is_flagged() -> None:
    connections = [
        VpnGatewayConnectionStatus(
            peer_gcp_gateway="peer-gw",
            ha_requirement_state="CONNECTION_REDUNDANCY_NOT_MET",
            ha_unsatisfied_reason="only one tunnel is established",
        )
    ]
    findings = evaluate_vpn_gateway_status(status=_gateway_status(connections), freshness=FRESHNESS)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "only one tunnel is established" in finding.summary
    assert finding.evidence


def test_multiple_connections_each_evaluated_independently() -> None:
    connections = [
        VpnGatewayConnectionStatus(
            peer_gcp_gateway="ok-peer", ha_requirement_state="CONNECTION_REDUNDANCY_MET"
        ),
        VpnGatewayConnectionStatus(
            peer_gcp_gateway="bad-peer", ha_requirement_state="CONNECTION_REDUNDANCY_NOT_MET"
        ),
    ]
    findings = evaluate_vpn_gateway_status(status=_gateway_status(connections), freshness=FRESHNESS)
    assert len(findings) == 1
    assert "bad-peer" in findings[0].summary


# --------------------------------------------------------------------------
# evaluate_interconnect (HYBRID-002)
# --------------------------------------------------------------------------


def _interconnect(
    *, operational_status: str | None = "OS_ACTIVE", state: str | None = "ACTIVE"
) -> Interconnect:
    return Interconnect(
        name="ic-1",
        project_id="p",
        observed_at=FRESHNESS,
        operational_status=operational_status,
        state=state,
    )


def test_active_interconnect_returns_none() -> None:
    assert evaluate_interconnect(interconnect=_interconnect(), freshness=FRESHNESS) is None


def test_interconnect_with_no_operational_status_returns_none() -> None:
    ic = _interconnect(operational_status=None)
    assert evaluate_interconnect(interconnect=ic, freshness=FRESHNESS) is None


def test_non_active_interconnect_is_critical() -> None:
    ic = _interconnect(operational_status="OS_UNPROVISIONED", state="UNPROVISIONED")
    finding = evaluate_interconnect(interconnect=ic, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "critical"
    assert finding.confidence == "high"
    assert finding.evidence
    assert finding.remediation is not None


# --------------------------------------------------------------------------
# evaluate_interconnect_diagnostics (HYBRID-002)
# --------------------------------------------------------------------------


def _diagnostics(links: list[InterconnectDiagnosticsLinkStatus]) -> InterconnectDiagnostics:
    return InterconnectDiagnostics(
        interconnect_self_link="https://www.googleapis.com/compute/v1/projects/p/global/interconnects/ic-1",
        links=links,
        observed_at=FRESHNESS,
    )


def test_all_links_up_produces_no_findings() -> None:
    links = [InterconnectDiagnosticsLinkStatus(circuit_id="c1", operational_status="UP")]
    findings = evaluate_interconnect_diagnostics(
        diagnostics=_diagnostics(links), freshness=FRESHNESS
    )
    assert findings == []


def test_missing_link_status_is_skipped() -> None:
    links = [InterconnectDiagnosticsLinkStatus(circuit_id="c1", operational_status=None)]
    findings = evaluate_interconnect_diagnostics(
        diagnostics=_diagnostics(links), freshness=FRESHNESS
    )
    assert findings == []


def test_down_link_is_flagged() -> None:
    links = [InterconnectDiagnosticsLinkStatus(circuit_id="c1", operational_status="DOWN")]
    findings = evaluate_interconnect_diagnostics(
        diagnostics=_diagnostics(links), freshness=FRESHNESS
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "c1" in finding.summary
    assert finding.evidence


# --------------------------------------------------------------------------
# evaluate_bgp_peer (HYBRID-003)
# --------------------------------------------------------------------------


def _peer(
    *,
    state: str | None = "UP",
    status: str | None = None,
    num_learned_routes: int | None = 5,
    status_reason: str | None = None,
) -> RouterBgpPeerStatus:
    return RouterBgpPeerStatus(
        name="peer-1",
        state=state,
        status=status,
        status_reason=status_reason,
        num_learned_routes=num_learned_routes,
    )


def test_no_state_and_no_status_returns_none() -> None:
    peer = _peer(state=None, status=None, num_learned_routes=None)
    assert (
        evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS) is None
    )


def test_up_with_learned_routes_returns_none() -> None:
    peer = _peer(state="UP", num_learned_routes=5)
    assert (
        evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS) is None
    )


def test_peer_not_up_is_flagged_with_high_confidence() -> None:
    peer = _peer(state="DOWN", status_reason="peer unreachable")
    finding = evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "not UP" in finding.summary
    assert "peer unreachable" in finding.summary
    assert finding.evidence


def test_up_but_zero_learned_routes_is_flagged_with_reduced_confidence() -> None:
    peer = _peer(state="UP", num_learned_routes=0)
    finding = evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence == "medium"
    assert "learned zero routes" in finding.summary
    assert finding.evidence


def test_up_with_null_learned_routes_count_is_treated_as_zero() -> None:
    peer = _peer(state="UP", num_learned_routes=None)
    finding = evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS)
    assert finding is not None
    assert finding.confidence == "medium"


def test_down_and_zero_routes_cases_have_matching_severity_but_different_confidence() -> None:
    """Both distinct triggers for BGP-001 report the same severity ('high')
    -- what distinguishes a confirmed session failure from the milder
    'session is up but suspiciously quiet' case is confidence, not
    severity."""
    down = evaluate_bgp_peer(
        router_self_link=ROUTER_SELF_LINK, peer=_peer(state="DOWN"), freshness=FRESHNESS
    )
    quiet = evaluate_bgp_peer(
        router_self_link=ROUTER_SELF_LINK,
        peer=_peer(state="UP", num_learned_routes=0),
        freshness=FRESHNESS,
    )
    assert down is not None
    assert quiet is not None
    assert down.severity == quiet.severity == "high"
    assert down.confidence != quiet.confidence
    assert down.confidence == "high"
    assert quiet.confidence == "medium"


def test_status_field_alone_can_indicate_healthy() -> None:
    """healthy is state==UP OR status==UP -- exercise the status-only path."""
    peer = _peer(state=None, status="UP", num_learned_routes=3)
    assert (
        evaluate_bgp_peer(router_self_link=ROUTER_SELF_LINK, peer=peer, freshness=FRESHNESS) is None
    )
