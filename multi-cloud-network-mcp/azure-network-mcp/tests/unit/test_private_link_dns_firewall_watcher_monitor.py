from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.firewall import list_azure_firewalls
from azure_network_mcp.arm.monitor import KNOWN_NETWORK_METRICS, get_metrics
from azure_network_mcp.arm.network_watcher import get_network_topology, list_network_watchers
from azure_network_mcp.arm.private_dns import list_private_dns_record_sets, list_private_dns_zones
from azure_network_mcp.arm.private_link import list_private_endpoints
from azure_network_mcp.exceptions import ToolExecutionError

BASE = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network"
)


def test_list_private_endpoints_normalizes_connections(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.private_endpoints.list_by_subscription.return_value = make_pageable(
        [
            SimpleNamespace(
                id=f"{BASE}/privateEndpoints/pe-1",
                name="pe-1",
                location="eastus",
                provisioning_state="Succeeded",
                tags={},
                subnet=SimpleNamespace(id="subnet-1"),
                network_interfaces=[SimpleNamespace(id="nic-1")],
                private_link_service_connections=[
                    SimpleNamespace(
                        name="conn-1",
                        private_link_service_id="pls-1",
                        group_ids=["blob"],
                        private_link_service_connection_state=SimpleNamespace(status="Approved"),
                    )
                ],
                manual_private_link_service_connections=[],
            )
        ]
    )

    result = list_private_endpoints(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].subnet_id == "subnet-1"
    assert result[0].private_link_service_connections[0].connection_state == "Approved"


def test_list_private_dns_zones_and_record_sets(
    client_factory: ClientFactory,
) -> None:
    from unittest.mock import MagicMock as _M

    mock_client = _M()
    client_factory._private_dns_clients[SUBSCRIPTION_ID] = mock_client
    mock_client.private_zones.list.return_value = make_pageable(
        [
            SimpleNamespace(
                id=f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network/privateDnsZones/contoso.internal",
                name="contoso.internal",
                location="global",
                provisioning_state="Succeeded",
                tags={},
                number_of_record_sets=3,
                number_of_virtual_network_links=1,
            )
        ]
    )
    mock_client.record_sets.list.return_value = make_pageable(
        [
            SimpleNamespace(
                id=f"{BASE}/privateDnsZones/contoso.internal/A/www",
                name="www",
                ttl=300,
                a_records=[SimpleNamespace(ipv4_address="10.0.0.5")],
                aaaa_records=[],
                mx_records=[],
                ptr_records=[],
                srv_records=[],
                txt_records=[],
                cname_record=None,
                soa_record=None,
            )
        ]
    )

    zones = list_private_dns_zones(client_factory, subscription_id=SUBSCRIPTION_ID)
    assert zones[0].name == "contoso.internal"

    records = list_private_dns_record_sets(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        zone_name="contoso.internal",
    )
    assert records[0].values == ["10.0.0.5"]


def test_list_azure_firewalls_extracts_public_ips(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.azure_firewalls.list_all.return_value = make_pageable(
        [
            SimpleNamespace(
                id=f"{BASE}/azureFirewalls/fw-1",
                name="fw-1",
                location="eastus",
                provisioning_state="Succeeded",
                tags={},
                sku=SimpleNamespace(name="AZFW_VNet", tier="Standard"),
                threat_intel_mode="Alert",
                virtual_hub=None,
                firewall_policy=SimpleNamespace(id=f"{BASE}/firewallPolicies/policy-1"),
                ip_configurations=[SimpleNamespace(name="ipconfig1")],
                hub_ip_addresses=SimpleNamespace(
                    public_i_ps=SimpleNamespace(addresses=[SimpleNamespace(address="20.1.2.3")])
                ),
            )
        ]
    )

    result = list_azure_firewalls(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].hub_ip_addresses == ["20.1.2.3"]
    assert result[0].ip_configuration_count == 1


def test_get_network_topology_constructs_topology_parameters(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.network_watchers.get_topology.return_value = SimpleNamespace(
        created_date_time=datetime(2026, 1, 1, tzinfo=UTC),
        last_modified=datetime(2026, 1, 2, tzinfo=UTC),
        resources=[
            SimpleNamespace(
                name="vnet-1",
                id=f"{BASE}/virtualNetworks/vnet-1",
                location="eastus",
                associations=[
                    SimpleNamespace(
                        name="subnet-1", resource_id="subnet-id-1", association_type="Associated"
                    )
                ],
            )
        ],
    )

    result = get_network_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_watcher_name="watcher-1",
        target_resource_group=RESOURCE_GROUP,
    )

    assert result.resources[0].name == "vnet-1"
    assert result.resources[0].associations[0].associated_resource_id == "subnet-id-1"
    call_kwargs = network_client.network_watchers.get_topology.call_args.kwargs
    assert call_kwargs["parameters"].target_resource_group_name == RESOURCE_GROUP


def test_list_network_watchers_scoped_to_resource_group(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.network_watchers.list.return_value = make_pageable([])
    list_network_watchers(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )
    network_client.network_watchers.list.assert_called_once_with(resource_group_name=RESOURCE_GROUP)


def test_get_metrics_raises_for_unknown_resource_type(client_factory: ClientFactory) -> None:
    with pytest.raises(ToolExecutionError):
        get_metrics(
            client_factory,
            subscription_id=SUBSCRIPTION_ID,
            resource_id=f"{BASE}/virtualNetworks/vnet-1",
        )


def test_get_metrics_queries_known_catalog_and_bounds_datapoints(
    client_factory: ClientFactory,
) -> None:
    mock_client = MagicMock()
    client_factory._monitor_clients[SUBSCRIPTION_ID] = mock_client
    resource_id = f"{BASE}/virtualNetworkGateways/vng-1"

    mock_client.metrics.list.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                name=SimpleNamespace(value="TunnelAverageBandwidth"),
                unit="BytesPerSecond",
                timeseries=[
                    SimpleNamespace(
                        data=[
                            SimpleNamespace(
                                time_stamp=datetime(2026, 1, 1, tzinfo=UTC),
                                average=100.0,
                                minimum=50.0,
                                maximum=150.0,
                                total=None,
                                count=None,
                            )
                        ]
                    )
                ],
            )
        ]
    )

    result = get_metrics(client_factory, subscription_id=SUBSCRIPTION_ID, resource_id=resource_id)

    assert result.series[0].metric_name == "TunnelAverageBandwidth"
    assert result.series[0].data_points[0].average == 100.0
    assert result.stale is False
    call_kwargs = mock_client.metrics.list.call_args.kwargs
    assert set(call_kwargs["metricnames"].split(",")) == set(
        KNOWN_NETWORK_METRICS["microsoft.network/virtualnetworkgateways"]
    )


def test_get_metrics_flags_stale_when_no_datapoints(client_factory: ClientFactory) -> None:
    mock_client = MagicMock()
    client_factory._monitor_clients[SUBSCRIPTION_ID] = mock_client
    resource_id = f"{BASE}/loadBalancers/lb-1"
    mock_client.metrics.list.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(name=SimpleNamespace(value="ByteCount"), unit="Count", timeseries=[])
        ]
    )

    result = get_metrics(client_factory, subscription_id=SUBSCRIPTION_ID, resource_id=resource_id)

    assert result.stale is True
