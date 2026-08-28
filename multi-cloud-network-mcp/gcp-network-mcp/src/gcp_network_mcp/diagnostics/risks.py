"""``gcp_find_network_risks``'s orchestration: runs every diagnostic rule
against an already-collected ``HybridNetworkSnapshot`` and returns every
finding -- including ``confidence="indeterminate"`` findings, which are
first-class output, never filtered out."""

from __future__ import annotations

from gcp_network_mcp.diagnostics import dns as dns_rules
from gcp_network_mcp.diagnostics import exposure as exposure_rules
from gcp_network_mcp.diagnostics import hybrid as hybrid_rules
from gcp_network_mcp.diagnostics import nat as nat_rules
from gcp_network_mcp.diagnostics import ncc as ncc_rules
from gcp_network_mcp.diagnostics import peering as peering_rules
from gcp_network_mcp.diagnostics import routing as routing_rules
from gcp_network_mcp.diagnostics.firewall import HIERARCHICAL_INTERACTION_RULE_ID
from gcp_network_mcp.diagnostics.models import Evidence, Finding
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot


def find_network_risks(snapshot: HybridNetworkSnapshot) -> list[Finding]:
    freshness = snapshot.observed_at
    findings: list[Finding] = []

    for network in snapshot.networks:
        network_id = network.self_link or network.name
        findings.extend(
            routing_rules.find_cidr_overlaps(
                network_self_link=network_id, routes=snapshot.routes, freshness=freshness
            )
        )

    for peering in snapshot.peerings:
        findings.append(peering_rules.evaluate_peering(peering=peering, freshness=freshness))

    for spoke in snapshot.ncc_spokes:
        finding = ncc_rules.evaluate_spoke(spoke=spoke, freshness=freshness)
        if finding is not None:
            findings.append(finding)

    for router in snapshot.routers:
        for nat in router.nats:
            finding = nat_rules.evaluate_nat(router_name=router.name, nat=nat, freshness=freshness)
            if finding is not None:
                findings.append(finding)

    for router_status in snapshot.router_statuses:
        for peer in router_status.bgp_peer_status:
            finding = hybrid_rules.evaluate_bgp_peer(
                router_self_link=router_status.router_self_link, peer=peer, freshness=freshness
            )
            if finding is not None:
                findings.append(finding)

    for tunnel in snapshot.vpn_tunnels:
        finding = hybrid_rules.evaluate_vpn_tunnel(tunnel=tunnel, freshness=freshness)
        if finding is not None:
            findings.append(finding)

    for vpn_gateway_status in snapshot.vpn_gateway_statuses:
        findings.extend(
            hybrid_rules.evaluate_vpn_gateway_status(status=vpn_gateway_status, freshness=freshness)
        )

    for interconnect in snapshot.interconnects:
        finding = hybrid_rules.evaluate_interconnect(interconnect=interconnect, freshness=freshness)
        if finding is not None:
            findings.append(finding)

    for diagnostics in snapshot.interconnect_diagnostics:
        findings.extend(
            hybrid_rules.evaluate_interconnect_diagnostics(
                diagnostics=diagnostics, freshness=freshness
            )
        )

    for zone in snapshot.dns_zones:
        findings.append(dns_rules.evaluate_zone(zone=zone, freshness=freshness))

    for rule in snapshot.forwarding_rules:
        finding = exposure_rules.evaluate_exposure(
            rule=rule, firewall_rules=snapshot.firewall_rules, freshness=freshness
        )
        if finding is not None:
            findings.append(finding)

    if snapshot.networks and not snapshot.hierarchical_firewall_policies:
        findings.append(
            Finding(
                rule_id=HIERARCHICAL_INTERACTION_RULE_ID,
                rule_version="1.0.0",
                severity="medium",
                confidence="indeterminate",
                summary=(
                    "Hierarchical (organization/folder) Firewall Policies were not supplied for "
                    "this scan -- every firewall-related finding above reflects network-level "
                    "rules only; a hierarchical policy could still override any of them."
                ),
                affected_resources=[n.self_link or n.name for n in snapshot.networks],
                evidence=[
                    Evidence(
                        source="hybrid_network_snapshot",
                        detail="hierarchical_firewall_policies is empty",
                    )
                ],
                freshness=freshness,
                limitations=[
                    "Hierarchical Firewall Policies are org/folder-scoped and require an "
                    "explicit parent_id -- none was supplied to this scan."
                ],
            )
        )

    return findings


__all__ = ["find_network_risks"]
