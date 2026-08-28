"""HYBRID-001: degraded HA VPN connections/tunnels (a tunnel not
ESTABLISHED, or HA redundancy requirement not met).
HYBRID-002: degraded Interconnect (operational status not up, or a
diagnostics link reporting degraded).
HYBRID-003: degraded BGP sessions (a peer not UP, or zero learned routes
on an otherwise-UP session -- a common symptom of a one-sided
misconfiguration).
"""

from __future__ import annotations

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.bgp import RouterBgpPeerStatus
from gcp_network_mcp.models.interconnect import Interconnect, InterconnectDiagnostics
from gcp_network_mcp.models.vpn import VpnGatewayStatus, VpnTunnel

VPN_RULE_ID = "HYBRID-001"
register_rule(
    rule_id=VPN_RULE_ID,
    version="1.0.0",
    title="Degraded HA VPN",
    description=(
        "Flags a VPN tunnel not in ESTABLISHED status, or an HA VPN connection not "
        "meeting GCP's redundancy requirement."
    ),
    default_severity="high",
)

INTERCONNECT_RULE_ID = "HYBRID-002"
register_rule(
    rule_id=INTERCONNECT_RULE_ID,
    version="1.0.0",
    title="Degraded Interconnect",
    description=(
        "Flags an Interconnect not operationally up, or a diagnostics link reporting "
        "a non-up operational status."
    ),
    default_severity="high",
)

BGP_RULE_ID = "HYBRID-003"
register_rule(
    rule_id=BGP_RULE_ID,
    version="1.0.0",
    title="Degraded BGP session",
    description=(
        "Flags a BGP peer session not UP, or a session that is UP but has learned zero routes."
    ),
    default_severity="high",
)

_HEALTHY_TUNNEL_STATUSES = {"ESTABLISHED"}
_HEALTHY_OPERATIONAL_STATUSES = {"OS_ACTIVE"}
_HEALTHY_LINK_STATUSES = {"UP"}
_HEALTHY_HA_STATES = {"CONNECTION_REDUNDANCY_MET"}


def evaluate_vpn_tunnel(*, tunnel: VpnTunnel, freshness: str) -> Finding | None:
    if not tunnel.status or tunnel.status in _HEALTHY_TUNNEL_STATUSES:
        return None
    return Finding(
        rule_id=VPN_RULE_ID,
        rule_version="1.0.0",
        severity="high",
        confidence="high",
        summary=(
            f"VPN tunnel {tunnel.name} is status={tunnel.status}"
            + (f" ({tunnel.detailed_status})" if tunnel.detailed_status else "")
            + ", not ESTABLISHED."
        ),
        affected_resources=[tunnel.name],
        evidence=[
            Evidence(
                source=f"vpn_tunnel:{tunnel.name}",
                detail=f"status={tunnel.status}, detailed_status={tunnel.detailed_status}",
            )
        ],
        reasoning=[
            ReasoningStep(
                step=1,
                description=f"tunnel.status={tunnel.status} != ESTABLISHED",
                evidence_indices=[0],
            )
        ],
        freshness=freshness,
        remediation=(
            "Check the peer gateway's configuration and detailed_status for the "
            "specific IKE/negotiation failure reason."
        ),
    )


def evaluate_vpn_gateway_status(*, status: VpnGatewayStatus, freshness: str) -> list[Finding]:
    findings: list[Finding] = []
    for connection in status.connections:
        if (
            not connection.ha_requirement_state
            or connection.ha_requirement_state in _HEALTHY_HA_STATES
        ):
            continue
        findings.append(
            Finding(
                rule_id=VPN_RULE_ID,
                rule_version="1.0.0",
                severity="high",
                confidence="high",
                summary=(
                    f"VPN gateway {status.vpn_gateway_self_link}'s connection to "
                    f"{connection.peer_gcp_gateway or connection.peer_external_gateway} "
                    "does not meet GCP's HA redundancy requirement "
                    f"(state={connection.ha_requirement_state})"
                    + (
                        f": {connection.ha_unsatisfied_reason}"
                        if connection.ha_unsatisfied_reason
                        else ""
                    )
                ),
                affected_resources=[status.vpn_gateway_self_link],
                evidence=[
                    Evidence(
                        source=f"vpn_gateway_status:{status.vpn_gateway_self_link}",
                        detail=(
                            f"ha_requirement_state={connection.ha_requirement_state}, "
                            f"reason={connection.ha_unsatisfied_reason}"
                        ),
                    )
                ],
                freshness=freshness,
                remediation=(
                    "Ensure both HA VPN gateway interfaces have an active, established "
                    "tunnel to independent peer interfaces."
                ),
            )
        )
    return findings


