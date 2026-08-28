from __future__ import annotations

from gcp_network_mcp.diagnostics.firewall import (
    evaluate_firewall,
    evaluate_hierarchical_interaction,
)
from gcp_network_mcp.models.firewall import (
    FirewallPolicy,
    FirewallPolicyRule,
    FirewallRule,
    ProtocolPorts,
)

FRESHNESS = "2026-08-27T00:00:00Z"
NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-1"


def _rule(
    name: str,
    *,
    action: str,
    direction: str = "INGRESS",
    priority: int = 1000,
    protocol: str = "tcp",
    ports: list[str] | None = None,
    source_ranges: list[str] | None = None,
    destination_ranges: list[str] | None = None,
    is_implied: bool = False,
) -> FirewallRule:
    entries = [ProtocolPorts(ip_protocol=protocol, ports=ports or [])]
    return FirewallRule(
        name=name,
        project_id="p",
        observed_at=FRESHNESS,
        network_self_link=NETWORK,
        direction=direction,
        priority=priority,
        disabled=False,
        action=action,
        allowed=entries if action == "ALLOW" else [],
        denied=entries if action == "DENY" else [],
        source_ranges=source_ranges if source_ranges is not None else [],
        destination_ranges=destination_ranges if destination_ranges is not None else [],
        is_implied=is_implied,
    )


# --------------------------------------------------------------------------
# evaluate_firewall (FW-001)
# --------------------------------------------------------------------------


def test_allow_rule_matches_traffic() -> None:
    rules = [_rule("allow-ssh", action="ALLOW", ports=["22"])]
    verdict, finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=22,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "ALLOW"
    assert finding.severity == "info"
    assert finding.confidence == "high"
    assert finding.evidence
    assert finding.evidence[0].source == "firewall_rule:allow-ssh"


def test_deny_rule_matches_traffic() -> None:
    rules = [_rule("deny-all", action="DENY", protocol="all")]
    verdict, finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=443,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "DENY"
    assert finding.severity == "medium"
    assert finding.evidence


def test_lower_priority_number_wins_first_match() -> None:
    rules = [
        _rule("allow-high-precedence", action="ALLOW", priority=100, protocol="all"),
        _rule("deny-low-precedence", action="DENY", priority=2000, protocol="all"),
    ]
    verdict, finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=80,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "ALLOW"
    assert "allow-high-precedence" in finding.summary


def test_empty_source_ranges_matches_any_peer() -> None:
    rules = [_rule("allow-any-source", action="ALLOW", protocol="all", source_ranges=[])]
    verdict, _finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=80,
        peer_ip="198.51.100.9",
        freshness=FRESHNESS,
    )
    assert verdict == "ALLOW"


def test_source_range_restricts_match_to_covered_peers() -> None:
    rules = [
        _rule(
            "allow-internal-only",
            action="ALLOW",
            protocol="all",
            source_ranges=["10.0.0.0/8"],
        )
    ]
    # peer outside the restricted range: this rule shouldn't match, and with
    # no other rules present the evaluation falls through to "no match".
    verdict, finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=80,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "indeterminate"


def test_port_range_entry_matches_contained_port() -> None:
    rules = [_rule("allow-range", action="ALLOW", protocol="tcp", ports=["1000-2000"])]
    verdict, _finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=rules,
        direction="INGRESS",
        protocol="tcp",
        port=1500,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "ALLOW"


def test_no_rule_matches_including_no_implied_defaults_is_indeterminate() -> None:
    verdict, finding = evaluate_firewall(
        network_self_link=NETWORK,
        firewall_rules=[],
        direction="INGRESS",
        protocol="tcp",
        port=80,
        peer_ip="203.0.113.5",
        freshness=FRESHNESS,
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "indeterminate"
    assert finding.evidence == []
    assert finding.limitations


# --------------------------------------------------------------------------
# evaluate_hierarchical_interaction (FW-002)
# --------------------------------------------------------------------------


def _policy(rules: list[FirewallPolicyRule]) -> FirewallPolicy:
    return FirewallPolicy(
        name="org-policy",
        project_id="",
        observed_at=FRESHNESS,
        scope="hierarchical",
        rules=rules,
    )


def test_no_hierarchical_policies_supplied_is_indeterminate() -> None:
    """No parent_id-scoped hierarchical policies were supplied at all --
    evaluate_hierarchical_interaction takes the policies themselves
    (``hierarchical_policies``) rather than a bare ``parent_id``; an empty
    list is the "not supplied" case."""
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict is None
    assert finding.confidence == "indeterminate"
    assert finding.limitations


def test_no_applicable_rule_leaves_network_level_verdict_standing() -> None:
    policy = _policy(
        [
            FirewallPolicyRule(
                priority=100,
                action="deny",
                direction="EGRESS",  # different direction -- not applicable
                disabled=False,
                rule_name="egress-deny",
            )
        ]
    )
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[policy],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict is None
    assert finding.confidence == "high"
    assert finding.severity == "info"


def test_hierarchical_deny_overrides_vpc_level_allow() -> None:
    policy = _policy(
        [
            FirewallPolicyRule(
                priority=10,
                action="deny",
                direction="INGRESS",
                disabled=False,
                rule_name="org-deny-ingress",
            )
        ]
    )
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[policy],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict == "DENY"
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "OVERRIDES" in finding.summary
    assert finding.evidence
    assert finding.remediation is not None


def test_hierarchical_rule_agreeing_with_verdict_does_not_override() -> None:
    policy = _policy(
        [
            FirewallPolicyRule(
                priority=10,
                action="allow",
                direction="INGRESS",
                disabled=False,
                rule_name="org-allow-ingress",
            )
        ]
    )
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[policy],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict is None
    assert finding.severity == "info"
    assert finding.remediation is None


def test_disabled_hierarchical_rule_is_not_applicable() -> None:
    policy = _policy(
        [
            FirewallPolicyRule(
                priority=10,
                action="deny",
                direction="INGRESS",
                disabled=True,
                rule_name="disabled-deny",
            )
        ]
    )
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[policy],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict is None
    assert finding.severity == "info"


def test_lowest_priority_number_wins_among_applicable_hierarchical_rules() -> None:
    policy = _policy(
        [
            FirewallPolicyRule(
                priority=500,
                action="allow",
                direction="INGRESS",
                disabled=False,
                rule_name="lower-precedence-allow",
            ),
            FirewallPolicyRule(
                priority=5,
                action="deny",
                direction="INGRESS",
                disabled=False,
                rule_name="higher-precedence-deny",
            ),
        ]
    )
    overriding_verdict, finding = evaluate_hierarchical_interaction(
        network_self_link=NETWORK,
        hierarchical_policies=[policy],
        network_level_verdict="ALLOW",
        direction="INGRESS",
        freshness=FRESHNESS,
    )
    assert overriding_verdict == "DENY"
    assert "higher-precedence-deny" in finding.summary
