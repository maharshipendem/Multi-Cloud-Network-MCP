from __future__ import annotations

from aws_cloudops_mcp.diagnostics.risks import find_network_risks
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Vpc
from aws_cloudops_mcp.models.network_resources import (
    NetworkInterface,
    SecurityGroup,
    SecurityGroupRule,
    SecurityGroupRulePeer,
)

_COMMON = {
    "account_id": "123456789012",
    "region": "us-east-1",
    "observed_at": "2026-08-27T00:00:00Z",
}


def test_find_network_risks_flags_overlapping_vpcs_and_exposed_eni() -> None:
    sg = SecurityGroup(
        **_COMMON,
        group_id="sg-1",
        group_name="app",
        vpc_id="vpc-1",
        rules=[
            SecurityGroupRule(
                **_COMMON,
                security_group_rule_id="sgr-1",
                security_group_id="sg-1",
                is_egress=False,
                ip_protocol="tcp",
                from_port=22,
                to_port=22,
                peer=SecurityGroupRulePeer(type="ipv4", value="0.0.0.0/0"),
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[
            Vpc(
                **_COMMON,
                vpc_id="vpc-1",
                cidr_block="10.0.0.0/16",
                state="available",
                is_default=False,
            ),
            Vpc(
                **_COMMON,
                vpc_id="vpc-2",
                cidr_block="10.0.8.0/20",
                state="available",
                is_default=False,
            ),
        ],
        security_groups=[sg],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-1",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address="10.0.1.5",
                security_group_ids=["sg-1"],
            )
        ],
    )
    findings = find_network_risks(snapshot)
    rule_ids = {f.rule_id for f in findings}
    assert "CONSIST-001" in rule_ids  # CIDR overlap
    assert "EXPOSE-001" in rule_ids  # ENI exposure (even if only latent)


def test_find_network_risks_min_severity_filters_info_findings() -> None:
    sg = SecurityGroup(**_COMMON, group_id="sg-1", group_name="app", vpc_id="vpc-1", rules=[])
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-1",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address="10.0.1.5",
                security_group_ids=["sg-1"],
            )
        ],
    )
    all_findings = find_network_risks(snapshot)
    assert any(f.severity == "info" for f in all_findings)

    filtered = find_network_risks(snapshot, min_severity="low")
    assert all(f.severity != "info" for f in filtered)


def test_find_network_risks_deterministic_ordering() -> None:
    sg = SecurityGroup(**_COMMON, group_id="sg-1", group_name="app", vpc_id="vpc-1", rules=[])
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id=f"eni-{i}",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address=f"10.0.1.{i}",
                security_group_ids=["sg-1"],
            )
            for i in range(5)
        ],
    )
    first = find_network_risks(snapshot)
    second = find_network_risks(snapshot)
    assert [f.affected_resources for f in first] == [f.affected_resources for f in second]


def test_find_network_risks_zero_resources_returns_empty() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1", account_id="123456789012", collected_at="2026-08-27T00:00:00Z"
    )
    assert find_network_risks(snapshot) == []
