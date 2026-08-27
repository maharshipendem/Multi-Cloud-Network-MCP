"""Integration tests against a real Azure subscription.

These are NOT run by default (see the ``addopts = "-m 'not integration'"``
setting in pyproject.toml). Run them explicitly with a real Azure identity
available (``az login``, a service principal via environment variables, or
a managed identity) and ``AZURE_DEFAULT_SUBSCRIPTION_ID`` set, via:

    pytest -m integration

Each test is read-only and safe to run against a real subscription, but
does require actual Azure Resource Manager API access.
"""

from __future__ import annotations

import re

import pytest

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.identity import get_caller_identity
from azure_network_mcp.arm.networking import list_virtual_networks
from azure_network_mcp.arm.resource_groups import list_resource_groups
from azure_network_mcp.arm.subscriptions import list_locations, list_subscriptions
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_client_factory() -> ClientFactory:
    settings = get_settings()
    return ClientFactory(settings, SubscriptionContext(settings))


@pytest.fixture(scope="module")
def live_subscription_id() -> str:
    settings = get_settings()
    if not settings.azure_default_subscription_id:
        pytest.skip("AZURE_DEFAULT_SUBSCRIPTION_ID is not configured")
    return settings.azure_default_subscription_id


def test_get_caller_identity_against_real_azure(live_client_factory: ClientFactory) -> None:
    identity = get_caller_identity(live_client_factory)
    assert identity.credential_type


def test_list_subscriptions_against_real_azure(live_client_factory: ClientFactory) -> None:
    subscriptions = list_subscriptions(live_client_factory)
    assert isinstance(subscriptions, list)  # may legitimately be empty if scoped narrowly
    for subscription in subscriptions:
        assert re.fullmatch(r"[0-9a-fA-F-]{36}", subscription.subscription_id), (
            subscription.subscription_id
        )


def test_list_locations_against_real_azure(
    live_client_factory: ClientFactory, live_subscription_id: str
) -> None:
    locations = list_locations(live_client_factory, subscription_id=live_subscription_id)
    assert any(loc.name == "eastus" for loc in locations)


def test_list_resource_groups_against_real_azure(
    live_client_factory: ClientFactory, live_subscription_id: str
) -> None:
    result = list_resource_groups(live_client_factory, subscription_id=live_subscription_id)
    assert isinstance(result.data, list)


def test_list_virtual_networks_against_real_azure(
    live_client_factory: ClientFactory, live_subscription_id: str
) -> None:
    vnets = list_virtual_networks(live_client_factory, subscription_id=live_subscription_id)
    assert isinstance(vnets, list)
