from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.subscriptions import list_locations, list_subscriptions, list_tenants
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings


def _sub(sub_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(subscription_id=sub_id, display_name=name, state="Enabled")


def _tenant(tenant_id: str) -> SimpleNamespace:
    return SimpleNamespace(tenant_id=tenant_id)


def _location(name: str, display_name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, display_name=display_name)


def test_list_subscriptions_returns_all_when_no_allowlist(
    client_factory: ClientFactory, subscription_client: MagicMock
) -> None:
    subscription_client.subscriptions.list.return_value = make_pageable(
        [_sub("sub-1", "One"), _sub("sub-2", "Two")]
    )
    result = list_subscriptions(client_factory)
    assert [s.subscription_id for s in result] == ["sub-1", "sub-2"]


def test_list_subscriptions_filters_to_allowlist() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist="sub-1")
    factory = ClientFactory(settings, SubscriptionContext(settings))
    mock_client = MagicMock()
    factory._subscription_client = mock_client
    mock_client.subscriptions.list.return_value = make_pageable(
        [_sub("sub-1", "One"), _sub("sub-2", "Two")]
    )

    result = list_subscriptions(factory)

    assert [s.subscription_id for s in result] == ["sub-1"]


def test_list_tenants_filters_to_allowlist() -> None:
    settings = Settings(
        _env_file=None, azure_tenant_id="tenant-a", azure_tenant_allowlist="tenant-a"
    )
    factory = ClientFactory(settings, SubscriptionContext(settings))
    mock_client = MagicMock()
    factory._subscription_client = mock_client
    mock_client.tenants.list.return_value = make_pageable(
        [_tenant("tenant-a"), _tenant("tenant-b")]
    )

    result = list_tenants(factory)

    assert [t.tenant_id for t in result] == ["tenant-a"]


def test_list_locations_calls_subscriptions_list_locations(
    client_factory: ClientFactory, subscription_client: MagicMock
) -> None:
    subscription_client.subscriptions.list_locations.return_value = make_pageable(
        [_location("eastus", "East US"), _location("westus", "West US")]
    )

    result = list_locations(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert [loc.name for loc in result] == ["eastus", "westus"]
    assert all(loc.subscription_id == SUBSCRIPTION_ID for loc in result)
    subscription_client.subscriptions.list_locations.assert_called_once()
