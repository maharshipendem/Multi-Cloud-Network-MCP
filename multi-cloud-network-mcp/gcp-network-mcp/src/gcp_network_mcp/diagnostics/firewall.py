"""FW-001: firewall evaluation (network-level rules + GCP's two implied
default rules) for one traffic 5-tuple.
FW-002: hierarchical Firewall Policy interaction -- GCP evaluates
hierarchical policies *before* VPC firewall rules for ingress traffic,
and *after* them for egress traffic; a hierarchical DENY/ALLOW at higher
precedence can override what FW-001 alone would conclude. This rule is
``confidence="indeterminate"`` whenever hierarchical policies weren't
supplied to the snapshot (they're org/folder-scoped, not derivable from
a project ID alone), per this milestone's guardrail against claiming
certainty with missing organization policies.
"""

from __future__ import annotations

import ipaddress

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.firewall import FirewallPolicy, FirewallRule, ProtocolPorts

EVALUATION_RULE_ID = "FW-001"
register_rule(
    rule_id=EVALUATION_RULE_ID,
    version="1.0.0",
    title="Firewall rule evaluation",
    description=(
        "Evaluates network-level firewall rules (plus GCP's two implied default rules) "
        "in priority order for one traffic 5-tuple, and reports the first rule that "
        "matches -- GCP's own first-match-wins evaluation semantics."
    ),
    default_severity="info",
)

HIERARCHICAL_INTERACTION_RULE_ID = "FW-002"
register_rule(
    rule_id=HIERARCHICAL_INTERACTION_RULE_ID,
    version="1.0.0",
    title="Hierarchical firewall policy interaction",
    description=(
        "Reports whether a hierarchical (organization/folder) Firewall Policy could "
        "override a network-level firewall verdict -- GCP evaluates hierarchical "
        "policies before VPC rules for ingress, after them for egress."
    ),
    default_severity="medium",
)


def _protocol_ports_match(entries: list[ProtocolPorts], protocol: str, port: int | None) -> bool:
    for entry in entries:
        if entry.ip_protocol.lower() not in ("all", protocol.lower()):
            continue
        if not entry.ports or port is None:
            return True
        for port_range in entry.ports:
            if "-" in port_range:
                low, high = port_range.split("-", 1)
                if int(low) <= port <= int(high):
                    return True
            elif int(port_range) == port:
                return True
    return False


def _rule_matches(
    rule: FirewallRule, *, direction: str, protocol: str, port: int | None, peer_ip: str
) -> bool:
    if rule.direction != direction:
        return False
    entries = rule.allowed if rule.action == "ALLOW" else rule.denied
    if not _protocol_ports_match(entries, protocol, port):
        return False
    ranges = rule.destination_ranges if direction == "EGRESS" else rule.source_ranges
    if not ranges:
        return True  # an empty range list matches any peer, per GCP's own semantics
    try:
        peer = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    for cidr in ranges:
        try:
            if peer in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def evaluate_firewall(
    *,
    network_self_link: str,
    firewall_rules: list[FirewallRule],
    direction: str,
    protocol: str,
    port: int | None,
    peer_ip: str,
    freshness: str,
) -> tuple[str, Finding]:
    """Return ``(verdict, Finding)`` -- ``verdict`` is ``"ALLOW"`` or
    ``"DENY"``. Rules are evaluated in ascending priority order (GCP:
    lower number = higher precedence); the first match wins, including
    GCP's own two implied default rules (priority 65535)."""
    candidates = sorted(
        (r for r in firewall_rules if r.network_self_link == network_self_link),
        key=lambda r: r.priority,
    )
    reasoning: list[ReasoningStep] = []
    evidence: list[Evidence] = []
    for step_index, rule in enumerate(candidates, start=1):
        matched = _rule_matches(
            rule, direction=direction, protocol=protocol, port=port, peer_ip=peer_ip
        )
        reasoning.append(
            ReasoningStep(
                step=step_index,
                description=(
                    f"Checked {rule.name} (priority={rule.priority}, action={rule.action}"
                    f"{', implied' if rule.is_implied else ''}) -- "
                    f"{'matched' if matched else 'no match'}."
                ),
            )
        )
        if not matched:
            continue
        evidence.append(
            Evidence(
                source=f"firewall_rule:{rule.name}",
                detail=(
                    f"priority={rule.priority}, action={rule.action}, direction={rule.direction}, "
                    f"is_implied={rule.is_implied}"
                ),
            )
        )
        return (
            rule.action,
            Finding(
                rule_id=EVALUATION_RULE_ID,
                rule_version="1.0.0",
                severity="info" if rule.action == "ALLOW" else "medium",
                confidence="high",
                summary=(
                    f"{direction} {protocol}:{port} from/to {peer_ip} on {network_self_link} "
                    f"is {rule.action}ed by {rule.name} (priority={rule.priority})."
                ),
                affected_resources=[network_self_link, rule.name],
                evidence=evidence,
                reasoning=reasoning,
                freshness=freshness,
                limitations=(
                    [
                        "This is a network-level verdict only -- see FW-002 for hierarchical "
                        "Firewall Policy interaction, which can override it."
                    ]
                ),
            ),
        )
    # No rule matched at all -- including the implied defaults, which should
    # never happen if implied_firewall_rules() were included in the snapshot,
    # but degrade honestly if they weren't.
    return (
        "indeterminate",
        Finding(
            rule_id=EVALUATION_RULE_ID,
            rule_version="1.0.0",
            severity="info",
            confidence="indeterminate",
            summary=(
                f"No firewall rule (including implied defaults) matched {direction} "
                f"{protocol}:{port} from/to {peer_ip} on {network_self_link}."
            ),
            affected_resources=[network_self_link],
            reasoning=reasoning,
            freshness=freshness,
            limitations=[
                "No implied default rule was present in the evaluated rule set -- the "
                "snapshot may not have included GCP's implied allow-egress/deny-ingress rules."
            ],
        ),
    )


