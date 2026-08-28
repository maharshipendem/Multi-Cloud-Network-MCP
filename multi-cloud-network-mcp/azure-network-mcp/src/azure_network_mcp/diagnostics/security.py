"""SEC-001: effective NSG rule evaluation for one source NIC toward one
destination IP/port/protocol.

Leverages Azure's own effective-NSG computation
(``azure_get_effective_network_security_groups`` /
``arm.network_security_groups.get_effective_network_security_groups``) --
Azure has already merged subnet- and NIC-level NSG associations and
expanded any Application Security Group reference into concrete IP
prefixes before this rule ever runs. This rule's own job is only
first-match-wins priority evaluation against one destination, not rule
merging or ASG expansion.

NSGs are stateful (like AWS security groups): only the initiating
direction is evaluated here (``direction="Outbound"`` from the source
NIC's perspective) -- the automatic stateful return path is not itself a
separate rule to evaluate, mirroring this project's AWS sibling's
"initiating-direction-only" security-group evaluation convention.
"""

from __future__ import annotations

import ipaddress

from azure_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from azure_network_mcp.models.network_resources import EffectiveSecurityRule

RULE_ID = "SEC-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Effective NSG rule evaluation",
    description=(
        "Evaluates the effective NSG rules (from Azure's own merged subnet/NIC "
        "association and ASG-expansion computation) Azure actually applies to a "
        "source NIC's outbound traffic toward a destination IP/port/protocol, in "
        "priority order, first match wins."
    ),
    default_severity="info",
)

_ANY_ADDRESS_TOKENS = {"*", "0.0.0.0/0", "internet", "any"}


def _address_matches(prefixes: list[str], ip: str) -> bool:
    if not prefixes:
        return False
    try:
        target = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for prefix in prefixes:
        token = prefix.strip().lower()
        if token in _ANY_ADDRESS_TOKENS:
            return True
        if token in {"virtualnetwork", "azureloadbalancer", "internet"}:
            continue  # service tags this rule doesn't resolve -- not a match, not a miss
        try:
            network = ipaddress.ip_network(prefix, strict=False)
        except ValueError:
            continue
        if target in network:
            return True
    return False


def _port_matches(port_ranges: list[str], port: int) -> bool:
    if not port_ranges:
        return False
    for entry in port_ranges:
        token = entry.strip()
        if token == "*":
            return True
        if "-" in token:
            try:
                low, high = (int(p) for p in token.split("-", 1))
            except ValueError:
                continue
            if low <= port <= high:
                return True
        else:
            try:
                if int(token) == port:
                    return True
            except ValueError:
                continue
    return False


def _protocol_matches(rule_protocol: str | None, protocol: str) -> bool:
    if not rule_protocol or rule_protocol == "*":
        return True
    return rule_protocol.strip().lower() == protocol.strip().lower()


def _rule_addresses(rule: EffectiveSecurityRule, *, destination: bool) -> list[str]:
    expanded = (
        rule.expanded_destination_address_prefix
        if destination
        else rule.expanded_source_address_prefix
    )
    if expanded:
        return expanded
    return rule.destination_address_prefixes if destination else rule.source_address_prefixes


def evaluate_security_rules(
    *,
    source_nic_id: str,
    effective_rules: list[EffectiveSecurityRule],
    destination_ip: str,
    destination_port: int,
    protocol: str,
    freshness: str,
) -> tuple[str, Finding]:
    """Return ``(security_verdict, Finding)``. ``security_verdict`` is one
    of ``"allowed"``, ``"blocked"``, or ``"indeterminate"``."""
    if not effective_rules:
        return (
            "indeterminate",
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="info",
                confidence="indeterminate",
                summary=(
                    f"No effective NSG rules were available for NIC {source_nic_id}; NSG "
                    "evaluation could not be determined."
                ),
                affected_resources=[source_nic_id],
                freshness=freshness,
                limitations=[
                    "The effective NSG computation for this NIC returned no rules -- it may "
                    "have no NSG association at all (all traffic implicitly allowed within "
                    "the VNet), or the identity may lack the "
                    "effectiveNetworkSecurityGroups/action permission."
                ],
            ),
        )

    outbound = sorted(
        (r for r in effective_rules if r.direction == "Outbound"),
        key=lambda r: r.priority if r.priority is not None else 1 << 20,
    )

    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []
    for rule in outbound:
        if not _protocol_matches(rule.protocol, protocol):
            continue
        if not _port_matches(rule.destination_port_ranges, destination_port):
            continue
        if not _address_matches(_rule_addresses(rule, destination=True), destination_ip):
            continue

        evidence.append(
            Evidence(
                source=f"effective_nsg_rule:{rule.name}",
                detail=(
                    f"priority={rule.priority}, access={rule.access}, "
                    f"protocol={rule.protocol}, destination_ports="
                    f"{','.join(rule.destination_port_ranges)}"
                ),
            )
        )
        reasoning.append(
            ReasoningStep(
                step=1,
                description=(
                    f"Rule '{rule.name}' (priority {rule.priority}) matches "
                    f"{protocol}/{destination_port} to {destination_ip}: access={rule.access}."
                ),
                evidence_indices=[0],
            )
        )

        if rule.access == "Allow":
            return (
                "allowed",
                Finding(
                    rule_id=RULE_ID,
                    rule_version="1.0.0",
                    severity="info",
                    confidence="high",
                    summary=(
                        f"NSG rule '{rule.name}' (priority {rule.priority}) allows outbound "
                        f"{protocol}/{destination_port} from NIC {source_nic_id} to "
                        f"{destination_ip}."
                    ),
                    affected_resources=[source_nic_id],
                    evidence=evidence,
                    reasoning=reasoning,
                    freshness=freshness,
                ),
            )
        return (
            "blocked",
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="medium",
                confidence="high",
                summary=(
                    f"NSG rule '{rule.name}' (priority {rule.priority}) denies outbound "
                    f"{protocol}/{destination_port} from NIC {source_nic_id} to "
                    f"{destination_ip}."
                ),
                affected_resources=[source_nic_id],
                evidence=evidence,
                reasoning=reasoning,
                freshness=freshness,
                remediation=(
                    "If this traffic should be allowed, add a higher-priority (lower "
                    "number) Allow rule to the NSG(s) applied to this NIC."
                ),
            ),
        )

    return (
        "indeterminate",
        Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="info",
            confidence="indeterminate",
            summary=(
                f"No effective NSG rule on NIC {source_nic_id} explicitly matched "
                f"{protocol}/{destination_port} to {destination_ip} (including default "
                "rules) -- evaluation is inconclusive."
            ),
            affected_resources=[source_nic_id],
            freshness=freshness,
            limitations=[
                "No rule (custom or default) in the effective rule set matched this exact "
                "protocol/port/destination combination; this can happen if the effective "
                "rule set was only partially returned."
            ],
        ),
    )


__all__ = ["RULE_ID", "evaluate_security_rules"]
