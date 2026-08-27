"""Deterministic security evaluation: security group (stateful) and
network ACL (stateless) rule matching for a source/destination/protocol/
port tuple.

**Statefulness is the one thing that must never be conflated between
these two.** A security group only needs its rules checked in the
direction traffic is *initiated* -- AWS automatically permits the return
traffic once the initiating direction is allowed, so this module never
invents a "return path" check for security groups. A network ACL is
stateless: AWS evaluates inbound and outbound rules independently for
every packet, including the response, so a connection can be broken by a
missing *return*-direction rule even when the forward direction looks
completely open. ``evaluate_network_acls`` checks all four legs (source
outbound, destination inbound, destination outbound, source inbound) for
exactly this reason -- the "NACL ephemeral-port failure" scenario this
milestone asks to be tested is a forward-direction NACL rule that looks
correct while the return leg silently drops the response.
"""

from __future__ import annotations

import ipaddress
from typing import Literal

from aws_cloudops_mcp.diagnostics.models import (
    Confidence,
    Evidence,
    Finding,
    ReasoningStep,
    Severity,
    register_rule,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.network_resources import NetworkAclEntry, SecurityGroupRule

RULE_SECURITY_GROUP_EVALUATION = register_rule(
    rule_id="SEC-001",
    version="1.0.0",
    title="Security group evaluation",
    description=(
        "Evaluates whether a security group's egress (source) and "
        "ingress (destination) rules permit a given protocol/port between "
        "a source and destination ENI. Security groups are stateful: only "
        "the initiating direction is checked, never a synthesized return "
        "path."
    ),
    default_severity="info",
)

RULE_NETWORK_ACL_EVALUATION = register_rule(
    rule_id="SEC-002",
    version="1.0.0",
    title="Network ACL evaluation",
    description=(
        "Evaluates whether network ACLs permit a given protocol/port "
        "between a source and destination subnet, checking all four "
        "stateless legs: source outbound, destination inbound, "
        "destination outbound (return), and source inbound (return)."
    ),
    default_severity="info",
)

# A generic assumption about client-side ephemeral source ports for the
# return leg of a stateless NACL evaluation -- real values vary by OS
# (Linux commonly 32768-60999, older Windows 49152-65535); this range
# covers the full IANA ephemeral range and is always disclosed as an
# assumption on the resulting Finding, never silently baked in.
EPHEMERAL_PORT_RANGE = (1024, 65535)

Decision = Literal["allow", "deny", "indeterminate"]


def _network_of(cidr: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return None


def _ip_in_cidr(ip: str, cidr: str) -> bool:
    net = _network_of(cidr)
    if net is None:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr in net


def _protocol_matches(rule_protocol: str, protocol: str) -> bool:
    return rule_protocol in ("-1", "all") or rule_protocol.lower() == protocol.lower()


def _port_matches(from_port: int | None, to_port: int | None, port: int | None) -> bool:
    if port is None:
        return True
    if from_port is None or to_port is None:
        return True
    return from_port <= port <= to_port


def _port_range_overlaps(
    from_port: int | None, to_port: int | None, range_start: int, range_end: int
) -> bool:
    if from_port is None or to_port is None:
        return True
    return from_port <= range_end and to_port >= range_start


def _sg_rule_peer_matches(
    rule: SecurityGroupRule,
    snapshot: NetworkSnapshot,
    *,
    peer_ip: str | None,
    peer_sg_ids: set[str] | None,
) -> bool | None:
    """Whether ``rule``'s peer matches the given counterparty. Returns
    ``None`` (not True/False) when the peer type genuinely cannot be
    evaluated with the information available -- a security-group-type
    peer when the counterparty's own group memberships are unknown."""
    peer = rule.peer
    if peer.type == "ipv4" and peer_ip:
        return _ip_in_cidr(peer_ip, peer.value)
    if peer.type == "ipv6" and peer_ip:
        return _ip_in_cidr(peer_ip, peer.value)
    if peer.type == "prefix_list":
        pl = next(
            (p for p in snapshot.managed_prefix_lists if p.prefix_list_id == peer.value), None
        )
        if pl is None or pl.entries is None or peer_ip is None:
            return None
        return any(_ip_in_cidr(peer_ip, e.cidr) for e in pl.entries)
    if peer.type == "security_group":
        if peer_sg_ids is None:
            return None
        return (peer.referenced_group_id or peer.value) in peer_sg_ids
    return None


def _evaluate_sg_direction(
    snapshot: NetworkSnapshot,
    group_ids: list[str],
    *,
    is_egress: bool,
    protocol: str,
    port: int | None,
    peer_ip: str | None,
    peer_sg_ids: set[str] | None,
) -> tuple[Decision, list[Evidence], list[str]]:
    evidence: list[Evidence] = []
    limitations: list[str] = []
    saw_unresolved = False

    for group_id in group_ids:
        sg = snapshot.security_group_by_id(group_id)
        if sg is None:
            limitations.append(f"security group {group_id} was not included in this snapshot")
            continue
        for rule in sg.rules:
            if rule.is_egress != is_egress:
                continue
            if not _protocol_matches(rule.ip_protocol, protocol):
                continue
            if not _port_matches(rule.from_port, rule.to_port, port):
                continue
            match = _sg_rule_peer_matches(rule, snapshot, peer_ip=peer_ip, peer_sg_ids=peer_sg_ids)
            if match is None:
                saw_unresolved = True
                limitations.append(
                    f"rule {rule.security_group_rule_id} in {group_id} references a peer "
                    "that could not be resolved from this snapshot"
                )
                continue
            if match:
                evidence.append(
                    Evidence(
                        source=f"security_group_rule:{rule.security_group_rule_id}",
                        detail=(
                            f"{group_id} {'egress' if is_egress else 'ingress'} allows "
                            f"{rule.ip_protocol}:{rule.from_port}-{rule.to_port} to/from "
                            f"{rule.peer.type}:{rule.peer.value}"
                        ),
                    )
                )
                return "allow", evidence, limitations

    if saw_unresolved:
        return "indeterminate", evidence, limitations
    return "deny", evidence, limitations


def evaluate_security_groups(
    snapshot: NetworkSnapshot,
    *,
    source_eni_id: str,
    destination_eni_id: str | None = None,
    destination_ip: str | None = None,
    protocol: str = "tcp",
    port: int | None = None,
) -> Finding:
    """Evaluate whether security groups permit traffic from
    ``source_eni_id`` to ``destination_eni_id`` (or ``destination_ip`` if
    the destination isn't a known ENI in this snapshot).

    Only the initiating direction is checked -- security groups are
    stateful, so the return path is implicitly permitted by AWS once the
    initiating direction is allowed and is never separately evaluated
    here.
    """
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []
    limitations: list[str] = []
    assumptions: list[str] = []

    source_eni = snapshot.eni_by_id(source_eni_id)
    if source_eni is None:
        return _sg_finding(
            "indeterminate",
            "indeterminate",
            f"Source ENI {source_eni_id} was not found in the analyzed snapshot.",
            [source_eni_id],
            evidence,
            reasoning,
            [f"ENI {source_eni_id} not present in snapshot"],
            assumptions,
            snapshot.collected_at,
        )

    dest_eni = snapshot.eni_by_id(destination_eni_id) if destination_eni_id else None
    if dest_eni is None and destination_ip:
        dest_eni = next(
            (
                e
                for e in snapshot.network_interfaces
                if e.private_ip_address == destination_ip or e.public_ip == destination_ip
            ),
            None,
        )
    dest_ip_for_matching = destination_ip or (dest_eni.private_ip_address if dest_eni else None)
    dest_sg_ids = set(dest_eni.security_group_ids) if dest_eni else None

    egress_decision, egress_evidence, egress_limitations = _evaluate_sg_direction(
        snapshot,
        source_eni.security_group_ids,
        is_egress=True,
        protocol=protocol,
        port=port,
        peer_ip=dest_ip_for_matching,
        peer_sg_ids=dest_sg_ids,
    )
    evidence.extend(egress_evidence)
    limitations.extend(egress_limitations)
    reasoning.append(
        ReasoningStep(
            step=1,
            description=(
                f"Evaluated egress rules on {source_eni.security_group_ids} -> {egress_decision}."
            ),
            evidence_indices=list(range(len(evidence) - len(egress_evidence), len(evidence))),
        )
    )

    if dest_eni is None:
        limitations.append(
            "destination is not a known ENI in this snapshot; ingress-side security group "
            "evaluation was not performed"
        )
        overall: Decision = "indeterminate" if egress_decision == "allow" else egress_decision
        summary = (
            f"Egress from {source_eni_id} is {egress_decision}; ingress at the destination "
            "could not be evaluated (destination is not a known ENI)."
        )
        return _sg_finding(
            overall,
            "indeterminate" if overall == "indeterminate" else "medium",
            summary,
            [source_eni_id],
            evidence,
            reasoning,
            limitations,
            assumptions,
            snapshot.collected_at,
        )

    ingress_decision, ingress_evidence, ingress_limitations = _evaluate_sg_direction(
        snapshot,
        dest_eni.security_group_ids,
        is_egress=False,
        protocol=protocol,
        port=port,
        peer_ip=source_eni.private_ip_address,
        peer_sg_ids=set(source_eni.security_group_ids),
    )
    evidence.extend(ingress_evidence)
    limitations.extend(ingress_limitations)
    reasoning.append(
        ReasoningStep(
            step=2,
            description=(
                f"Evaluated ingress rules on {dest_eni.security_group_ids} -> {ingress_decision}."
            ),
            evidence_indices=list(range(len(evidence) - len(ingress_evidence), len(evidence))),
        )
    )

    if egress_decision == "deny" or ingress_decision == "deny":
        overall = "deny"
        confidence: Confidence = "high"
    elif egress_decision == "indeterminate" or ingress_decision == "indeterminate":
        overall = "indeterminate"
        confidence = "indeterminate"
    else:
        overall = "allow"
        confidence = "high"

    verb = (
        "permit"
        if overall == "allow"
        else "deny"
        if overall == "deny"
        else "cannot be conclusively evaluated for"
    )
    port_desc = f":{port}" if port else ""
    dest_desc = destination_eni_id or destination_ip
    summary = f"Security groups {verb} {protocol}{port_desc} from {source_eni_id} to {dest_desc}."
    return _sg_finding(
        overall,
        confidence,
        summary,
        [source_eni_id, dest_eni.network_interface_id],
        evidence,
        reasoning,
        limitations,
        assumptions,
        snapshot.collected_at,
    )


def _sg_finding(
    decision: Decision,
    confidence: Confidence,
    summary: str,
    affected: list[str],
    evidence: list[Evidence],
    reasoning: list[ReasoningStep],
    limitations: list[str],
    assumptions: list[str],
    freshness: str,
) -> Finding:
    severity: Severity = "info"
    remediation = None
    if decision == "deny":
        remediation = (
            "Add a security group rule permitting this traffic if it is expected to succeed."
        )
    return Finding(
        rule_id=RULE_SECURITY_GROUP_EVALUATION.rule_id,
        rule_version=RULE_SECURITY_GROUP_EVALUATION.version,
        severity=severity,
        confidence=confidence,
        summary=summary,
        affected_resources=affected,
        evidence=evidence,
        reasoning=reasoning,
        assumptions=assumptions,
        limitations=limitations,
        freshness=freshness,
        remediation=remediation,
    )


def _nacl_direction_decision(
    entries: list[NetworkAclEntry],
    *,
    egress: bool,
    protocol: str,
    port_start: int,
    port_end: int,
    peer_cidr_ip: str,
) -> tuple[Decision, NetworkAclEntry | None]:
    """First matching entry (in ascending rule_number order, per AWS's
    real evaluation order) wins; no match at all is an implicit deny --
    AWS's own default for a custom NACL, and the correct fallback even
    when the snapshot's default-deny entry (rule 32767) wasn't collected.
    """
    ordered = sorted((e for e in entries if e.egress == egress), key=lambda e: e.rule_number)
    for entry in ordered:
        if entry.protocol not in ("-1", "all") and entry.protocol.lower() != protocol.lower():
            continue
        if not _port_range_overlaps(
            entry.port_range_from, entry.port_range_to, port_start, port_end
        ):
            continue
        cidr = entry.cidr_block or entry.ipv6_cidr_block
        if not cidr or not _ip_in_cidr(peer_cidr_ip, cidr):
            continue
        return ("allow" if entry.rule_action == "allow" else "deny"), entry
    return "deny", None


def evaluate_network_acls(
    snapshot: NetworkSnapshot,
    *,
    source_subnet_id: str,
    source_ip: str,
    destination_subnet_id: str,
    destination_ip: str,
    protocol: str = "tcp",
    port: int,
) -> Finding:
    """Evaluate all four stateless NACL legs for one connection: source
    outbound (the request leaving), destination inbound (the request
    arriving), destination outbound (the response leaving, on an
    ephemeral source port), and source inbound (the response arriving).

    A missing rule permitting the ephemeral-port return leg on either
    side breaks the connection even when the forward-direction rules
    look completely open -- this is why all four legs are checked, not
    just the two "obvious" ones.
    """
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []
    limitations: list[str] = []
    assumptions = [
        f"Return-path (ephemeral) source ports assumed to fall within "
        f"{EPHEMERAL_PORT_RANGE[0]}-{EPHEMERAL_PORT_RANGE[1]} (the full IANA ephemeral "
        "range) -- actual client-side ephemeral ranges vary by OS."
    ]

    source_nacl = snapshot.network_acl_for_subnet(source_subnet_id)
    dest_nacl = snapshot.network_acl_for_subnet(destination_subnet_id)
    if source_nacl is None or dest_nacl is None:
        missing = source_subnet_id if source_nacl is None else destination_subnet_id
        return _nacl_finding(
            "indeterminate",
            "indeterminate",
            f"No network ACL association found for subnet {missing} in this snapshot.",
            [source_subnet_id, destination_subnet_id],
            evidence,
            reasoning,
            [f"no NACL found for subnet {missing}"],
            assumptions,
            snapshot.collected_at,
        )

    legs = [
        ("source outbound (request)", source_nacl, True, port, port, destination_ip),
        ("destination inbound (request)", dest_nacl, False, port, port, source_ip),
        (
            "destination outbound (return)",
            dest_nacl,
            True,
            EPHEMERAL_PORT_RANGE[0],
            EPHEMERAL_PORT_RANGE[1],
            source_ip,
        ),
        (
            "source inbound (return)",
            source_nacl,
            False,
            EPHEMERAL_PORT_RANGE[0],
            EPHEMERAL_PORT_RANGE[1],
            destination_ip,
        ),
    ]

    step = 1
    for label, nacl, egress, p_start, p_end, peer_ip in legs:
        decision, matched_entry = _nacl_direction_decision(
            nacl.entries,
            egress=egress,
            protocol=protocol,
            port_start=p_start,
            port_end=p_end,
            peer_cidr_ip=peer_ip,
        )
        if matched_entry is not None:
            direction_word = "to" if egress else "from"
            entry_cidr = matched_entry.cidr_block or matched_entry.ipv6_cidr_block
            evidence.append(
                Evidence(
                    source=f"network_acl_entry:{nacl.network_acl_id}#{matched_entry.rule_number}",
                    detail=(
                        f"{nacl.network_acl_id} rule {matched_entry.rule_number} "
                        f"{matched_entry.rule_action}s {matched_entry.protocol} "
                        f"{matched_entry.port_range_from}-{matched_entry.port_range_to} "
                        f"{direction_word} {entry_cidr}"
                    ),
                )
            )
        else:
            evidence.append(
                Evidence(
                    source=f"network_acl:{nacl.network_acl_id}",
                    detail=f"no {label} entry matches; implicit deny",
                )
            )
        reasoning.append(
            ReasoningStep(
                step=step,
                description=f"{label} on {nacl.network_acl_id}: {decision}.",
                evidence_indices=[len(evidence) - 1],
            )
        )
        step += 1
        if decision == "deny":
            return _nacl_finding(
                "deny",
                "high",
                f"Network ACL {nacl.network_acl_id} denies the {label} leg.",
                [nacl.network_acl_id, source_subnet_id, destination_subnet_id],
                evidence,
                reasoning,
                limitations,
                assumptions,
                snapshot.collected_at,
                remediation=(
                    f"Add an allow entry on {nacl.network_acl_id} covering the {label} leg "
                    "if this traffic is expected to succeed."
                ),
            )

    return _nacl_finding(
        "allow",
        "high",
        f"Network ACLs permit {protocol}:{port} between {source_subnet_id} and "
        f"{destination_subnet_id} in both directions, including the ephemeral-port return leg.",
        [source_nacl.network_acl_id, dest_nacl.network_acl_id],
        evidence,
        reasoning,
        limitations,
        assumptions,
        snapshot.collected_at,
    )


def _nacl_finding(
    decision: Decision,
    confidence: Confidence,
    summary: str,
    affected: list[str],
    evidence: list[Evidence],
    reasoning: list[ReasoningStep],
    limitations: list[str],
    assumptions: list[str],
    freshness: str,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        rule_id=RULE_NETWORK_ACL_EVALUATION.rule_id,
        rule_version=RULE_NETWORK_ACL_EVALUATION.version,
        severity="info",
        confidence=confidence,
        summary=summary,
        affected_resources=affected,
        evidence=evidence,
        reasoning=reasoning,
        assumptions=assumptions,
        limitations=limitations,
        freshness=freshness,
        remediation=remediation,
    )


__all__ = [
    "EPHEMERAL_PORT_RANGE",
    "evaluate_network_acls",
    "evaluate_security_groups",
]
