"""``gcp_explain_network_path``'s orchestration: runs ROUTE-001,
FW-001, and FW-002 for one network toward one destination IP/port/
protocol, against an already-collected ``HybridNetworkSnapshot``."""

from __future__ import annotations

from pydantic import BaseModel

from gcp_network_mcp.diagnostics.firewall import (
    evaluate_firewall,
    evaluate_hierarchical_interaction,
)
from gcp_network_mcp.diagnostics.models import Finding
from gcp_network_mcp.diagnostics.routing import evaluate_route
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot


class NetworkPathExplanation(BaseModel):
    network_self_link: str
    destination_ip: str
    destination_port: int | None
    protocol: str
    route_verdict: str
    firewall_verdict: str
    overall_verdict: str
    findings: list[Finding]


def _overall_verdict(
    *, route_verdict: str, firewall_verdict: str, hierarchical_override: str | None
) -> str:
    effective_firewall_verdict = hierarchical_override or firewall_verdict
    if effective_firewall_verdict == "DENY" or route_verdict == "blocked":
        return "blocked"
    if route_verdict == "indeterminate" or effective_firewall_verdict == "indeterminate":
        return "partially_evaluated"
    return "allowed"


def explain_network_path(
    snapshot: HybridNetworkSnapshot,
    *,
    network_self_link: str,
    destination_ip: str,
    destination_port: int | None,
    protocol: str,
) -> NetworkPathExplanation:
    """Evaluate route resolution and firewall rules (network-level plus
    hierarchical policy interaction) for one network toward one
    destination. ``overall_verdict`` is ``"allowed"`` only when every
    layer independently concluded so; ``"blocked"`` if any did (a
    hierarchical DENY override takes precedence over the network-level
    firewall verdict, matching GCP's own evaluation order);
    ``"partially_evaluated"`` if any layer's evidence was incomplete --
    never silently upgraded to ``"allowed"``.
    """
    freshness = snapshot.observed_at

    route_verdict, route_finding = evaluate_route(
        network_self_link=network_self_link,
        routes=snapshot.routes,
        destination_ip=destination_ip,
        freshness=freshness,
    )

    firewall_verdict, firewall_finding = evaluate_firewall(
        network_self_link=network_self_link,
        firewall_rules=snapshot.firewall_rules,
        direction="INGRESS",
        protocol=protocol,
        port=destination_port,
        peer_ip=destination_ip,
        freshness=freshness,
    )

    hierarchical_override, hierarchical_finding = evaluate_hierarchical_interaction(
        network_self_link=network_self_link,
        hierarchical_policies=snapshot.hierarchical_firewall_policies,
        network_level_verdict=firewall_verdict,
        direction="INGRESS",
        freshness=freshness,
    )

    return NetworkPathExplanation(
        network_self_link=network_self_link,
        destination_ip=destination_ip,
        destination_port=destination_port,
        protocol=protocol,
        route_verdict=route_verdict,
        firewall_verdict=hierarchical_override or firewall_verdict,
        overall_verdict=_overall_verdict(
            route_verdict=route_verdict,
            firewall_verdict=firewall_verdict,
            hierarchical_override=hierarchical_override,
        ),
        findings=[route_finding, firewall_finding, hierarchical_finding],
    )


__all__ = ["NetworkPathExplanation", "explain_network_path"]
