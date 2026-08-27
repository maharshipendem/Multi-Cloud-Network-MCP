"""Consistency checks that scan an entire snapshot for structural
misconfigurations, rather than answering one specific source/destination
question: CIDR overlap, orphaned Transit Gateway attachments, missing
route-table propagation, asymmetric VPC peering routes, and degraded/
failed resource states.

Each check function returns a list of :class:`Finding` (zero or more --
these report issues found, not a single pass/fail verdict), so they
compose directly into ``aws_find_network_risks``.
"""

from __future__ import annotations

import ipaddress
from itertools import combinations

from aws_cloudops_mcp.diagnostics.models import (
    Confidence,
    Evidence,
    Finding,
    ReasoningStep,
    RuleMetadata,
    Severity,
    register_rule,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot

RULE_CIDR_OVERLAP = register_rule(
    rule_id="CONSIST-001",
    version="1.0.0",
    title="CIDR overlap",
    description="Flags VPCs (or subnets within the same VPC) whose CIDR blocks overlap.",
    default_severity="high",
)

RULE_ORPHANED_TGW_ATTACHMENT = register_rule(
    rule_id="CONSIST-002",
    version="1.0.0",
    title="Orphaned Transit Gateway attachment",
    description=(
        "Flags an available Transit Gateway attachment with no route "
        "table association -- it exists but cannot send or receive "
        "traffic through the TGW."
    ),
    default_severity="medium",
)

RULE_MISSING_PROPAGATION = register_rule(
    rule_id="CONSIST-003",
    version="1.0.0",
    title="Missing Transit Gateway route propagation",
    description=(
        "Flags an associated Transit Gateway attachment with no "
        "propagation into any route table -- its routes will not appear "
        "anywhere unless added statically."
    ),
    default_severity="low",
)

RULE_ASYMMETRIC_PEERING_ROUTE = register_rule(
    rule_id="CONSIST-004",
    version="1.0.0",
    title="Asymmetric VPC peering route",
    description=(
        "Flags an active VPC peering connection where only one side's "
        "route tables have a route back through the peering connection."
    ),
    default_severity="high",
)

RULE_DEGRADED_RESOURCE_STATE = register_rule(
    rule_id="CONSIST-005",
    version="1.0.0",
    title="Degraded or failed resource state",
    description=(
        "Flags NAT gateways, Transit Gateway attachments, and VPN "
        "connections in a failed, degraded, or otherwise non-healthy "
        "state."
    ),
    default_severity="high",
)


def _finding(
    rule: RuleMetadata,
    severity: Severity,
    confidence: Confidence,
    summary: str,
    affected: list[str],
    evidence: list[Evidence],
    reasoning: list[ReasoningStep],
    freshness: str,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        severity=severity,
        confidence=confidence,
        summary=summary,
        affected_resources=affected,
        evidence=evidence,
        reasoning=reasoning,
        assumptions=[],
        limitations=[],
        freshness=freshness,
        remediation=remediation,
    )


def check_cidr_overlap(snapshot: NetworkSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    vpc_cidrs: list[tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]] = []
    for vpc in snapshot.vpcs:
        try:
            vpc_cidrs.append((vpc.vpc_id, ipaddress.ip_network(vpc.cidr_block, strict=False)))
        except ValueError:
            continue
        for assoc in vpc.cidr_block_associations:
            try:
                vpc_cidrs.append((vpc.vpc_id, ipaddress.ip_network(assoc.cidr_block, strict=False)))
            except ValueError:
                continue

    for (vpc_a, net_a), (vpc_b, net_b) in combinations(vpc_cidrs, 2):
        if vpc_a == vpc_b:
            continue
        if net_a.version != net_b.version:
            continue
        if net_a.overlaps(net_b):
            findings.append(
                _finding(
                    RULE_CIDR_OVERLAP,
                    "high",
                    "high",
                    f"VPC {vpc_a} ({net_a}) and VPC {vpc_b} ({net_b}) have overlapping CIDR "
                    "blocks.",
                    [vpc_a, vpc_b],
                    [
                        Evidence(source=f"vpc:{vpc_a}", detail=f"CidrBlock={net_a}"),
                        Evidence(source=f"vpc:{vpc_b}", detail=f"CidrBlock={net_b}"),
                    ],
                    [
                        ReasoningStep(
                            step=1,
                            description=f"{net_a} overlaps {net_b}.",
                            evidence_indices=[0, 1],
                        )
                    ],
                    snapshot.collected_at,
                    remediation=(
                        "Overlapping CIDRs prevent VPC peering and can cause ambiguous routing if "
                        "these VPCs are ever connected (peering, TGW). Re-CIDR one of them if a "
                        "future connection is planned."
                    ),
                )
            )

    subnets_by_vpc: dict[str, list[tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]]] = {}
    for subnet in snapshot.subnets:
        try:
            net = ipaddress.ip_network(subnet.cidr_block, strict=False)
        except ValueError:
            continue
        subnets_by_vpc.setdefault(subnet.vpc_id, []).append((subnet.subnet_id, net))

    for vpc_id, subnets in subnets_by_vpc.items():
        for (id_a, net_a), (id_b, net_b) in combinations(subnets, 2):
            if net_a.overlaps(net_b):
                findings.append(
                    _finding(
                        RULE_CIDR_OVERLAP,
                        "high",
                        "high",
                        f"Subnets {id_a} ({net_a}) and {id_b} ({net_b}) in VPC {vpc_id} overlap.",
                        [id_a, id_b],
                        [
                            Evidence(source=f"subnet:{id_a}", detail=f"CidrBlock={net_a}"),
                            Evidence(source=f"subnet:{id_b}", detail=f"CidrBlock={net_b}"),
                        ],
                        [
                            ReasoningStep(
                                step=1,
                                description=f"{net_a} overlaps {net_b}.",
                                evidence_indices=[0, 1],
                            )
                        ],
                        snapshot.collected_at,
                    )
                )

    return findings


