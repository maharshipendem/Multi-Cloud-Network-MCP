from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.network_interfaces import list_network_interfaces

NIC_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/networkInterfaces/nic-1"
)


def _nic() -> SimpleNamespace:
    return SimpleNamespace(
        id=NIC_ID,
        name="nic-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        ip_configurations=[
            SimpleNamespace(
                name="ipconfig1",
                private_ip_address="10.0.1.4",
                private_ip_allocation_method="Dynamic",
                subnet=SimpleNamespace(id="subnet-id"),
                public_ip_address=SimpleNamespace(id="pip-id"),
                primary=True,
            ),
            SimpleNamespace(
                name="ipconfig2",
                private_ip_address="10.0.1.5",
                private_ip_allocation_method="Static",
                subnet=SimpleNamespace(id="subnet-id"),
                public_ip_address=None,
                primary=False,
            ),
        ],
        network_security_group=SimpleNamespace(id="nsg-id"),
        mac_address="00-11-22-33-44-55",
        primary=True,
        enable_ip_forwarding=False,
        enable_accelerated_networking=True,
        virtual_machine=SimpleNamespace(id="vm-id"),
    )


def test_list_network_interfaces_normalizes_ip_configurations(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.network_interfaces.list_all.return_value = make_pageable([_nic()])

    result = list_network_interfaces(client_factory, subscription_id=SUBSCRIPTION_ID)

    nic = result[0]
    assert len(nic.ip_configurations) == 2
    assert nic.ip_configurations[0].primary is True
    assert nic.ip_configurations[0].public_ip_address_id == "pip-id"
    assert nic.ip_configurations[1].public_ip_address_id is None
    assert nic.network_security_group_id == "nsg-id"
    assert nic.virtual_machine_id == "vm-id"
    assert nic.enable_accelerated_networking is True


def test_list_network_interfaces_scoped_to_resource_group(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.network_interfaces.list.return_value = make_pageable([])
    list_network_interfaces(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )
    network_client.network_interfaces.list.assert_called_once_with(
        resource_group_name=RESOURCE_GROUP
    )
