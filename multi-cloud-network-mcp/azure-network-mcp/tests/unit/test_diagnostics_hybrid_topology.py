from __future__ import annotations

from azure_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.hybrid_connectivity import (
    ExpressRouteCircuit,
    ExpressRouteConnection,
    ExpressRouteGateway,
    HubVirtualNetworkConnection,
    VirtualHub,
    VpnConnection,
    VpnGateway,
)
from azure_network_mcp.models.network_resources import VirtualNetwork
from azure_network_mcp.models.private_link import PrivateEndpoint

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


def _vnet(name: str) -> VirtualNetwork:
    return VirtualNetwork(
        resource_id=f"{BASE}/virtualNetworks/{name}",
        name=name,
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
    )


def _hub(name: str, *, is_route_server: bool = False) -> VirtualHub:
    return VirtualHub(
        resource_id=f"{BASE}/virtualHubs/{name}",
        name=name,
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        is_route_server=is_route_server,
    )


def test_vwan_hub_vnet_propagation_produces_an_edge() -> None:
    """vWAN propagation scenario: a hub-to-VNet connection joins the hub
    node to the VNet node with evidence."""
    hub = _hub("hub-1")
    vnet = _vnet("vnet-1")
    conn = HubVirtualNetworkConnection(
        resource_id=f"{BASE}/virtualHubs/hub-1/hubVirtualNetworkConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        virtual_hub_name="hub-1",
        remote_virtual_network_id=vnet.resource_id,
    )
    topology = build_hybrid_topology(
        _snapshot(
            virtual_hubs=[hub], virtual_networks=[vnet], hub_virtual_network_connections=[conn]
        )
    )

    node_ids = {n.node_id for n in topology.nodes}
    assert hub.resource_id in node_ids
    assert vnet.resource_id in node_ids
    edges = {(e.source_id, e.target_id, e.relationship) for e in topology.edges}
    assert (hub.resource_id, vnet.resource_id, "connected_to_vnet") in edges
    assert topology.warnings == []


def test_hub_connection_to_out_of_scope_vnet_produces_warning() -> None:
    """A hub connection referencing a VNet outside this resource group
    still produces an edge, with a completeness warning, not a silent gap."""
    hub = _hub("hub-1")
    remote_vnet_id = (
        f"/subscriptions/{SUB}/resourceGroups/rg-other/providers/Microsoft.Network/"
        "virtualNetworks/vnet-remote"
    )
    conn = HubVirtualNetworkConnection(
        resource_id=f"{BASE}/virtualHubs/hub-1/hubVirtualNetworkConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        virtual_hub_name="hub-1",
        remote_virtual_network_id=remote_vnet_id,
    )
    topology = build_hybrid_topology(
        _snapshot(virtual_hubs=[hub], hub_virtual_network_connections=[conn])
    )

    node_ids = {n.node_id for n in topology.nodes}
    assert remote_vnet_id not in node_ids
    edges = {(e.source_id, e.target_id) for e in topology.edges}
    assert (hub.resource_id, remote_vnet_id) in edges
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topology.warnings)


def test_route_server_hub_gets_route_server_node_type() -> None:
    """Route Server peers scenario: a standalone Route Server (is_route_server
    hub) is typed distinctly from a regular vWAN hub."""
    route_server = _hub("rs-1", is_route_server=True)
    topology = build_hybrid_topology(_snapshot(virtual_hubs=[route_server]))

    node = next(n for n in topology.nodes if n.node_id == route_server.resource_id)
    assert node.node_type == "route_server"


def test_vpn_gateway_connection_and_site_edges() -> None:
    hub = _hub("hub-1")
    gw = VpnGateway(
        resource_id=f"{BASE}/vpnGateways/gw-1",
        name="gw-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        virtual_hub_id=hub.resource_id,
    )
    conn = VpnConnection(
        resource_id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        vpn_gateway_name="gw-1",
        remote_vpn_site_id=f"{BASE}/vpnSites/site-1",
        connection_status="Connected",
    )
    topology = build_hybrid_topology(
        _snapshot(virtual_hubs=[hub], vpn_gateways=[gw], vpn_connections=[conn])
    )

    edges = {(e.source_id, e.target_id, e.relationship) for e in topology.edges}
    assert (hub.resource_id, gw.resource_id, "hub_has_vpn_gateway") in edges
    assert (gw.resource_id, conn.resource_id, "has_connection") in edges
    assert (conn.resource_id, f"{BASE}/vpnSites/site-1", "connects_to_site") in edges
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topology.warnings)


def test_express_route_gateway_circuit_connection_chain() -> None:
    """ExpressRoute states scenario at the topology level: gateway ->
    connection -> circuit chain is fully joined."""
    hub = _hub("hub-1")
    circuit = ExpressRouteCircuit(
        resource_id=f"{BASE}/expressRouteCircuits/circuit-1",
        name="circuit-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
    )
    gw = ExpressRouteGateway(
        resource_id=f"{BASE}/expressRouteGateways/ergw-1",
        name="ergw-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        virtual_hub_id=hub.resource_id,
    )
    conn = ExpressRouteConnection(
        resource_id=f"{BASE}/expressRouteGateways/ergw-1/expressRouteConnections/conn-1",
        name="conn-1",
        subscription_id=SUB,
        observed_at="now",
        express_route_gateway_name="ergw-1",
        express_route_circuit_peering_id=f"{circuit.resource_id}/peerings/AzurePrivatePeering",
    )
    topology = build_hybrid_topology(
        _snapshot(
            virtual_hubs=[hub],
            express_route_circuits=[circuit],
            express_route_gateways=[gw],
            express_route_connections=[conn],
        )
    )

    edges = {(e.source_id, e.target_id, e.relationship) for e in topology.edges}
    assert (hub.resource_id, gw.resource_id, "hub_has_express_route_gateway") in edges
    assert (gw.resource_id, conn.resource_id, "has_connection") in edges
    assert (conn.resource_id, circuit.resource_id, "connects_to_circuit") in edges


def test_private_endpoint_resides_in_subnet() -> None:
    """Private Endpoint DNS scenario: the topology joins a private endpoint
    to its subnet (the DNS-relevant association -- the private endpoint's
    presence in a subnet is what a Private DNS zone link resolves against)."""
    vnet = _vnet("vnet-1")
    subnet_id = f"{vnet.resource_id}/subnets/pe-subnet"
    from azure_network_mcp.models.network_resources import Subnet

    subnet = Subnet(
        resource_id=subnet_id,
        name="pe-subnet",
        subscription_id=SUB,
        observed_at="now",
    )
    pe = PrivateEndpoint(
        resource_id=f"{BASE}/privateEndpoints/pe-1",
        name="pe-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        subnet_id=subnet_id,
    )
    topology = build_hybrid_topology(
        _snapshot(virtual_networks=[vnet], subnets=[subnet], private_endpoints=[pe])
    )

    edges = {(e.source_id, e.target_id, e.relationship) for e in topology.edges}
    assert (pe.resource_id, subnet_id, "resides_in") in edges


def test_topology_ordering_is_deterministic() -> None:
    hub_a = _hub("hub-a")
    hub_b = _hub("hub-b")
    first = build_hybrid_topology(_snapshot(virtual_hubs=[hub_b, hub_a]))
    second = build_hybrid_topology(_snapshot(virtual_hubs=[hub_a, hub_b]))
    assert [n.node_id for n in first.nodes] == [n.node_id for n in second.nodes]
