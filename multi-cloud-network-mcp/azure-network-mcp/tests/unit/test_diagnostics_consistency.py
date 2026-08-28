from __future__ import annotations

import pytest

from azure_network_mcp.diagnostics.consistency import find_blackhole_routes, find_degraded_resources
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.hybrid_connectivity import (
    ExpressRouteCircuit,
    VirtualNetworkGatewayConnection,
    VpnConnection,
    VpnGateway,
)
from azure_network_mcp.models.network_resources import (
    NetworkInterface,
    Route,
    RouteTable,
    VirtualNetwork,
)

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


def test_vnet_with_failed_provisioning_state_is_flagged() -> None:
    vnet = VirtualNetwork(
        resource_id=f"{BASE}/virtualNetworks/vnet-1",
        name="vnet-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Failed",
    )
    findings = find_degraded_resources(_snapshot(virtual_networks=[vnet]))
    assert len(findings) == 1
    assert findings[0].rule_id == "CONSIST-001"
    assert findings[0].severity == "high"


def test_succeeded_resources_are_not_flagged() -> None:
    vnet = VirtualNetwork(
        resource_id=f"{BASE}/virtualNetworks/vnet-1",
        name="vnet-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Succeeded",
    )
    findings = find_degraded_resources(_snapshot(virtual_networks=[vnet]))
    assert findings == []


@pytest.mark.parametrize("status", ["Disconnected", "NotConnected", "Degraded", "Unknown"])
def test_unhealthy_vpn_connection_status_is_flagged(status: str) -> None:
    """S2S VPN/BGP degradation scenario per the milestone's named test coverage."""
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        connection_status=status,
    )
    findings = find_degraded_resources(_snapshot(vpn_connections=[conn]))
    assert len(findings) == 1
    assert "connection_status" in findings[0].evidence[0].detail


def test_connected_vpn_connection_is_not_flagged() -> None:
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        connection_status="Connected",
    )
    findings = find_degraded_resources(_snapshot(vpn_connections=[conn]))
    assert findings == []


def test_unhealthy_classic_gateway_connection_is_flagged() -> None:
    conn = VirtualNetworkGatewayConnection(
        resource_id=f"{BASE}/connections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        connection_status="Disconnected",
    )
    findings = find_degraded_resources(_snapshot(virtual_network_gateway_connections=[conn]))
    assert len(findings) == 1


def test_degraded_express_route_circuit_is_flagged() -> None:
    """ExpressRoute states scenario per the milestone's named test coverage."""
    circuit = ExpressRouteCircuit(
        resource_id=f"{BASE}/expressRouteCircuits/circuit-1",
        name="circuit-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Failed",
    )
    findings = find_degraded_resources(_snapshot(express_route_circuits=[circuit]))
    assert len(findings) == 1
    assert "express_route_circuit" in findings[0].summary


def test_multiple_degraded_resources_all_reported() -> None:
    gw = VpnGateway(
        resource_id=f"{BASE}/vpnGateways/gw-1",
        name="gw-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Updating",
    )
    circuit = ExpressRouteCircuit(
        resource_id=f"{BASE}/expressRouteCircuits/circuit-1",
        name="circuit-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        provisioning_state="Failed",
    )
    findings = find_degraded_resources(
        _snapshot(vpn_gateways=[gw], express_route_circuits=[circuit])
    )
    assert len(findings) == 2


def _route_table(routes: list[Route]) -> RouteTable:
    return RouteTable(
        resource_id=f"{BASE}/routeTables/rt-1",
        name="rt-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        routes=routes,
    )


def test_blackhole_route_is_flagged() -> None:
    rt = _route_table([Route(name="r1", address_prefix="10.1.0.0/24", next_hop_type="None")])
    findings = find_blackhole_routes(_snapshot(route_tables=[rt]))
    assert len(findings) == 1
    assert findings[0].rule_id == "CONSIST-002"
    assert findings[0].confidence == "high"


def test_virtual_appliance_route_to_known_nic_is_not_flagged() -> None:
    """Asymmetric UDR scenario, healthy case: the NVA next hop matches a
    real NIC in this snapshot -- not a risk."""
    nic = NetworkInterface(
        resource_id=f"{BASE}/networkInterfaces/nva-nic",
        name="nva-nic",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        ip_configurations=[
            {
                "name": "ipconfig1",
                "private_ip_address": "10.0.0.4",
                "subnet_id": f"{BASE}/virtualNetworks/vnet-1/subnets/nva-subnet",
            }
        ],
    )
    rt = _route_table(
        [
            Route(
                name="r1",
                address_prefix="0.0.0.0/0",
                next_hop_type="VirtualAppliance",
                next_hop_ip_address="10.0.0.4",
            )
        ]
    )
    findings = find_blackhole_routes(_snapshot(route_tables=[rt], network_interfaces=[nic]))
    assert findings == []


def test_virtual_appliance_route_to_unknown_ip_is_indeterminate() -> None:
    """Asymmetric/orphaned UDR scenario: the NVA next hop matches no known
    NIC -- flagged, but only as indeterminate since the NVA may live
    outside this resource group's scope."""
    rt = _route_table(
        [
            Route(
                name="r1",
                address_prefix="0.0.0.0/0",
                next_hop_type="VirtualAppliance",
                next_hop_ip_address="10.0.0.99",
            )
        ]
    )
    findings = find_blackhole_routes(_snapshot(route_tables=[rt], network_interfaces=[]))
    assert len(findings) == 1
    assert findings[0].confidence == "indeterminate"


def test_vnet_local_route_is_never_flagged() -> None:
    rt = _route_table([Route(name="r1", address_prefix="10.0.0.0/16", next_hop_type="VnetLocal")])
    findings = find_blackhole_routes(_snapshot(route_tables=[rt]))
    assert findings == []
