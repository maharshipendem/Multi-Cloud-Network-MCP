from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.peerings import list_virtual_network_peerings


def _peering(state: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="peering-id",
        name="peer-1",
        provisioning_state="Succeeded",
        remote_virtual_network=SimpleNamespace(id="remote-vnet-id"),
        remote_address_space=SimpleNamespace(address_prefixes=["10.1.0.0/16"]),
        peering_state=state,
        peering_sync_level="FullyInSync",
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
    )


@pytest.mark.parametrize("state", ["Initiated", "Connected", "Disconnected"])
def test_list_virtual_network_peerings_normalizes_every_peering_state(
    client_factory: ClientFactory, network_client: MagicMock, state: str
) -> None:
    network_client.virtual_network_peerings.list.return_value = make_pageable([_peering(state)])

    result = list_virtual_network_peerings(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    assert result[0].peering_state == state
    assert result[0].remote_virtual_network_id == "remote-vnet-id"
    assert result[0].remote_address_space == ["10.1.0.0/16"]