def check_orphaned_tgw_attachments(snapshot: NetworkSnapshot) -> list[Finding]:
    """Available attachments with no association, and associated
    attachments with no propagation into any route table."""
    findings: list[Finding] = []
    associated_attachment_ids: set[str] = set()
    propagated_attachment_ids: set[str] = set()

    for rt in snapshot.transit_gateway_route_tables:
        for assoc in rt.associations or []:
            if assoc.transit_gateway_attachment_id and (assoc.state or "").lower() == "associated":
                associated_attachment_ids.add(assoc.transit_gateway_attachment_id)
        for prop in rt.propagations or []:
            if prop.transit_gateway_attachment_id and (prop.state or "").lower() == "enabled":
                propagated_attachment_ids.add(prop.transit_gateway_attachment_id)

    for att in snapshot.transit_gateway_attachments:
        if att.state != "available":
            continue
        att_id = att.transit_gateway_attachment_id
        if att_id not in associated_attachment_ids:
            findings.append(
                _finding(
                    RULE_ORPHANED_TGW_ATTACHMENT,
                    "medium",
                    "medium" if att.association is None else "high",
                    f"Attachment {att_id} ({att.resource_type}:{att.resource_id}) is available but "
                    "has no route table association.",
                    [att_id],
                    [
                        Evidence(
                            source=f"transit_gateway_attachment:{att_id}",
                            detail=f"State=available, association={att.association}",
                        )
                    ],
                    [
                        ReasoningStep(
                            step=1,
                            description="No association found in any collected route table.",
                            evidence_indices=[0],
                        )
                    ],
                    snapshot.collected_at,
                    remediation=(
                        f"Associate {att_id} with a Transit Gateway route table if it is "
                        "meant to pass traffic."
                    ),
                )
            )
        elif att_id not in propagated_attachment_ids:
            findings.append(
                _finding(
                    RULE_MISSING_PROPAGATION,
                    "low",
                    "medium",
                    f"Attachment {att_id} ({att.resource_type}:{att.resource_id}) is associated "
                    "but has no route propagation into any route table.",
                    [att_id],
                    [
                        Evidence(
                            source=f"transit_gateway_attachment:{att_id}",
                            detail="associated, not propagated",
                        )
                    ],
                    [
                        ReasoningStep(
                            step=1,
                            description="No propagation found in any collected route table.",
                            evidence_indices=[0],
                        )
                    ],
                    snapshot.collected_at,
                    remediation=(
                        f"Enable route propagation for {att_id}, or add static routes, if "
                        "its routes should be reachable."
                    ),
                )
            )

    return findings


def _has_active_route_to_peer(
    snapshot: NetworkSnapshot, vpc_id: str, peering_connection_id: str, peer_cidrs: list[str]
) -> bool:
    for rt in snapshot.route_tables:
        if rt.vpc_id != vpc_id:
            continue
        for route in rt.routes:
            if route.target != peering_connection_id or route.state != "active":
                continue
            dest = route.destination_cidr_block
            if dest and any(dest == c for c in peer_cidrs):
                return True
    return False


