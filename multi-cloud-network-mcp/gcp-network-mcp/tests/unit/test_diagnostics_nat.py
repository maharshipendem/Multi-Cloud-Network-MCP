from __future__ import annotations

from gcp_network_mcp.diagnostics.nat import evaluate_nat
from gcp_network_mcp.models.nat import RouterNatSummary

FRESHNESS = "2026-08-27T00:00:00Z"
ROUTER_NAME = "router-1"


def _nat(
    *,
    nat_ip_allocate_option: str | None = "AUTO_ONLY",
    nat_ips: list[str] | None = None,
    min_ports_per_vm: int | None = 64,
) -> RouterNatSummary:
    return RouterNatSummary(
        name="nat-1",
        nat_ip_allocate_option=nat_ip_allocate_option,
        nat_ips=nat_ips or [],
        min_ports_per_vm=min_ports_per_vm,
    )


def test_healthy_auto_nat_returns_none() -> None:
    nat = _nat(nat_ip_allocate_option="AUTO_ONLY", min_ports_per_vm=64)
    assert evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS) is None


def test_healthy_manual_nat_with_ips_and_sufficient_ports_returns_none() -> None:
    nat = _nat(nat_ip_allocate_option="MANUAL_ONLY", nat_ips=["1.2.3.4"], min_ports_per_vm=128)
    assert evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS) is None


def test_missing_min_ports_per_vm_is_not_flagged() -> None:
    nat = _nat(nat_ip_allocate_option="AUTO_ONLY", min_ports_per_vm=None)
    assert evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS) is None


def test_manual_only_with_zero_ips_is_critical() -> None:
    nat = _nat(nat_ip_allocate_option="MANUAL_ONLY", nat_ips=[], min_ports_per_vm=64)
    finding = evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "critical"
    assert finding.confidence == "high"
    assert finding.evidence
    assert "MANUAL_ONLY" in finding.summary
    assert finding.remediation is not None


def test_low_min_ports_per_vm_is_low_severity_reduced_confidence() -> None:
    nat = _nat(nat_ip_allocate_option="AUTO_ONLY", min_ports_per_vm=32)
    finding = evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "low"
    assert finding.confidence == "medium"
    assert finding.evidence
    assert finding.limitations
    assert "32" in finding.summary


def test_min_ports_per_vm_at_threshold_is_not_flagged() -> None:
    nat = _nat(nat_ip_allocate_option="AUTO_ONLY", min_ports_per_vm=64)
    assert evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS) is None


def test_manual_only_zero_ips_takes_precedence_over_low_ports() -> None:
    """Both triggers technically apply (MANUAL_ONLY/no IPs, and a low
    min_ports_per_vm) -- the manual-allocation check runs first and wins,
    since it's the more severe, definite outage vs. a port-exhaustion risk."""
    nat = _nat(nat_ip_allocate_option="MANUAL_ONLY", nat_ips=[], min_ports_per_vm=16)
    finding = evaluate_nat(router_name=ROUTER_NAME, nat=nat, freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "critical"


def test_two_distinct_triggers_produce_different_severities() -> None:
    manual_zero_ips = evaluate_nat(
        router_name=ROUTER_NAME,
        nat=_nat(nat_ip_allocate_option="MANUAL_ONLY", nat_ips=[], min_ports_per_vm=64),
        freshness=FRESHNESS,
    )
    low_ports = evaluate_nat(
        router_name=ROUTER_NAME,
        nat=_nat(nat_ip_allocate_option="AUTO_ONLY", min_ports_per_vm=32),
        freshness=FRESHNESS,
    )
    assert manual_zero_ips is not None
    assert low_ports is not None
    assert manual_zero_ips.severity != low_ports.severity
    assert manual_zero_ips.confidence != low_ports.confidence
