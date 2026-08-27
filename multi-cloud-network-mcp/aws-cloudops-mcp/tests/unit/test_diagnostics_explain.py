from __future__ import annotations

from aws_cloudops_mcp.diagnostics.explain import explain_network_path
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Route, RouteTable, RouteTableAssociation, Subnet, Vpc
from aws_cloudops_mcp.models.network_resources import (
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


def _vpc(vpc_id: str, cidr: str) -> Vpc:
    return Vpc(**_COMMON, vpc_id=vpc_id, cidr_block=cidr, state="available", is_default=False)


def _subnet(subnet_id: str, vpc_id: str, cidr: str) -> Subnet:
    return Subnet(
        **_COMMON,
        subnet_id=subnet_id,
        vpc_id=vpc_id,
        cidr_block=cidr,
        availability_zone="us-east-1a",
        available_ip_address_count=250,
        map_public_ip_on_launch=False,
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


def _base_snapshot(sg_rules: list[SecurityGroupRule]) -> NetworkSnapshot:
    sg = SecurityGroup(**_COMMON, group_id="sg-1", group_name="app", vpc_id="vpc-1", rules=sg_rules)
    return NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[
            _subnet("subnet-a", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-b", "vpc-1", "10.0.2.0/24"),
        ],
        route_tables=[
            RouteTable(
                **_COMMON,
                route_table_id="rtb-1",
                vpc_id="vpc-1",
                routes=[
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    )
                ],
                associations=[
                    RouteTableAssociation(subnet_id="subnet-a"),
                    RouteTableAssociation(subnet_id="subnet-b"),
                ],
            )
        ],
        security_groups=[sg],
        network_acls=[_open_nacl("acl-a", "subnet-a"), _open_nacl("acl-b", "subnet-b")],
        network_interfaces=[
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-src",
                subnet_id="subnet-a",
                vpc_id="vpc-1",
                private_ip_address="10.0.1.5",
                security_group_ids=["sg-1"],
            ),
            NetworkInterface(
                **_COMMON,
                network_interface_id="eni-dst",
                subnet_id="subnet-b",
                vpc_id="vpc-1",
                private_ip_address="10.0.2.5",
                security_group_ids=["sg-1"],
            ),
        ],
    )


def _open_sg_rule(egress: bool) -> SecurityGroupRule:
    return SecurityGroupRule(
        **_COMMON,
        security_group_rule_id=f"sgr-{'eg' if egress else 'in'}",
        security_group_id="sg-1",
        is_egress=egress,
        ip_protocol="tcp",
        from_port=443,
        to_port=443,
        peer=SecurityGroupRulePeer(type="ipv4", value="10.0.0.0/16"),
    )


def test_fully_allowed_path_evaluates_routing_sg_and_nacl() -> None:
    snapshot = _base_snapshot([_open_sg_rule(True), _open_sg_rule(False)])
    result = explain_network_path(
        snapshot,
        source_eni_id="eni-src",
        destination_eni_id="eni-dst",
        source_ip="10.0.1.5",
        destination_ip="10.0.2.5",
        destination="10.0.2.5",
        protocol="tcp",
        port=443,
    )
    assert result.overall_verdict == "allowed"
    assert len(result.findings) == 3


def test_blocked_at_routing_skips_sg_and_nacl() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            RouteTable(
                **_COMMON,
                route_table_id="rtb-1",
                vpc_id="vpc-1",
                routes=[],
                associations=[RouteTableAssociation(subnet_id="subnet-a")],
            )
        ],
    )
    result = explain_network_path(snapshot, source_subnet_id="subnet-a", destination="203.0.113.5")
    assert result.overall_verdict == "blocked"
    assert len(result.findings) == 1


def test_blocked_by_security_group_even_though_routable() -> None:
    snapshot = _base_snapshot([])  # no rules at all -> egress denied
    result = explain_network_path(
        snapshot,
        source_eni_id="eni-src",
        destination_eni_id="eni-dst",
        destination="10.0.2.5",
        protocol="tcp",
        port=443,
    )
    assert result.overall_verdict == "blocked"


def test_no_eni_info_is_partially_evaluated_not_silently_allowed() -> None:
    snapshot = _base_snapshot([_open_sg_rule(True), _open_sg_rule(False)])
    result = explain_network_path(snapshot, source_subnet_id="subnet-a", destination="10.0.2.5")
    assert result.overall_verdict == "partially_evaluated"
    assert len(result.findings) == 1
    assert result.findings[0].limitations