def check_asymmetric_peering_routes(snapshot: NetworkSnapshot) -> list[Finding]:
    """Scenario: peering without return route -- scanned proactively
    across every active peering connection, not just the one path a
    caller happens to ask about."""
    findings: list[Finding] = []

    for pcx in snapshot.vpc_peering_connections:
        if pcx.status_code != "active":
            continue
        req_vpc, acc_vpc = pcx.requester.vpc_id, pcx.accepter.vpc_id
        if not req_vpc or not acc_vpc:
            continue

        req_has_route = _has_active_route_to_peer(
            snapshot, req_vpc, pcx.vpc_peering_connection_id, pcx.accepter.cidr_blocks
        )
        acc_has_route = _has_active_route_to_peer(
            snapshot, acc_vpc, pcx.vpc_peering_connection_id, pcx.requester.cidr_blocks
        )

        if req_has_route and not acc_has_route:
            missing_side, present_side = acc_vpc, req_vpc
        elif acc_has_route and not req_has_route:
            missing_side, present_side = req_vpc, acc_vpc
        else:
            continue

        findings.append(
            _finding(
                RULE_ASYMMETRIC_PEERING_ROUTE,
                "high",
                "high",
                f"Peering {pcx.vpc_peering_connection_id}: {present_side} routes to the peer, but "
                f"{missing_side} has no return route -- traffic can only flow one way.",
                [pcx.vpc_peering_connection_id, req_vpc, acc_vpc],
                [
                    Evidence(
                        source=f"vpc_peering_connection:{pcx.vpc_peering_connection_id}",
                        detail=f"requester={req_vpc} accepter={acc_vpc} status=active",
                    )
                ],
                [
                    ReasoningStep(
                        step=1,
                        description=(
                            f"Route tables in {missing_side} have no active route to "
                            f"{pcx.vpc_peering_connection_id}."
                        ),
                        evidence_indices=[0],
                    )
                ],
                snapshot.collected_at,
                remediation=(
                    f"Add a route in {missing_side}'s route table(s) pointing to "
                    f"{pcx.vpc_peering_connection_id}."
                ),
            )
        )

    return findings


_DEGRADED_NAT_STATES = {"failed", "deleting", "deleted"}
_DEGRADED_TGW_ATTACHMENT_STATES = {"failed", "failing", "rejected", "rejecting", "deleting"}
_DEGRADED_VPN_TUNNEL_STATUSES = {"DOWN"}


def check_degraded_resource_states(snapshot: NetworkSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    for nat in snapshot.nat_gateways:
        if nat.state in _DEGRADED_NAT_STATES:
            findings.append(
                _finding(
                    RULE_DEGRADED_RESOURCE_STATE,
                    "high",
                    "high",
                    f"NAT gateway {nat.nat_gateway_id} is in state '{nat.state}'"
                    + (f": {nat.failure_message}" if nat.failure_message else "."),
                    [nat.nat_gateway_id],
                    [
                        Evidence(
                            source=f"nat_gateway:{nat.nat_gateway_id}",
                            detail=f"State={nat.state} FailureCode={nat.failure_code}",
                        )
                    ],
                    [
                        ReasoningStep(
                            step=1,
                            description=f"NAT gateway state is '{nat.state}'.",
                            evidence_indices=[0],
                        )
                    ],
                    snapshot.collected_at,
                    remediation=(
                        "Replace the NAT gateway; a failed NAT gateway silently drops all "
                        "egress traffic routed to it."
                    ),
                )
            )

    for att in snapshot.transit_gateway_attachments:
        if att.state in _DEGRADED_TGW_ATTACHMENT_STATES:
            findings.append(
                _finding(
                    RULE_DEGRADED_RESOURCE_STATE,
                    "high",
                    "high",
                    f"Transit Gateway attachment {att.transit_gateway_attachment_id} "
                    f"({att.resource_type}:{att.resource_id}) is in state '{att.state}'.",
                    [att.transit_gateway_attachment_id],
                    [
                        Evidence(
                            source=f"transit_gateway_attachment:{att.transit_gateway_attachment_id}",
                            detail=f"State={att.state}",
                        )
                    ],
                    [
                        ReasoningStep(
                            step=1,
                            description=f"Attachment state is '{att.state}'.",
                            evidence_indices=[0],
                        )
                    ],
                    snapshot.collected_at,
                )
            )

    for vpn in snapshot.vpn_connections:
        for tunnel in vpn.tunnels:
            if tunnel.status in _DEGRADED_VPN_TUNNEL_STATUSES:
                findings.append(
                    _finding(
                        RULE_DEGRADED_RESOURCE_STATE,
                        "medium",
                        "high",
                        f"VPN connection {vpn.vpn_connection_id} tunnel "
                        f"{tunnel.outside_ip_address} is {tunnel.status}"
                        + (f": {tunnel.status_message}" if tunnel.status_message else "."),
                        [vpn.vpn_connection_id],
                        [
                            Evidence(
                                source=f"vpn_connection:{vpn.vpn_connection_id}",
                                detail=f"tunnel {tunnel.outside_ip_address} Status={tunnel.status}",
                            )
                        ],
                        [
                            ReasoningStep(
                                step=1,
                                description=f"Tunnel status is '{tunnel.status}'.",
                                evidence_indices=[0],
                            )
                        ],
                        snapshot.collected_at,
                        remediation=(
                            "A single down tunnel is often expected (VPN connections have two "
                            "for redundancy); check whether the other tunnel is UP before "
                            "treating this as an outage."
                        ),
                    )
                )

    return findings


def run_all_consistency_checks(snapshot: NetworkSnapshot) -> list[Finding]:
    return [
        *check_cidr_overlap(snapshot),
        *check_orphaned_tgw_attachments(snapshot),
        *check_asymmetric_peering_routes(snapshot),
        *check_degraded_resource_states(snapshot),
    ]


__all__ = [
    "check_asymmetric_peering_routes",
    "check_cidr_overlap",
    "check_degraded_resource_states",
    "check_orphaned_tgw_attachments",
    "run_all_consistency_checks",
]
