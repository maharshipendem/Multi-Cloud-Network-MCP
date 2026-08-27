from __future__ import annotations

import pytest

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings
from azure_network_mcp.exceptions import SubscriptionNotAllowedError

SUB_A = "aaaaaaaa-0000-0000-0000-000000000000"
SUB_B = "bbbbbbbb-0000-0000-0000-000000000000"
TENANT_A = "tenant-a"


def test_init_enforces_tenant_allowlist_against_configured_tenant() -> None:
    settings = Settings(
        _env_file=None, azure_tenant_id="other-tenant", azure_tenant_allowlist=TENANT_A
    )
    ctx = SubscriptionContext(settings)
    with pytest.raises(SubscriptionNotAllowedError):
        ClientFactory(settings, ctx)


def test_init_succeeds_when_configured_tenant_is_allowed() -> None:
    settings = Settings(_env_file=None, azure_tenant_id=TENANT_A, azure_tenant_allowlist=TENANT_A)
    ctx = SubscriptionContext(settings)
    ClientFactory(settings, ctx)  # must not raise


def test_get_network_client_caches_per_subscription(client_factory: ClientFactory) -> None:
    client_a1 = client_factory.get_network_client(SUB_A)
    client_a2 = client_factory.get_network_client(SUB_A)
    client_b = client_factory.get_network_client(SUB_B)
    assert client_a1 is client_a2
    assert client_a1 is not client_b


def test_get_resource_client_caches_per_subscription(client_factory: ClientFactory) -> None:
    client_a1 = client_factory.get_resource_client(SUB_A)
    client_a2 = client_factory.get_resource_client(SUB_A)
    assert client_a1 is client_a2


def test_get_subscription_client_is_a_singleton(client_factory: ClientFactory) -> None:
    client_1 = client_factory.get_subscription_client()
    client_2 = client_factory.get_subscription_client()
    assert client_1 is client_2


def test_get_network_client_rejects_disallowed_subscription() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=SUB_A)
    ctx = SubscriptionContext(settings)
    factory = ClientFactory(settings, ctx)
    with pytest.raises(SubscriptionNotAllowedError):
        factory.get_network_client(SUB_B)


def test_get_resource_client_rejects_disallowed_subscription() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=SUB_A)
    ctx = SubscriptionContext(settings)
    factory = ClientFactory(settings, ctx)
    with pytest.raises(SubscriptionNotAllowedError):
        factory.get_resource_client(SUB_B)


def test_client_kwargs_reflect_configured_timeouts_and_retries() -> None:
    settings = Settings(
        _env_file=None,
        azure_max_retries=7,
        azure_connection_timeout=1.5,
        azure_read_timeout=9.0,
    )
    ctx = SubscriptionContext(settings)
    factory = ClientFactory(settings, ctx)
    kwargs = factory._client_kwargs()
    assert kwargs == {"retry_total": 7, "connection_timeout": 1.5, "read_timeout": 9.0}
