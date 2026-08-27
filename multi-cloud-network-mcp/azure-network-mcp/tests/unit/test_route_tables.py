from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.route_tables import get_effective_route_table, list_route_tables

RT_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/routeTables/rt-1"
)


def _route(name: str, next_hop_type: str, next_hop_ip: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        address_prefix="10.1.0.0/24",
        next_hop_type=next_hop_type,
        next_hop_ip_address=next_hop_ip,
        provisioning_state="Succeeded",
    )


def _route_table(routes: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id=RT_ID,
        name="rt-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        routes=routes,
        subnets=[],
        disable_bgp_route_propagation=False,
    )


@pytest.mark.parametrize(
    "next_hop_type",
    ["VirtualAppliance", "VnetLocal", "Internet", "None", "VirtualNetworkGateway"],
)
def test_list_route_tables_normalizes_every_udr_next_hop_type(
    client_factory: ClientFactory, network_client: MagicMock, next_hop_type: str
) -> None:
    network_client.route_tables.list_all.return_value = make_pageable(
        [_route_table([_route("r1", next_hop_type, next_hop_ip="10.0.0.4")])]
    )

    result = list_route_tables(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].routes[0].next_hop_type == next_hop_type


def test_list_route_tables_scoped_to_resource_group(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.route_tables.list.return_value = make_pageable([_route_table([])])

    list_route_tables(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    network_client.route_tables.list.assert_called_once_with(resource_group_name=RESOURCE_GROUP)


def test_get_effective_route_table_resolves_lro_and_normalizes(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    poller = MagicMock()
    poller.result.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                name="effective-1",
                address_prefix=["10.0.0.0/24"],
                next_hop_type="VnetLocal",
                next_hop_ip_address=[],
                source="Default",
                state="Active",
            )
        ]
    )
    network_client.network_interfaces.begin_get_effective_route_table.return_value = poller

    result = get_effective_route_table(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
    )

    assert len(result) == 1
    assert result[0].source == "Default"
    assert result[0].state == "Active"
    assert result[0].address_prefixes == ["10.0.0.0/24"]
    network_client.network_interfaces.begin_get_effective_route_table.assert_called_once_with(
        resource_group_name=RESOURCE_GROUP, network_interface_name="nic-1"
    )
