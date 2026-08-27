from __future__ import annotations

from aws_cloudops_mcp.diagnostics.exposure import (
    evaluate_eni_exposure,
    evaluate_load_balancer_exposure,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Route, RouteTable, RouteTableAssociation
from aws_cloudops_mcp.models.network_resources import (
    Listener,
    LoadBalancer,
    NetworkAcl,
    NetworkAclAssociation,
    NetworkAclEntry,
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


def _open_route_table(rt_id: str, subnet_id: str) -> RouteTable:
    return RouteTable(
        **_COMMON,
        route_table_id=rt_id,
        vpc_id="vpc-1",
        routes=[
            Route(
                destination_cidr_block="0.0.0.0/0",
                target="igw-1",
                target_type="gateway",
                state="active",
                origin="CreateRoute",
            ),
        ],
        associations=[RouteTableAssociation(subnet_id=subnet_id)],
    )


def _open_nacl(nacl_id: str, subnet_id: str) -> NetworkAcl:
    return NetworkAcl(
        **_COMMON,
        network_acl_id=nacl_id,
        vpc_id="vpc-1",
        is_default=False,
        entries=[
            NetworkAclEntry(
                rule_number=100,
                protocol="-1",
                rule_action="allow",
                egress=False,
                cidr_block="0.0.0.0/0",
            ),
            NetworkAclEntry(
                rule_number=100,
                protocol="-1",
                rule_action="allow",
                egress=True,
                cidr_block="0.0.0.0/0",
            ),
        ],
        associations=[NetworkAclAssociation(subnet_id=subnet_id)],
    )


def test_accidental_ssh_exposure_is_proven_reachable() -> None:
    """Scenario: accidental SSH exposure -- public IP + public route + SG
    allowing 0.0.0.0/0:22 + permissive NACL together prove reachability,
    not just potential exposure."""
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
        security_groups=[sg],
        route_tables=[_open_route_table("rtb-1", "subnet-a")],
        network_acls=[_open_nacl("acl-1", "subnet-a")],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-1",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address="10.0.1.5",
                public_ip="203.0.113.9",
                security_group_ids=["sg-1"],
            )
        ],
    )
    finding = evaluate_eni_exposure(snapshot, "eni-1")
    assert finding.severity == "critical"
    assert finding.confidence == "high"
    assert "reachable" in finding.summary.lower()


def test_permissive_sg_without_public_ip_is_latent_not_reachable() -> None:
    """Distinguishes potential exposure from proven reachability: the SG
    is wide open, but there's no public IP, so this must not be reported
    as actually reachable."""
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
        security_groups=[sg],
        route_tables=[_open_route_table("rtb-1", "subnet-a")],
        network_acls=[_open_nacl("acl-1", "subnet-a")],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-1",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address="10.0.1.5",
                public_ip=None,
                security_group_ids=["sg-1"],
            )
        ],
    )
    finding = evaluate_eni_exposure(snapshot, "eni-1")
    assert finding.severity == "low"
    assert finding.confidence == "high"
    assert (
        "not currently reachable" in finding.summary.lower() or "latent" in finding.summary.lower()
    )


def test_no_open_ingress_produces_low_noise_finding() -> None:
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
    finding = evaluate_eni_exposure(snapshot, "eni-1")
    assert finding.severity == "info"


def test_public_alb_with_open_ingress_flagged() -> None:
    """Scenario: public ALB."""
    sg = SecurityGroup(
        **_COMMON,
        group_id="sg-lb",
        group_name="lb-sg",
        vpc_id="vpc-1",
        rules=[
            SecurityGroupRule(
                **_COMMON,
                security_group_rule_id="sgr-1",
                security_group_id="sg-lb",
                is_egress=False,
                ip_protocol="tcp",
                from_port=443,
                to_port=443,
                peer=SecurityGroupRulePeer(type="ipv4", value="0.0.0.0/0"),
            )
        ],
    )
    lb = LoadBalancer(
        **_COMMON,
        load_balancer_arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/x/1",
        load_balancer_name="public-alb",
        scheme="internet-facing",
        type="application",
        security_group_ids=["sg-lb"],
        listeners=[
            Listener(
                listener_arn="arn:listener/1",
                load_balancer_arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/x/1",
                protocol="HTTPS",
                port=443,
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        load_balancers=[lb],
    )
    finding = evaluate_load_balancer_exposure(snapshot, lb.load_balancer_arn)
    assert finding.confidence == "high"
    assert "internet-facing" in finding.summary.lower()


def test_internal_lb_not_flagged_as_exposed() -> None:
    lb = LoadBalancer(
        **_COMMON,
        load_balancer_arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/x/2",
        load_balancer_name="internal-alb",
        scheme="internal",
        type="application",
        security_group_ids=[],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        load_balancers=[lb],
    )
    finding = evaluate_load_balancer_exposure(snapshot, lb.load_balancer_arn)
    assert finding.severity == "info"


def test_unknown_eni_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1", account_id="123456789012", collected_at="2026-08-27T00:00:00Z"
    )
    finding = evaluate_eni_exposure(snapshot, "eni-missing")
    assert finding.confidence == "indeterminate"
