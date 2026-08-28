from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.expressroute import (
    list_express_route_circuits,
    list_express_route_connections,
    list_express_route_gateways,
)
from azure_network_mcp.arm.route_server import list_route_servers
from azure_network_mcp.arm.virtual_wan import list_virtual_hubs, list_virtual_wans
from azure_network_mcp.arm.vpn import (
    list_virtual_network_gateway_connections,
    list_vpn_connections,
    list_vpn_sites,
)

BASE = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network"
)


def _wan() -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/virtualWans/wan-1",
        name="wan-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        disable_vpn_encryption=False,
        allow_branch_to_branch_traffic=True,
        office365_local_breakout_category=None,
        virtual_hubs=[SimpleNamespace(id=f"{BASE}/virtualHubs/hub-1")],
        vpn_sites=[],
    )


def test_list_virtual_wans_normalizes_hub_ids(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_wans.list.return_value = make_pageable([_wan()])

    result = list_virtual_wans(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].name == "wan-1"
    assert result[0].virtual_hub_ids == [f"{BASE}/virtualHubs/hub-1"]


def _hub(*, sku: str, virtual_wan: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/virtualHubs/hub-1",
        name="hub-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        virtual_wan=SimpleNamespace(id=f"{BASE}/virtualWans/wan-1") if virtual_wan else None,
        address_prefix="10.100.0.0/24",
        sku=sku,
        routing_state="Provisioned",
        virtual_router_asn=65515,
        virtual_router_ips=["10.100.0.4", "10.100.0.5"],
        allow_branch_to_branch_traffic=True,
        hub_routing_preference="ExpressRoute",
    )


def test_list_virtual_hubs_marks_route_server(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_hubs.list.return_value = make_pageable(
        [_hub(sku="Standard", virtual_wan=False), _hub(sku="Basic", virtual_wan=True)]
    )

    result = list_virtual_hubs(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].is_route_server is True
    assert result[1].is_route_server is False


def test_list_route_servers_filters_to_standalone_hubs(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_hubs.list.return_value = make_pageable(
        [_hub(sku="Standard", virtual_wan=False), _hub(sku="Basic", virtual_wan=True)]
    )

    result = list_route_servers(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert len(result) == 1
    assert result[0].sku == "Standard"


def _vpn_site() -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/vpnSites/site-1",
        name="site-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        virtual_wan=None,
        device_properties=SimpleNamespace(device_vendor="Cisco", device_model="ASR1001"),
        ip_address="20.1.2.3",
        site_key="THIS-MUST-NEVER-BE-READ",
        address_space=SimpleNamespace(address_prefixes=["192.168.0.0/24"]),
        is_security_site=False,
        vpn_site_links=[
            SimpleNamespace(
                name="link-1",
                ip_address="20.1.2.3",
                link_properties=SimpleNamespace(link_speed_in_mbps=50, link_provider_name="ISP"),
            )
        ],
    )


def test_list_vpn_sites_never_reads_site_key(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.vpn_sites.list.return_value = make_pageable([_vpn_site()])

    result = list_vpn_sites(client_factory, subscription_id=SUBSCRIPTION_ID)

    site = result[0]
    assert site.redacted is True
    assert "site_key" not in site.model_dump()
    assert "THIS-MUST-NEVER-BE-READ" not in str(site.model_dump())
    assert site.links[0].link_speed_in_mbps == 50


def _vpn_connection() -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/vpnGateways/gw-1/vpnConnections/conn-1",
        name="conn-1",
        provisioning_state="Succeeded",
        remote_vpn_site=SimpleNamespace(id=f"{BASE}/vpnSites/site-1"),
        connection_status="Connected",
        vpn_connection_protocol_type="IKEv2",
        enable_bgp=True,
        routing_weight=0,
        ingress_bytes_transferred=1024,
        egress_bytes_transferred=2048,
        shared_key="THIS-MUST-NEVER-BE-READ",
    )


def test_list_vpn_connections_never_reads_shared_key(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.vpn_connections.list_by_vpn_gateway.return_value = make_pageable(
        [_vpn_connection()]
    )

    result = list_vpn_connections(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        vpn_gateway_name="gw-1",
    )

    conn = result[0]
    assert conn.redacted is True
    assert "shared_key" not in conn.model_dump()
    assert "THIS-MUST-NEVER-BE-READ" not in str(conn.model_dump())
    assert conn.connection_status == "Connected"


def _vnet_gateway_connection() -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/connections/conn-1",
        name="conn-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        virtual_network_gateway1=SimpleNamespace(id=f"{BASE}/virtualNetworkGateways/vng-1"),
        virtual_network_gateway2=None,
        local_network_gateway2=SimpleNamespace(id=f"{BASE}/localNetworkGateways/lng-1"),
        connection_type="IPsec",
        connection_status="Connected",
        enable_bgp=False,
        routing_weight=0,
        ingress_bytes_transferred=0,
        egress_bytes_transferred=0,
        authorization_key="THIS-MUST-NEVER-BE-READ",
        shared_key="THIS-MUST-NEVER-BE-READ-EITHER",
    )


def test_list_virtual_network_gateway_connections_never_reads_secrets(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_network_gateway_connections.list.return_value = make_pageable(
        [_vnet_gateway_connection()]
    )

    result = list_virtual_network_gateway_connections(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    conn = result[0]
    dumped = str(conn.model_dump())
    assert "THIS-MUST-NEVER-BE-READ" not in dumped
    assert conn.redacted is True


def _circuit() -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{BASE}/expressRouteCircuits/circuit-1",
        name="circuit-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        sku=SimpleNamespace(name="Standard", tier="Standard", family="MeteredData"),
        circuit_provisioning_state="Enabled",
        service_provider_provisioning_state="Provisioned",
        service_provider_properties=SimpleNamespace(
            service_provider_name="Equinix",
            peering_location="Silicon Valley",
            bandwidth_in_mbps=1000,
        ),
        express_route_port=None,
        global_reach_enabled=False,
        authorization_key="THIS-MUST-NEVER-BE-READ",
        service_key="THIS-MUST-NEVER-BE-READ-EITHER",
        peerings=[],
    )


def test_list_express_route_circuits_never_reads_keys(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.express_route_circuits.list_all.return_value = make_pageable([_circuit()])

    result = list_express_route_circuits(client_factory, subscription_id=SUBSCRIPTION_ID)

    circuit = result[0]
    dumped = str(circuit.model_dump())
    assert "THIS-MUST-NEVER-BE-READ" not in dumped
    assert circuit.redacted is True
    assert circuit.service_provider_name == "Equinix"


def test_list_express_route_gateways_unwraps_non_paginated_list_wrapper(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.express_route_gateways.list_by_subscription.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                id=f"{BASE}/expressRouteGateways/gw-1",
                name="gw-1",
                location="eastus",
                provisioning_state="Succeeded",
                tags={},
                virtual_hub=SimpleNamespace(id=f"{BASE}/virtualHubs/hub-1"),
                auto_scale_configuration=SimpleNamespace(bounds=SimpleNamespace(min=2, max=10)),
                allow_non_virtual_wan_traffic=False,
            )
        ]
    )

    result = list_express_route_gateways(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].name == "gw-1"
    assert result[0].min_scale_units == 2
    assert result[0].max_scale_units == 10
    network_client.express_route_gateways.list_by_subscription.assert_called_once()


def test_list_express_route_connections_never_reads_authorization_key(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.express_route_connections.list.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                id=f"{BASE}/expressRouteGateways/gw-1/expressRouteConnections/conn-1",
                name="conn-1",
                provisioning_state="Succeeded",
                express_route_circuit_peering=SimpleNamespace(
                    id=f"{BASE}/expressRouteCircuits/circuit-1/peerings/AzurePrivatePeering"
                ),
                routing_weight=0,
                enable_internet_security=False,
                authorization_key="THIS-MUST-NEVER-BE-READ",
            )
        ]
    )

    result = list_express_route_connections(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        express_route_gateway_name="gw-1",
    )

    assert "THIS-MUST-NEVER-BE-READ" not in str(result[0].model_dump())
    assert result[0].redacted is True
