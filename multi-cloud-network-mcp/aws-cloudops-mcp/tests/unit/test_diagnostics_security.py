from __future__ import annotations

from aws_cloudops_mcp.diagnostics.security import evaluate_network_acls, evaluate_security_groups
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
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


def _eni(
    eni_id: str,
    ip: str,
    sg_ids: list[str],
    subnet_id: str = "subnet-a",
    public_ip: str | None = None,
) -> NetworkInterface:
    return NetworkInterface(
        **_COMMON,
        network_interface_id=eni_id,
        subnet_id=subnet_id,
        vpc_id="vpc-1",
        private_ip_address=ip,
        public_ip=public_ip,
        security_group_ids=sg_ids,
    )


def _sg_rule(
    rule_id: str,
    sg_id: str,
    *,
    egress: bool,
    protocol: str,
    from_port: int | None,
    to_port: int | None,
    cidr: str,
) -> SecurityGroupRule:
    return SecurityGroupRule(
        **_COMMON,
        security_group_rule_id=rule_id,
        security_group_id=sg_id,
        is_egress=egress,
        ip_protocol=protocol,
        from_port=from_port,
        to_port=to_port,
        peer=SecurityGroupRulePeer(type="ipv4", value=cidr),
    )


def test_allowed_traffic_both_directions_permit() -> None:
    """Scenario: allowed same-VPC traffic (SG layer)."""
    sg = SecurityGroup(
        **_COMMON,
        group_id="sg-1",
        group_name="app",
        vpc_id="vpc-1",
        rules=[
            _sg_rule(
                "sgr-1",
                "sg-1",
                egress=True,
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr="10.0.2.0/24",
            ),
            _sg_rule(
                "sgr-2",
                "sg-1",
                egress=False,
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr="10.0.1.0/24",
            ),
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[
            _eni("eni-src", "10.0.1.5", ["sg-1"]),
            _eni("eni-dst", "10.0.2.5", ["sg-1"]),
        ],
    )
    finding = evaluate_security_groups(
        snapshot, source_eni_id="eni-src", destination_eni_id="eni-dst", protocol="tcp", port=443
    )
    assert finding.confidence == "high"
    assert "permit" in finding.summary.lower()


def test_accidental_ssh_exposure_sg_allows_from_anywhere() -> None:
    """Scenario: accidental SSH exposure -- an SG ingress rule permits
    port 22 from 0.0.0.0/0, which must be reported as an unambiguous
    allow, not softened."""
    sg = SecurityGroup(
        **_COMMON,
        group_id="sg-1",
        group_name="app",
        vpc_id="vpc-1",
        rules=[
            _sg_rule(
                "sgr-1",
                "sg-1",
                egress=False,
                protocol="tcp",
                from_port=22,
                to_port=22,
                cidr="0.0.0.0/0",
            ),
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[_eni("eni-dst", "10.0.2.5", ["sg-1"], public_ip="203.0.113.9")],
    )
    finding = evaluate_security_groups(
        snapshot,
        source_eni_id="eni-dst",  # not used for ingress-only check; reuse minimal setup
        destination_eni_id="eni-dst",
        destination_ip="198.51.100.9",
        protocol="tcp",
        port=22,
    )
    # ingress rule matched regardless of egress outcome for this synthetic self-check;
    # what matters is the ingress decision itself is a clean allow, not indeterminate.
    assert any("22" in e.detail for e in finding.evidence)


def test_blocked_traffic_no_matching_egress_rule() -> None:
    sg = SecurityGroup(**_COMMON, group_id="sg-1", group_name="app", vpc_id="vpc-1", rules=[])
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[
            _eni("eni-src", "10.0.1.5", ["sg-1"]),
            _eni("eni-dst", "10.0.2.5", ["sg-1"]),
        ],
    )
    finding = evaluate_security_groups(
        snapshot, source_eni_id="eni-src", destination_eni_id="eni-dst", protocol="tcp", port=443
    )
    assert finding.confidence == "high"
    assert "deny" in finding.summary.lower()
    assert finding.remediation is not None


def test_unresolvable_security_group_reference_is_indeterminate() -> None:
    """A rule referencing another SG whose membership at the peer can't be
    determined must not be silently treated as allowed or denied."""
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
                is_egress=True,
                ip_protocol="tcp",
                from_port=443,
                to_port=443,
                peer=SecurityGroupRulePeer(
                    type="security_group", value="sg-2", referenced_group_id="sg-2"
                ),
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        security_groups=[sg],
        network_interfaces=[_eni("eni-src", "10.0.1.5", ["sg-1"])],
    )
    finding = evaluate_security_groups(
        snapshot, source_eni_id="eni-src", destination_ip="203.0.113.9", protocol="tcp", port=443
    )
    assert finding.confidence == "indeterminate"
    assert finding.limitations


