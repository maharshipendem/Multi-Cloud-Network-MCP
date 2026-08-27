from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.resource_groups import list_resource_groups
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings


def _rg(name: str, has_network: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{name}",
        name=name,
        location="eastus",
        managed_by=None,
        tags={},
        properties=SimpleNamespace(provisioning_state="Succeeded"),
    )


def _resource(resource_type: str) -> SimpleNamespace:
    return SimpleNamespace(type=resource_type)


def test_list_resource_groups_basic(
    client_factory: ClientFactory, resource_client: MagicMock
) -> None:
    resource_client.resource_groups.list.return_value = make_pageable(
        [_rg("rg-network"), _rg("rg-storage")]
    )

    result = list_resource_groups(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert [g.name for g in result.data] == ["rg-network", "rg-storage"]
    assert result.warnings == []


def test_list_resource_groups_name_contains_filter(
    client_factory: ClientFactory, resource_client: MagicMock
) -> None:
    resource_client.resource_groups.list.return_value = make_pageable(
        [_rg("rg-network-prod"), _rg("rg-storage-prod")]
    )

    result = list_resource_groups(
        client_factory, subscription_id=SUBSCRIPTION_ID, name_contains="network"
    )

    assert [g.name for g in result.data] == ["rg-network-prod"]


def test_list_resource_groups_only_with_network_resources_keeps_matching_groups(
    client_factory: ClientFactory, resource_client: MagicMock
) -> None:
    resource_client.resource_groups.list.return_value = make_pageable(
        [_rg("rg-network"), _rg("rg-storage")]
    )
    resource_client.resources.list_by_resource_group.side_effect = [
        make_pageable([_resource("Microsoft.Network/virtualNetworks")]),
        make_pageable([_resource("Microsoft.Storage/storageAccounts")]),
    ]

    result = list_resource_groups(
        client_factory, subscription_id=SUBSCRIPTION_ID, only_with_network_resources=True
    )

    assert [g.name for g in result.data] == ["rg-network"]
    assert result.warnings == []


def test_list_resource_groups_fanout_cap_reached_emits_warning_and_keeps_group() -> None:
    settings = Settings(
        _env_file=None, azure_default_subscription_id=SUBSCRIPTION_ID, max_fanout_calls=1
    )
    factory = ClientFactory(settings, SubscriptionContext(settings))
    mock_client = MagicMock()
    factory._resource_clients[SUBSCRIPTION_ID] = mock_client
    mock_client.resource_groups.list.return_value = make_pageable(
        [_rg("rg-a"), _rg("rg-b"), _rg("rg-c")]
    )
    mock_client.resources.list_by_resource_group.return_value = make_pageable(
        [_resource("Microsoft.Network/virtualNetworks")]
    )

    result = list_resource_groups(
        factory, subscription_id=SUBSCRIPTION_ID, only_with_network_resources=True
    )

    assert len(result.warnings) == 2
    assert all(w.code == "FANOUT_CAP_REACHED" for w in result.warnings)
    # First group consumed the only budget slot and was checked/kept;
    # the remaining two are kept unconditionally once the cap is hit.
    assert [g.name for g in result.data] == ["rg-a", "rg-b", "rg-c"]
