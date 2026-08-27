"""Tests for the offline dry-run mode: loading a saved snapshot and
running the diagnostics engine against it with zero AWS/boto3 involvement
-- no ``mock_aws()``, no ``client_factory`` fixture, nothing network-
related imported at all in this file besides the diagnostics package.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aws_cloudops_mcp.diagnostics.explain import explain_network_path
from aws_cloudops_mcp.diagnostics.offline import load_snapshot, save_snapshot
from aws_cloudops_mcp.diagnostics.risks import find_network_risks
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Vpc

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "demo_network_snapshot.json"


def test_demo_fixture_exists_and_loads() -> None:
    assert _FIXTURE_PATH.exists(), f"expected demo fixture at {_FIXTURE_PATH}"
    snapshot = load_snapshot(_FIXTURE_PATH)
    assert isinstance(snapshot, NetworkSnapshot)
    assert len(snapshot.vpcs) >= 2


def test_demo_fixture_reproduces_accidental_ssh_exposure_and_cidr_overlap() -> None:
    """The demo fixture is a deliberately-seeded multi-scenario dataset --
    prove it actually reproduces the two risks it was built to
    demonstrate, entirely offline."""
    snapshot = load_snapshot(_FIXTURE_PATH)
    findings = find_network_risks(snapshot)
    rule_ids = {f.rule_id for f in findings}
    assert "EXPOSE-001" in rule_ids
    assert "CONSIST-001" in rule_ids

    exposure_finding = next(f for f in findings if f.rule_id == "EXPOSE-001")
    assert exposure_finding.severity == "critical"


def test_demo_fixture_explains_nat_egress_path() -> None:
    snapshot = load_snapshot(_FIXTURE_PATH)
    result = explain_network_path(
        snapshot, source_subnet_id="subnet-demo01private", destination="203.0.113.50"
    )
    assert result.route_verdict == "routable"
    assert [h.target_type for h in result.hops] == ["nat_gateway", "gateway"]


def test_load_snapshot_round_trips_through_save(tmp_path: Path) -> None:
    original = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[
            Vpc(
                account_id="123456789012",
                region="us-east-1",
                observed_at="2026-08-27T00:00:00Z",
                vpc_id="vpc-1",
                cidr_block="10.0.0.0/16",
                state="available",
                is_default=False,
            )
        ],
    )
    out_path = tmp_path / "snapshot.json"
    save_snapshot(original, out_path)
    reloaded = load_snapshot(out_path)
    assert reloaded == original


def test_load_snapshot_rejects_malformed_file(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"region": "us-east-1"}')  # missing required fields
    with pytest.raises(Exception, match="account_id|collected_at"):
        load_snapshot(bad_path)
