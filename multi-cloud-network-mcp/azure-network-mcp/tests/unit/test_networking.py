from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.networking import list_subnets, list_virtual_networks

VNET_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/virtualNetworks/vnet-1"
)
SUBNET_ID = f"{VNET_ID}/subnets/subnet-a"
NSG_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/networkSecurityGroups/nsg-1"
)
RT_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/routeTables/rt-1"
)
NAT_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/natGateways/nat-1"
)


def _vnet() -> SimpleNamespace:
    return SimpleNamespace(
        id=VNET_ID,
        name="vnet-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={"env": "prod"},
        address_space=SimpleNamespace(address_prefixes=["10.0.0.0/16"]),
        dhcp_options=SimpleNamespace(dns_servers=["10.0.0.4"]),
        subnets=[SimpleNamespace(id=SUBNET_ID)],
        virtual_network_peerings=[
            SimpleNamespace(
                name="peer-1",
                remote_virtual_network=SimpleNamespace(id="remote-vnet-id"),
                peering_state="Connected",
            )
        ],
        enable_ddos_protection=False,
    )


def _subnet(*, nsg: bool = True, route_table: bool = True, nat: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=SUBNET_ID,
        name="subnet-a",
        provisioning_state="Succeeded",
        address_prefix="10.0.1.0/24",
        address_prefixes=None,
        network_security_group=SimpleNamespace(id=NSG_ID) if nsg else None,
        route_table=SimpleNamespace(id=RT_ID) if route_table else None,
        nat_gateway=SimpleNamespace(id=NAT_ID) if nat else None,
        service_endpoints=[SimpleNamespace(service="Microsoft.Storage", locations=["eastus"])],
        delegations=[
            SimpleNamespace(
                name="delegation-1",
                service_name="Microsoft.ContainerInstance/containerGroups",
                actions=["Microsoft.Network/virtualNetworks/subnets/action"],
            )
        ],
    )


def test_list_virtual_networks_whole_subscription_uses_list_all(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_networks.list_all.return_value = make_pageable([_vnet()])

    result = list_virtual_networks(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert len(result) == 1
    vnet = result[0]
    assert vnet.resource_id == VNET_ID
    assert vnet.address_space == ["10.0.0.0/16"]
    assert vnet.dns_servers == ["10.0.0.4"]
    assert vnet.subnet_ids == [SUBNET_ID]
    assert vnet.peerings[0].peering_state == "Connected"
    assert vnet.resource_group == RESOURCE_GROUP
    network_client.virtual_networks.list_all.assert_called_once()
    network_client.virtual_networks.list.assert_not_called()


def test_list_virtual_networks_scoped_to_resource_group_uses_list(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_networks.list.return_value = make_pageable([_vnet()])

    list_virtual_networks(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    network_client.virtual_networks.list.assert_called_once_with(resource_group_name=RESOURCE_GROUP)
    network_client.virtual_networks.list_all.assert_not_called()


def test_list_subnets_normalizes_associations_and_endpoints(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.subnets.list.return_value = make_pageable([_subnet()])

    result = list_subnets(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    subnet = result[0]
    assert subnet.network_security_group_id == NSG_ID
    assert subnet.route_table_id == RT_ID
    assert subnet.nat_gateway_id == NAT_ID
    assert subnet.service_endpoints[0].service == "Microsoft.Storage"
    assert subnet.delegations[0].service_name == "Microsoft.ContainerInstance/containerGroups"
    assert subnet.virtual_network_name == "vnet-1"


def test_list_subnets_handles_unassociated_subnet(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.subnets.list.return_value = make_pageable(
        [_subnet(nsg=False, route_table=False, nat=False)]
    )

    result = list_subnets(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    subnet = result[0]
    assert subnet.network_security_group_id is None
    assert subnet.route_table_id is None
    assert subnet.nat_gateway_id is None
