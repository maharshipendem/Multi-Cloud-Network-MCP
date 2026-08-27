from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.nat_gateways import list_nat_gateways


def _nat_gateway() -> SimpleNamespace:
    return SimpleNamespace(
        id="nat-id",
        name="nat-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        sku=SimpleNamespace(name="Standard"),
        idle_timeout_in_minutes=4,
        public_ip_addresses=[SimpleNamespace(id="pip-1")],
        subnets=[SimpleNamespace(id="subnet-1")],
    )


def test_list_nat_gateways_normalizes_associations(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.nat_gateways.list_all.return_value = make_pageable([_nat_gateway()])

    result = list_nat_gateways(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].sku_name == "Standard"
    assert result[0].public_ip_address_ids == ["pip-1"]
    assert result[0].subnet_ids == ["subnet-1"]