def evaluate_hierarchical_interaction(
    *,
    network_self_link: str,
    hierarchical_policies: list[FirewallPolicy],
    network_level_verdict: str,
    direction: str,
    freshness: str,
) -> tuple[str | None, Finding]:
    """Return ``(overriding_verdict, Finding)``. ``overriding_verdict`` is
    ``"ALLOW"``/``"DENY"`` when a hierarchical rule overrides
    ``network_level_verdict``, else ``None`` (no applicable rule, or the
    applicable rule agrees) -- never inferred from the Finding's own
    prose summary, so callers get a clean structured signal."""
    if not hierarchical_policies:
        return (
            None,
            Finding(
                rule_id=HIERARCHICAL_INTERACTION_RULE_ID,
                rule_version="1.0.0",
                severity="medium",
                confidence="indeterminate",
                summary=(
                    "Hierarchical (organization/folder) Firewall Policies were not supplied for "
                    f"this evaluation -- whether one overrides the network-level "
                    f"{network_level_verdict} verdict for {network_self_link} could not be "
                    "determined."
                ),
                affected_resources=[network_self_link],
                freshness=freshness,
                limitations=[
                    "Hierarchical Firewall Policies are org/folder-scoped and require an "
                    "explicit parent_id -- none was supplied to this analysis."
                ],
            ),
        )

    applicable_rules = [
        rule
        for policy in hierarchical_policies
        for rule in policy.rules
        if rule.direction == direction
        and not rule.disabled
        and (network_self_link in rule.target_resources or not rule.target_resources)
    ]
    applicable_rules.sort(key=lambda r: r.priority)
    evidence = [
        Evidence(
            source=f"hierarchical_rule:{r.rule_name or r.priority}",
            detail=f"priority={r.priority}, action={r.action}",
        )
        for r in applicable_rules
    ]

    # GCP evaluation order: ingress = hierarchical policies evaluated
    # BEFORE VPC rules (so a hierarchical verdict here always wins over
    # network_level_verdict); egress = hierarchical policies evaluated
    # AFTER VPC rules (so they only matter if the network-level rule set
    # didn't already produce a terminal ALLOW/DENY -- which, given
    # implied defaults are always present, it always does; a hierarchical
    # egress rule can therefore still override even the implied default).
    if not applicable_rules:
        return (
            None,
            Finding(
                rule_id=HIERARCHICAL_INTERACTION_RULE_ID,
                rule_version="1.0.0",
                severity="info",
                confidence="high",
                summary=(
                    f"No applicable hierarchical Firewall Policy rule was found for {direction} "
                    f"traffic on {network_self_link}; the network-level {network_level_verdict} "
                    "verdict stands."
                ),
                affected_resources=[network_self_link],
                freshness=freshness,
            ),
        )

    winning_rule = applicable_rules[0]
    winning_action = winning_rule.action.upper()
    overrides = winning_action != network_level_verdict
    finding = Finding(
        rule_id=HIERARCHICAL_INTERACTION_RULE_ID,
        rule_version="1.0.0",
        severity="high" if overrides else "info",
        confidence="high",
        summary=(
            f"Hierarchical rule {winning_rule.rule_name or winning_rule.priority} "
            f"(action={winning_rule.action}) "
            + (
                f"OVERRIDES the network-level {network_level_verdict} verdict for {direction} "
                f"traffic on {network_self_link}."
                if overrides
                else f"agrees with the network-level {network_level_verdict} verdict for "
                f"{direction} traffic on {network_self_link}."
            )
        ),
        affected_resources=[network_self_link],
        evidence=evidence,
        reasoning=[
            ReasoningStep(
                step=1,
                description=(
                    f"GCP evaluates hierarchical policies "
                    f"{'before' if direction == 'INGRESS' else 'after'} VPC rules for "
                    f"{direction.lower()} traffic; the highest-precedence applicable "
                    f"hierarchical rule is {winning_rule.rule_name or winning_rule.priority} "
                    f"(priority={winning_rule.priority})."
                ),
                evidence_indices=list(range(len(evidence))),
            )
        ],
        freshness=freshness,
        remediation=(
            "Review the hierarchical policy rule's target scope if this override is unintended."
            if overrides
            else None
        ),
    )
    return (winning_action if overrides else None), finding


__all__ = [
    "EVALUATION_RULE_ID",
    "HIERARCHICAL_INTERACTION_RULE_ID",
    "evaluate_firewall",
    "evaluate_hierarchical_interaction",
]
