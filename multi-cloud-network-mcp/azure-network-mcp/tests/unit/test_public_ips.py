from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.public_ips import list_public_ip_addresses


def _pip(*, associated: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id="pip-id",
        name="pip-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        ip_address="20.1.2.3" if associated else None,
        public_ip_allocation_method="Static",
        public_ip_address_version="IPv4",
        sku=SimpleNamespace(name="Standard"),
        idle_timeout_in_minutes=4,
        ip_configuration=SimpleNamespace(id="nic-ipconfig-id") if associated else None,
    )


def test_list_public_ip_addresses_associated(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.public_ip_addresses.list_all.return_value = make_pageable(
        [_pip(associated=True)]
    )

    result = list_public_ip_addresses(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].associated_resource_id == "nic-ipconfig-id"
    assert result[0].ip_address == "20.1.2.3"


def test_list_public_ip_addresses_unassociated(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.public_ip_addresses.list_all.return_value = make_pageable(
        [_pip(associated=False)]
    )

    result = list_public_ip_addresses(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].associated_resource_id is None
    assert result[0].ip_address is None
