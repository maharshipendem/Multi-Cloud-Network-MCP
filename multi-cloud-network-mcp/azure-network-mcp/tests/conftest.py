"""Shared pytest fixtures.

Unit tests never touch real Azure credentials or subscriptions: every
service-layer function is exercised by monkeypatching the ARM SDK's
operation-group methods (``.list``, ``.list_all``, ``.get``, ``begin_*``)
directly on a ``ClientFactory``-produced client, so ``DefaultAzureCredential``
is never asked to actually resolve a token. Integration tests that need real
credentials live under ``tests/integration`` and are marked
``@pytest.mark.integration``, excluded by default (see pyproject.toml's
``addopts``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings


class FakePageIterator:
    """Mimics ``azure.core.paging.ItemPaged.by_page()``.

    Splits ``items`` into ``page_size``-sized pages so ``paginate()``'s
    per-page call counting can be exercised without a real Azure response.
    """

    def __init__(self, items: list[Any], *, page_size: int = 100) -> None:
        self._pages = [items[i : i + page_size] for i in range(0, len(items), page_size)] or [[]]

    def __iter__(self) -> Iterator[list[Any]]:
        return iter(self._pages)


def make_pageable(items: list[Any], *, page_size: int = 100) -> MagicMock:
    """Build a MagicMock shaped like an ``ItemPaged`` for a ``.list*`` call."""
    pageable = MagicMock()
    pageable.by_page.return_value = FakePageIterator(items, page_size=page_size)
    return pageable


@pytest.fixture(autouse=True)
def azure_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Obviously-fake values so DefaultAzureCredential's environment-variable
    # source, if ever constructed, cannot resolve to anything real. No test
    # actually invokes get_token() -- operation-group methods are always
    # monkeypatched directly -- but this keeps the sandbox honest.
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_CERTIFICATE_PATH", raising=False)
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000002")


SUBSCRIPTION_ID = "11111111-1111-1111-1111-111111111111"
RESOURCE_GROUP = "rg-network-test"
TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        azure_tenant_id=TENANT_ID,
        azure_client_id=None,
        azure_subscription_allowlist=None,
        azure_tenant_allowlist=None,
        azure_default_subscription_id=SUBSCRIPTION_ID,
    )


@pytest.fixture
def subscription_context(settings: Settings) -> SubscriptionContext:
    return SubscriptionContext(settings)


@pytest.fixture
def client_factory(settings: Settings, subscription_context: SubscriptionContext) -> ClientFactory:
    return ClientFactory(settings, subscription_context)


@pytest.fixture
def network_client(client_factory: ClientFactory) -> MagicMock:
    """A MagicMock substituted in place of the real ``NetworkManagementClient``
    for ``SUBSCRIPTION_ID``, so tests can set return values on its operation
    groups (e.g. ``network_client.virtual_networks.list_all.return_value``)."""
    mock_client = MagicMock()
    client_factory._network_clients[SUBSCRIPTION_ID] = mock_client
    return mock_client


@pytest.fixture
def resource_client(client_factory: ClientFactory) -> MagicMock:
    mock_client = MagicMock()
    client_factory._resource_clients[SUBSCRIPTION_ID] = mock_client
    return mock_client


@pytest.fixture
def subscription_client(client_factory: ClientFactory) -> MagicMock:
    mock_client = MagicMock()
    client_factory._subscription_client = mock_client
    return mock_client
