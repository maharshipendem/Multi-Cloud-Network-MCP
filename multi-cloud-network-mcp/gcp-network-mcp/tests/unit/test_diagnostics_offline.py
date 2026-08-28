"""Unit tests for ``diagnostics.offline`` -- ``load_snapshot`` (accepting
a dict, a ``Path``, or a raw JSON string) and ``analyze_offline_snapshot``
(the full offline diagnostics-engine entrypoint)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gcp_network_mcp.diagnostics.offline import analyze_offline_snapshot, load_snapshot
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot

PROJECT_ID = "test-project-1"
FRESHNESS = "2026-01-01T00:00:00Z"


def _snapshot_dict(**overrides: object) -> dict:
    base = {"project_id": PROJECT_ID, "observed_at": FRESHNESS}
    base.update(overrides)
    return base


def test_load_snapshot_from_dict() -> None:
    snapshot = load_snapshot(_snapshot_dict())
    assert isinstance(snapshot, HybridNetworkSnapshot)
    assert snapshot.project_id == PROJECT_ID
    assert snapshot.observed_at == FRESHNESS


def test_load_snapshot_from_raw_json_string() -> None:
    raw = json.dumps(_snapshot_dict())
    snapshot = load_snapshot(raw)
    assert snapshot.project_id == PROJECT_ID


def test_load_snapshot_from_raw_json_string_tolerates_leading_whitespace() -> None:
    raw = "   \n" + json.dumps(_snapshot_dict())
    snapshot = load_snapshot(raw)
    assert snapshot.project_id == PROJECT_ID


def test_load_snapshot_from_path(tmp_path: Path) -> None:
    file_path = tmp_path / "snapshot.json"
    file_path.write_text(json.dumps(_snapshot_dict()))

    snapshot = load_snapshot(file_path)

    assert snapshot.project_id == PROJECT_ID


def test_load_snapshot_from_string_path_to_existing_file(tmp_path: Path) -> None:
    """A plain (non-JSON-looking) string is treated as a file path, same
    as passing a ``Path`` directly."""
    file_path = tmp_path / "snapshot.json"
    file_path.write_text(json.dumps(_snapshot_dict()))

    snapshot = load_snapshot(str(file_path))

    assert snapshot.project_id == PROJECT_ID


def test_load_snapshot_rejects_malformed_json_dict() -> None:
    with pytest.raises(ValidationError):
        load_snapshot({"project_id": PROJECT_ID})  # missing required observed_at


def test_load_snapshot_long_garbage_string_raises_clean_value_error_not_oserror() -> None:
    """Regression test: a long string that is neither valid JSON (doesn't
    start with '{') nor a real file path must not leak a raw, platform-
    specific ``OSError`` (e.g. ``OSError: [Errno 36]``/``[Errno 63] File
    name too long``) out of ``load_snapshot`` -- it must raise a clean,
    expected ``ValueError`` instead."""
    garbage = "x" * 5000

    with pytest.raises(ValueError) as exc_info:
        load_snapshot(garbage)

    assert not isinstance(exc_info.value, OSError)


def test_load_snapshot_missing_but_path_shaped_file_still_raises_clean_error(
    tmp_path: Path,
) -> None:
    """A short, plausible-looking path that simply doesn't exist should
    also raise the same clean ``ValueError`` (wrapping the underlying
    ``FileNotFoundError``), not propagate a raw ``OSError`` subclass."""
    missing = tmp_path / "does-not-exist.json"

    with pytest.raises(ValueError):
        load_snapshot(str(missing))


def test_analyze_offline_snapshot_bundles_risks_topology_and_health() -> None:
    """One end-to-end test: loading a snapshot dict and analyzing it
    returns the snapshot, its risk findings, its topology, and its
    health report -- the same objects ``find_network_risks``/
    ``build_hybrid_topology``/``get_network_health`` would produce if
    called directly against the loaded snapshot."""
    network_self_link = (
        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
    )
    data = _snapshot_dict(
        networks=[
            {
                "self_link": network_self_link,
                "name": "vpc-1",
                "project_id": PROJECT_ID,
                "mode": "auto",
                "observed_at": FRESHNESS,
            }
        ],
        peerings=[
            {
                "name": "peer-1",
                "owning_network_self_link": network_self_link,
                "network": (
                    "https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x"
                ),
                "state": "INACTIVE",
            }
        ],
    )

    snapshot, findings, topology, health = analyze_offline_snapshot(data)

    assert isinstance(snapshot, HybridNetworkSnapshot)
    assert snapshot.project_id == PROJECT_ID

    # risks: the INACTIVE peering triggers a PEER-001 finding, plus the
    # FW-002 "no hierarchical policies supplied" advisory (network present).
    rule_ids = {f.rule_id for f in findings}
    assert "PEER-001" in rule_ids
    assert "FW-002" in rule_ids

    # topology: the network is a node.
    assert any(n.node_id == network_self_link for n in topology.nodes)

    # health: bundles the exact same findings, with a matching overall_status.
    assert {f.rule_id for f in health.findings} == rule_ids
    assert health.overall_status == "degraded"  # PEER-001 non-ACTIVE peering is high-severity
    assert health.resource_counts.networks == 1


def test_analyze_offline_snapshot_accepts_a_json_string_too(tmp_path: Path) -> None:
    raw = json.dumps(_snapshot_dict())
    snapshot, findings, topology, health = analyze_offline_snapshot(raw)
    assert snapshot.project_id == PROJECT_ID
    assert findings == []
    assert topology.nodes == []
    assert health.overall_status == "healthy"


# --- Golden test: the sanitized multi-scenario fixture -----------------

_FIXTURE_PATH = (
    Path(__file__).parent.parent.parent / "fixtures" / "hybrid_diagnostics_scenarios.json"
)


def test_hybrid_diagnostics_scenarios_fixture_produces_the_expected_findings() -> None:
    """Golden-test reasoning over the sanitized ``fixtures/hybrid_diagnostics_scenarios.json``
    snapshot, which was built by running real GCP SDK objects through the
    real ``gcp/*.py`` normalizers rather than hand-authored JSON (see
    ``fixtures/README.md``), so it's guaranteed schema-valid. It packs
    one instance of every
    milestone-8 scenario category into a single project: NCC propagation,
    HA VPN redundancy, BGP route preference/degradation, Interconnect
    states, Shared VPC, hierarchical Firewall Policy visibility gap, VPC
    peering route import/export limitations, Cloud NAT egress, an
    unknown-next-hop route, overlapping CIDR routes, public forwarding
    rule exposure, split-horizon DNS (evaluated at indeterminate
    confidence, by design), and partial-IAM/API-disabled/throttling/
    stale-monitoring-data collection warnings. If a rule's logic changes
    in a way that changes its verdict on this unchanged input, this test
    is meant to catch it."""
    snapshot, findings, topology, health = analyze_offline_snapshot(_FIXTURE_PATH)

    rule_ids = {f.rule_id for f in findings}
    assert rule_ids == {
        "PEER-001",
        "NAT-001",
        "ROUTE-002",
        "NCC-001",
        "HYBRID-001",
        "HYBRID-002",
        "HYBRID-003",
        "DNS-001",
        "EXPOSE-001",
        "FW-002",
    }

    # NAT-001: MANUAL_ONLY allocation with zero IPs is critical.
    nat_findings = [f for f in findings if f.rule_id == "NAT-001"]
    assert any(f.severity == "critical" for f in nat_findings)

    # DNS-001: one zone with name servers (indeterminate forwarding-chain
    # confidence) and one with none (high confidence, the one fact this
    # rule can check directly).
    dns_findings = [f for f in findings if f.rule_id == "DNS-001"]
    assert len(dns_findings) == 2
    assert {f.confidence for f in dns_findings} == {"indeterminate", "high"}

    # HYBRID-003: one degraded peer (zero learned routes) among two.
    bgp_findings = [f for f in findings if f.rule_id == "HYBRID-003"]
    assert len(bgp_findings) == 1
    assert bgp_findings[0].confidence == "medium"

    # Redaction survives a full round trip through JSON and back.
    assert "never-returned" not in str(snapshot)
    tunnel_by_name = {t.name: t for t in snapshot.vpn_tunnels}
    assert tunnel_by_name["tunnel-1"].redacted is True
    attachment_by_name = {a.name: a for a in snapshot.interconnect_attachments}
    assert attachment_by_name["attach-primary"].redacted is True

    # Every finding stays a first-class, fully-qualified citizen -- never
    # missing the fields the milestone spec requires on every finding.
    for finding in findings:
        assert finding.severity
        assert finding.confidence
        assert finding.evidence, f"{finding.rule_id} finding has no evidence"

    assert topology.completeness == "partial"  # snapshot.warnings is non-empty
    assert health.overall_status == "critical"
    assert health.collection_warning_count == len(snapshot.warnings) == 4