def evaluate_interconnect(*, interconnect: Interconnect, freshness: str) -> Finding | None:
    if (
        not interconnect.operational_status
        or interconnect.operational_status in _HEALTHY_OPERATIONAL_STATUSES
    ):
        return None
    return Finding(
        rule_id=INTERCONNECT_RULE_ID,
        rule_version="1.0.0",
        severity="critical",
        confidence="high",
        summary=(
            f"Interconnect {interconnect.name} is "
            f"operational_status={interconnect.operational_status}, not OS_ACTIVE."
        ),
        affected_resources=[interconnect.name],
        evidence=[
            Evidence(
                source=f"interconnect:{interconnect.name}",
                detail=(
                    f"operational_status={interconnect.operational_status}, "
                    f"state={interconnect.state}"
                ),
            )
        ],
        reasoning=[
            ReasoningStep(
                step=1,
                description=(
                    f"interconnect.operational_status={interconnect.operational_status} "
                    "!= OS_ACTIVE"
                ),
                evidence_indices=[0],
            )
        ],
        freshness=freshness,
        remediation=(
            "Check diagnostics for this Interconnect (get_interconnect_diagnostics) for "
            "the specific physical-link issue, or contact Google/your Partner for a "
            "Dedicated/Partner outage."
        ),
    )


def evaluate_interconnect_diagnostics(
    *, diagnostics: InterconnectDiagnostics, freshness: str
) -> list[Finding]:
    findings: list[Finding] = []
    for link in diagnostics.links:
        if not link.operational_status or link.operational_status in _HEALTHY_LINK_STATUSES:
            continue
        findings.append(
            Finding(
                rule_id=INTERCONNECT_RULE_ID,
                rule_version="1.0.0",
                severity="high",
                confidence="high",
                summary=(
                    f"Interconnect {diagnostics.interconnect_self_link} link (circuit_id="
                    f"{link.circuit_id}) is operational_status={link.operational_status}, not UP."
                ),
                affected_resources=[diagnostics.interconnect_self_link],
                evidence=[
                    Evidence(
                        source=f"interconnect_diagnostics:{diagnostics.interconnect_self_link}",
                        detail=(
                            f"circuit_id={link.circuit_id}, "
                            f"operational_status={link.operational_status}"
                        ),
                    )
                ],
                freshness=freshness,
                remediation=(
                    "Contact Google (Dedicated Interconnect) or your Partner (Partner "
                    "Interconnect) with this circuit_id."
                ),
            )
        )
    return findings


def evaluate_bgp_peer(
    *, router_self_link: str, peer: RouterBgpPeerStatus, freshness: str
) -> Finding | None:
    if not peer.state and not peer.status:
        return None
    healthy = (peer.state or "").upper() == "UP" or (peer.status or "").upper() == "UP"
    if healthy and (peer.num_learned_routes or 0) > 0:
        return None

    if not healthy:
        summary = (
            f"BGP peer {peer.name} on router {router_self_link} is not UP "
            f"(state={peer.state}, status={peer.status})"
            + (f": {peer.status_reason}" if peer.status_reason else "")
        )
        confidence = "high"
    else:
        summary = (
            f"BGP peer {peer.name} on router {router_self_link} session is up but has learned "
            "zero routes -- likely a one-sided route advertisement misconfiguration."
        )
        confidence = "medium"

    return Finding(
        rule_id=BGP_RULE_ID,
        rule_version="1.0.0",
        severity="high",
        confidence=confidence,
        summary=summary,
        affected_resources=[router_self_link, peer.name or ""],
        evidence=[
            Evidence(
                source=f"bgp_peer_status:{peer.name}",
                detail=(
                    f"state={peer.state}, status={peer.status}, "
                    f"num_learned_routes={peer.num_learned_routes}"
                ),
            )
        ],
        reasoning=[
            ReasoningStep(
                step=1,
                description="Peer session unhealthy or zero learned routes.",
                evidence_indices=[0],
            )
        ],
        freshness=freshness,
        remediation=(
            "Verify the peer device's BGP configuration and that it is actually "
            "advertising routes to this session."
        ),
    )


__all__ = [
    "BGP_RULE_ID",
    "INTERCONNECT_RULE_ID",
    "VPN_RULE_ID",
    "evaluate_bgp_peer",
    "evaluate_interconnect",
    "evaluate_interconnect_diagnostics",
    "evaluate_vpn_gateway_status",
    "evaluate_vpn_tunnel",
]
