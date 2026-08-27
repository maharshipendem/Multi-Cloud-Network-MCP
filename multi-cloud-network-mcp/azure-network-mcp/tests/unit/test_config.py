from __future__ import annotations

from azure_network_mcp.config import Settings


def test_subscription_allowlist_none_when_unset() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=None)
    assert settings.subscription_allowlist is None


def test_subscription_allowlist_parses_comma_separated_ids() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist=" sub-1, sub-2 ,sub-3")
    assert settings.subscription_allowlist == ["sub-1", "sub-2", "sub-3"]


def test_subscription_allowlist_empty_string_is_none() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist="")
    assert settings.subscription_allowlist is None


def test_tenant_allowlist_parses_comma_separated_ids() -> None:
    settings = Settings(_env_file=None, azure_tenant_allowlist="tenant-a,tenant-b")
    assert settings.tenant_allowlist == ["tenant-a", "tenant-b"]


def test_tenant_allowlist_none_when_unset() -> None:
    settings = Settings(_env_file=None, azure_tenant_allowlist=None)
    assert settings.tenant_allowlist is None


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == "azure-network-mcp"
    assert settings.log_level == "INFO"
    assert settings.azure_max_retries == 3
    assert settings.max_page_results == 1000
    assert settings.max_fanout_calls == 50
    assert settings.max_concurrency == 10
