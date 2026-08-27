from __future__ import annotations

import pytest

from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings
from azure_network_mcp.exceptions import InvalidConfigurationError, SubscriptionNotAllowedError

SUB_A = "aaaaaaaa-0000-0000-0000-000000000000"
SUB_B = "bbbbbbbb-0000-0000-0000-000000000000"
TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


def test_resolve_subscription_id_uses_requested_value() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id=SUB_B)
    ctx = SubscriptionContext(settings)
    assert ctx.resolve_subscription_id(SUB_A) == SUB_A


def test_resolve_subscription_id_falls_back_to_default() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id=SUB_B)
    ctx = SubscriptionContext(settings)
    assert ctx.resolve_subscription_id(None) == SUB_B


def test_resolve_subscription_id_raises_when_neither_given() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id=None)
    ctx = SubscriptionContext(settings)
    with pytest.raises(InvalidConfigurationError):
        ctx.resolve_subscription_id(None)


def test_assert_subscription_allowed_passes_when_no_allowlist() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=None)
    ctx = SubscriptionContext(settings)
    ctx.assert_subscription_allowed(SUB_A)  # must not raise


def test_assert_subscription_allowed_passes_when_in_allowlist() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=f"{SUB_A},{SUB_B}")
    ctx = SubscriptionContext(settings)
    ctx.assert_subscription_allowed(SUB_A)  # must not raise


def test_assert_subscription_allowed_rejects_when_not_in_allowlist() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=SUB_A)
    ctx = SubscriptionContext(settings)
    with pytest.raises(SubscriptionNotAllowedError):
        ctx.assert_subscription_allowed(SUB_B)


def test_resolve_subscription_id_enforces_allowlist_on_fallback() -> None:
    settings = Settings(
        _env_file=None, azure_default_subscription_id=SUB_B, azure_subscription_allowlist=SUB_A
    )
    ctx = SubscriptionContext(settings)
    with pytest.raises(SubscriptionNotAllowedError):
        ctx.resolve_subscription_id(None)


def test_assert_tenant_allowed_passes_when_no_allowlist() -> None:
    settings = Settings(_env_file=None, azure_tenant_allowlist=None)
    ctx = SubscriptionContext(settings)
    ctx.assert_tenant_allowed(TENANT_A)  # must not raise
    ctx.assert_tenant_allowed(None)  # must not raise


def test_assert_tenant_allowed_passes_when_in_allowlist() -> None:
    settings = Settings(_env_file=None, azure_tenant_allowlist=f"{TENANT_A},{TENANT_B}")
    ctx = SubscriptionContext(settings)
    ctx.assert_tenant_allowed(TENANT_A)  # must not raise


def test_assert_tenant_allowed_rejects_when_not_in_allowlist() -> None:
    settings = Settings(_env_file=None, azure_tenant_allowlist=TENANT_A)
    ctx = SubscriptionContext(settings)
    with pytest.raises(SubscriptionNotAllowedError):
        ctx.assert_tenant_allowed(TENANT_B)


def test_assert_tenant_allowed_rejects_none_when_allowlist_configured() -> None:
    """Fail-closed: an allowlist is configured but the tenant is unknown."""
    settings = Settings(_env_file=None, azure_tenant_allowlist=TENANT_A)
    ctx = SubscriptionContext(settings)
    with pytest.raises(SubscriptionNotAllowedError):
        ctx.assert_tenant_allowed(None)
