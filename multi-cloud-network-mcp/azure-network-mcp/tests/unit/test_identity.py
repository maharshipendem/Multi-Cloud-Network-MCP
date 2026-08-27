from __future__ import annotations

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.identity import get_caller_identity
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings


def test_get_caller_identity_reports_credential_type_and_context() -> None:
    settings = Settings(
        _env_file=None,
        azure_tenant_id="tenant-a",
        azure_default_subscription_id="sub-1",
    )
    factory = ClientFactory(settings, SubscriptionContext(settings))

    identity = get_caller_identity(factory)

    assert identity.credential_type == "DefaultAzureCredential"
    assert identity.tenant_id == "tenant-a"
    assert identity.default_subscription_id == "sub-1"
    assert identity.subscription_allowlist_configured is False
    assert identity.tenant_allowlist_configured is False


def test_get_caller_identity_reports_configured_allowlists() -> None:
    settings = Settings(
        _env_file=None,
        azure_tenant_id="tenant-a",
        azure_tenant_allowlist="tenant-a",
        azure_subscription_allowlist="sub-1,sub-2",
    )
    factory = ClientFactory(settings, SubscriptionContext(settings))

    identity = get_caller_identity(factory)

    assert identity.subscription_allowlist_configured is True
    assert identity.tenant_allowlist_configured is True


def test_get_caller_identity_never_exposes_token_fields() -> None:
    settings = Settings(_env_file=None)
    factory = ClientFactory(settings, SubscriptionContext(settings))
    identity = get_caller_identity(factory)
    dumped = identity.model_dump()
    for forbidden in ("token", "secret", "credential_value", "access_token"):
        assert forbidden not in dumped
