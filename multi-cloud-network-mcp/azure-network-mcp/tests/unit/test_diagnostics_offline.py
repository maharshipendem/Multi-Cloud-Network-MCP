"""Offline dry-run tests: load the demo fixture and run the diagnostics
engine against it with zero Azure calls, then confirm it reproduces
several findings at once, exactly as a real (mocked) collection would."""

from __future__ import annotations

from pathlib import Path

from azure_network_mcp.diagnostics.exposure import find_exposed_network_interfaces
from azure_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from azure_network_mcp.diagnostics.offline import load_snapshot_from_file
from azure_network_mcp.diagnostics.risks import find_network_risks

FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "demo_hybrid_snapshot.json"


def test_load_snapshot_from_file_makes_no_azure_calls() -> None:
    snapshot = load_snapshot_from_file(FIXTURE_PATH)
    assert snapshot.resource_group == "rg-demo-network"
    assert len(snapshot.virtual_networks) == 1


def test_offline_snapshot_reproduces_exposure_finding() -> None:
    snapshot = load_snapshot_from_file(FIXTURE_PATH)
    findings = find_exposed_network_interfaces(snapshot)
    assert len(findings) == 1
    assert findings[0].severity == "high"  # port 22 is sensitive


def test_offline_snapshot_reproduces_multiple_risk_findings_at_once() -> None:
    snapshot = load_snapshot_from_file(FIXTURE_PATH)
    findings = find_network_risks(snapshot)
    rule_ids = {f.rule_id for f in findings}
    assert "EXPOSE-001" in rule_ids  # public SSH exposure
    assert "CONSIST-001" in rule_ids  # disconnected VPN connection
    assert "CONSIST-002" in rule_ids  # blackhole route


def test_offline_snapshot_builds_a_topology() -> None:
    snapshot = load_snapshot_from_file(FIXTURE_PATH)
    topology = build_hybrid_topology(snapshot)
    node_types = {n.node_type for n in topology.nodes}
    assert "virtual_network" in node_types
    assert "vpn_gateway" in node_types
