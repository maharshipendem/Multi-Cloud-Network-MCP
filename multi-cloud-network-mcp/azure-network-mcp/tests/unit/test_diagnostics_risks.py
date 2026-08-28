from __future__ import annotations

from azure_network_mcp.diagnostics.risks import find_network_risks
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.hybrid_connectivity import VpnConnection
from azure_network_mcp.models.network_resources import Route, RouteTable

SUB = "11111111-1111-1111-1111-111111111111"
RG = "rg-test"
BASE = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network"


def _snapshot(**overrides: object) -> HybridNetworkSnapshot:
    defaults: dict[str, object] = {
        "subscription_id": SUB,
        "resource_group": RG,
        "observed_at": "now",
    }
    defaults.update(overrides)
    return HybridNetworkSnapshot(**defaults)  # type: ignore[arg-type]


def test_find_network_risks_combines_all_rule_categories() -> None:
    rt = RouteTable(
        resource_id=f"{BASE}/routeTables/rt-1",
        name="rt-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        routes=[Route(name="r1", address_prefix="10.1.0.0/24", next_hop_type="None")],
    )
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        connection_status="Disconnected",
    )
    findings = find_network_risks(_snapshot(route_tables=[rt], vpn_connections=[conn]))

    rule_ids = {f.rule_id for f in findings}
    assert "CONSIST-001" in rule_ids
    assert "CONSIST-002" in rule_ids


def test_find_network_risks_filters_by_min_severity() -> None:
    rt = RouteTable(
        resource_id=f"{BASE}/routeTables/rt-1",
        name="rt-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        routes=[Route(name="r1", address_prefix="10.1.0.0/24", next_hop_type="None")],  # medium
    )
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        connection_status="Disconnected",  # high
    )
    findings = find_network_risks(
        _snapshot(route_tables=[rt], vpn_connections=[conn]), min_severity="high"
    )

    assert all(f.severity in {"high", "critical"} for f in findings)
    assert any(f.rule_id == "CONSIST-001" for f in findings)
    assert not any(f.rule_id == "CONSIST-002" for f in findings)


def test_find_network_risks_empty_snapshot_returns_no_findings() -> None:
    assert find_network_risks(_snapshot()) == []
