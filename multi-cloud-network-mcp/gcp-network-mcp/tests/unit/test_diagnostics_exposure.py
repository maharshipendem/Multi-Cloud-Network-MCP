from __future__ import annotations

from gcp_network_mcp.diagnostics.exposure import evaluate_exposure
from gcp_network_mcp.models.firewall import FirewallRule, ProtocolPorts
from gcp_network_mcp.models.load_balancing import ForwardingRuleSummary

FRESHNESS = "2026-08-27T00:00:00Z"
NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-1"


def _forwarding_rule(
    *,
    scheme: str | None = "EXTERNAL",
    network_self_link: str | None = NETWORK,
    ports: list[str] | None = None,
    port_range: str | None = None,
    ip_protocol: str | None = "TCP",
) -> ForwardingRuleSummary:
    return ForwardingRuleSummary(
        name="fr-1",
        project_id="p",
        observed_at=FRESHNESS,
        ip_address="203.0.113.10",
        ip_protocol=ip_protocol,
        load_balancing_scheme=scheme,
        network_self_link=network_self_link,
        ports=ports or [],
        port_range=port_range,
    )


def _allow_all_ingress() -> FirewallRule:
    return FirewallRule(
        name="allow-all-ingress",
        project_id="p",
        observed_at=FRESHNESS,
        network_self_link=NETWORK,
        direction="INGRESS",
        priority=1000,
        disabled=False,
        action="ALLOW",
        allowed=[ProtocolPorts(ip_protocol="all")],
        source_ranges=[],
    )


def _deny_all_ingress() -> FirewallRule:
    return FirewallRule(
        name="deny-all-external",
        project_id="p",
        observed_at=FRESHNESS,
        network_self_link=NETWORK,
        direction="INGRESS",
        priority=1000,
        disabled=False,
        action="DENY",
        denied=[ProtocolPorts(ip_protocol="all")],
        source_ranges=["0.0.0.0/0"],
    )


def test_internal_scheme_is_not_exposure_and_returns_none() -> None:
    rule = _forwarding_rule(scheme="INTERNAL")
    assert evaluate_exposure(rule=rule, firewall_rules=[], freshness=FRESHNESS) is None


def test_external_scheme_with_no_network_self_link_is_indeterminate() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL", network_self_link=None)
    finding = evaluate_exposure(rule=rule, firewall_rules=[], freshness=FRESHNESS)
    assert finding is not None
    assert finding.confidence == "indeterminate"
    assert finding.severity == "medium"
    assert finding.limitations
    assert finding.evidence == []


def test_external_managed_scheme_is_also_treated_as_external() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL_MANAGED", ports=["443"])
    finding = evaluate_exposure(
        rule=rule, firewall_rules=[_allow_all_ingress()], freshness=FRESHNESS
    )
    assert finding is not None
    assert finding.severity == "high"


def test_public_rule_with_no_protecting_firewall_rule_is_flagged_high() -> None:
    """No firewall rules at all (not even implied defaults) means
    evaluate_firewall's own verdict is 'indeterminate', not 'ALLOW' -- but
    exposure still surfaces a Finding for the externally-scoped rule,
    just at reduced (indeterminate) confidence rather than the 'ALLOW'
    high-severity case."""
    rule = _forwarding_rule(scheme="EXTERNAL", ports=["443"])
    finding = evaluate_exposure(rule=rule, firewall_rules=[], freshness=FRESHNESS)
    assert finding is not None
    assert finding.evidence
    assert finding.limitations


def test_public_rule_explicitly_allowed_is_high_severity() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL", ports=["443"])
    finding = evaluate_exposure(
        rule=rule, firewall_rules=[_allow_all_ingress()], freshness=FRESHNESS
    )
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert finding.evidence
    assert finding.remediation is not None


def test_public_rule_protected_by_deny_all_is_lower_severity() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL", ports=["443"])
    finding = evaluate_exposure(
        rule=rule, firewall_rules=[_deny_all_ingress()], freshness=FRESHNESS
    )
    assert finding is not None
    assert finding.severity == "low"
    assert finding.confidence == "high"
    assert finding.evidence
    assert finding.limitations == []


def test_allowed_and_denied_verdicts_produce_different_severities() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL", ports=["443"])
    allowed = evaluate_exposure(
        rule=rule, firewall_rules=[_allow_all_ingress()], freshness=FRESHNESS
    )
    denied = evaluate_exposure(rule=rule, firewall_rules=[_deny_all_ingress()], freshness=FRESHNESS)
    assert allowed is not None
    assert denied is not None
    assert allowed.severity != denied.severity
    assert allowed.severity == "high"
    assert denied.severity == "low"


def test_port_range_is_used_when_ports_list_is_empty() -> None:
    rule = _forwarding_rule(scheme="EXTERNAL", ports=[], port_range="8000-9000")
    finding = evaluate_exposure(
        rule=rule, firewall_rules=[_allow_all_ingress()], freshness=FRESHNESS
    )
    assert finding is not None
    assert finding.severity == "high"
