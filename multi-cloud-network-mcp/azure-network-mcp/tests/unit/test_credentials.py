from __future__ import annotations

from azure.identity import DefaultAzureCredential

from azure_network_mcp.auth.credentials import _cached_credential, get_shared_credential
from azure_network_mcp.config import Settings


def test_get_shared_credential_returns_default_azure_credential() -> None:
    settings = Settings(_env_file=None, azure_tenant_id=None, azure_client_id=None)
    credential = get_shared_credential(settings)
    assert isinstance(credential, DefaultAzureCredential)


def test_get_shared_credential_is_cached_for_identical_settings() -> None:
    _cached_credential.cache_clear()
    settings_a = Settings(_env_file=None, azure_tenant_id="tenant-x", azure_client_id=None)
    settings_b = Settings(_env_file=None, azure_tenant_id="tenant-x", azure_client_id=None)
    assert get_shared_credential(settings_a) is get_shared_credential(settings_b)


def test_get_shared_credential_differs_across_distinct_tenants() -> None:
    _cached_credential.cache_clear()
    settings_a = Settings(_env_file=None, azure_tenant_id="tenant-x", azure_client_id=None)
    settings_b = Settings(_env_file=None, azure_tenant_id="tenant-y", azure_client_id=None)
    assert get_shared_credential(settings_a) is not get_shared_credential(settings_b)


def test_credential_never_exposes_a_get_token_call_in_this_codebase() -> None:
    """Regression guard: this module must never call .get_token() itself --
    only the ARM SDK clients (outside this codebase) are permitted to."""
    import inspect

    from azure_network_mcp.auth import credentials

    source = inspect.getsource(credentials)
    assert ".get_token(" not in source