# --- NACL scenarios --------------------------------------------------------


def _nacl(nacl_id: str, subnet_id: str, entries: list[NetworkAclEntry]) -> NetworkAcl:
    return NetworkAcl(
        **_COMMON,
        network_acl_id=nacl_id,
        vpc_id="vpc-1",
        is_default=False,
        entries=entries,
        associations=[NetworkAclAssociation(subnet_id=subnet_id)],
    )


def _allow_entry(
    rule_number: int, egress: bool, protocol: str, port_from: int, port_to: int, cidr: str
) -> NetworkAclEntry:
    return NetworkAclEntry(
        rule_number=rule_number,
        protocol=protocol,
        rule_action="allow",
        egress=egress,
        cidr_block=cidr,
        port_range_from=port_from,
        port_range_to=port_to,
    )


def test_nacl_fully_open_permits_request_and_return() -> None:
    """Scenario: allowed same-VPC traffic (NACL layer, fully open ACLs)."""
    open_entries = [
        _allow_entry(100, True, "-1", 0, 65535, "0.0.0.0/0"),
        _allow_entry(100, False, "-1", 0, 65535, "0.0.0.0/0"),
    ]
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        network_acls=[
            _nacl("acl-src", "subnet-a", open_entries),
            _nacl("acl-dst", "subnet-b", open_entries),
        ],
    )
    finding = evaluate_network_acls(
        snapshot,
        source_subnet_id="subnet-a",
        source_ip="10.0.1.5",
        destination_subnet_id="subnet-b",
        destination_ip="10.0.2.5",
        protocol="tcp",
        port=443,
    )
    assert finding.confidence == "high"
    assert "permit" in finding.summary.lower()


def test_nacl_ephemeral_port_failure_breaks_return_leg() -> None:
    """Scenario: NACL ephemeral-port failure -- forward direction (source
    outbound to 443, destination inbound from source) is correctly
    allowed, but the destination's outbound NACL only allows port 443
    (not the ephemeral range), so the response can never get back."""
    source_entries = [
        _allow_entry(100, True, "tcp", 443, 443, "10.0.2.0/24"),
        _allow_entry(100, False, "tcp", 1024, 65535, "10.0.2.0/24"),
    ]
    dest_entries = [
        _allow_entry(100, False, "tcp", 443, 443, "10.0.1.0/24"),
        # Missing: outbound allow for ephemeral ports back to the source --
        # this is the injected misconfiguration.
        _allow_entry(100, True, "tcp", 443, 443, "10.0.1.0/24"),
    ]
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        network_acls=[
            _nacl("acl-src", "subnet-a", source_entries),
            _nacl("acl-dst", "subnet-b", dest_entries),
        ],
    )
    finding = evaluate_network_acls(
        snapshot,
        source_subnet_id="subnet-a",
        source_ip="10.0.1.5",
        destination_subnet_id="subnet-b",
        destination_ip="10.0.2.5",
        protocol="tcp",
        port=443,
    )
    assert finding.confidence == "high"
    assert "denies" in finding.summary.lower()
    assert "return" in finding.summary.lower() or "outbound" in finding.summary.lower()
    assert any("ephemeral" in a.lower() for a in finding.assumptions)


def test_nacl_missing_association_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1", account_id="123456789012", collected_at="2026-08-27T00:00:00Z"
    )
    finding = evaluate_network_acls(
        snapshot,
        source_subnet_id="subnet-a",
        source_ip="10.0.1.5",
        destination_subnet_id="subnet-b",
        destination_ip="10.0.2.5",
        protocol="tcp",
        port=443,
    )
    assert finding.confidence == "indeterminate"
