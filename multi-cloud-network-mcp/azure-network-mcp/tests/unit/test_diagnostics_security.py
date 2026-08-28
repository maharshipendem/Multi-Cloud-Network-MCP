from __future__ import annotations

from azure_network_mcp.diagnostics.security import evaluate_security_rules
from azure_network_mcp.models.network_resources import EffectiveSecurityRule

NIC_ID = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/networkInterfaces/nic-1"


def _rule(
    name: str,
    priority: int,
    access: str,
    *,
    direction: str = "Outbound",
    protocol: str = "Tcp",
    dest_ports: list[str] | None = None,
    dest_prefixes: list[str] | None = None,
) -> EffectiveSecurityRule:
    return EffectiveSecurityRule(
        name=name,
        protocol=protocol,
        destination_port_ranges=dest_ports or ["443"],
        destination_address_prefixes=dest_prefixes or ["*"],
        access=access,
        priority=priority,
        direction=direction,
    )


def test_no_effective_rules_is_indeterminate() -> None:
    verdict, finding = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=[],
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "indeterminate"


def test_lowest_priority_number_wins_first_match() -> None:
    rules = [
        _rule("DenyAll", 4096, "Deny", dest_ports=["*"]),
        _rule("AllowHttps", 100, "Allow", dest_ports=["443"]),
    ]
    verdict, finding = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "allowed"
    assert "AllowHttps" in finding.summary


def test_deny_rule_blocks() -> None:
    rules = [_rule("DenyHttps", 100, "Deny", dest_ports=["443"])]
    verdict, finding = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "blocked"
    assert finding.remediation is not None


def test_default_deny_all_inbound_rule_still_evaluates_outbound_only() -> None:
    """Inbound-direction rules must never affect an outbound evaluation."""
    rules = [
        _rule("DenyAllInBound", 65500, "Deny", direction="Inbound", dest_ports=["*"]),
        _rule("AllowVnetOutBound", 65000, "Allow", direction="Outbound", dest_ports=["*"]),
    ]
    verdict, _ = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "allowed"


def test_port_range_matches() -> None:
    rules = [_rule("AllowEphemeral", 100, "Allow", dest_ports=["1024-65535"])]
    verdict, _ = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=50000,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "allowed"


def test_protocol_mismatch_does_not_match() -> None:
    rules = [_rule("AllowUdp", 100, "Allow", protocol="Udp", dest_ports=["443"])]
    verdict, finding = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "indeterminate"


def test_expanded_asg_prefix_is_used_over_raw_prefix() -> None:
    rule = _rule("AllowFromAsg", 100, "Allow", dest_ports=["443"])
    rule.destination_address_prefixes = []
    rule.expanded_destination_address_prefix = ["10.0.1.0/24"]
    verdict, _ = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=[rule],
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "allowed"


def test_priority_100_beats_priority_200_for_same_traffic() -> None:
    """Explicit NSG-priority-ordering scenario per the milestone's named
    test coverage ('NSG priority/default rules')."""
    rules = [
        _rule("Rule200", 200, "Deny", dest_ports=["443"]),
        _rule("Rule100", 100, "Allow", dest_ports=["443"]),
    ]
    verdict, finding = evaluate_security_rules(
        source_nic_id=NIC_ID,
        effective_rules=rules,
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
        freshness="now",
    )
    assert verdict == "allowed"
    assert "Rule100" in finding.summary
