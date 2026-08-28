from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.diagnostics.health import MAX_METRIC_RESOURCES, get_network_health
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.hybrid_connectivity import VirtualNetworkGateway, VpnConnection
from azure_network_mcp.models.network_resources import VirtualNetwork

SUB = SUBSCRIPTION_ID
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


def test_get_network_health_counts_degraded_and_unhealthy() -> None:
    vnet = VirtualNetwork(
        resource_id=f"{BASE}/virtualNetworks/vnet-1",
        name="vnet-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Failed",
    )
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        connection_status="Disconnected",
    )
    report = get_network_health(_snapshot(virtual_networks=[vnet], vpn_connections=[conn]))

    assert report.degraded_resource_count == 1
    assert report.unhealthy_connection_count == 1
    assert report.total_resources_checked == 2  # 1 VNet + 1 VPN connection


def test_get_network_health_without_metrics_by_default() -> None:
    report = get_network_health(_snapshot())
    assert report.metrics == []


def test_get_network_health_include_metrics_without_client_factory_warns() -> None:
    report = get_network_health(_snapshot(), include_metrics=True, client_factory=None)
    assert any(w.code == "METRICS_UNAVAILABLE" for w in report.warnings)


def test_get_network_health_include_metrics_queries_bounded_resources(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    gateways = [
        VirtualNetworkGateway(
            resource_id=f"{BASE}/virtualNetworkGateways/vng-{i}",
            name=f"vng-{i}",
            subscription_id=SUB,
            resource_group=RG,
            observed_at="now",
        )
        for i in range(MAX_METRIC_RESOURCES + 2)
    ]
    network_client.metrics = MagicMock()
    client_factory._monitor_clients[SUB] = MagicMock()
    client_factory._monitor_clients[SUB].metrics.list.return_value = SimpleNamespace(value=[])

    report = get_network_health(
        _snapshot(virtual_network_gateways=gateways),
        client_factory=client_factory,
        include_metrics=True,
    )

    assert len(report.metrics) == MAX_METRIC_RESOURCES
    assert any(w.code == "FANOUT_CAP_REACHED" for w in report.warnings)
