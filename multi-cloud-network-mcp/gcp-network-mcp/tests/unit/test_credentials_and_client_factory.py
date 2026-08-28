from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.auth import impersonated_credentials

from gcp_network_mcp.auth.credentials import _cached_credentials, get_shared_credentials
from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.client_factory import ClientFactory


@pytest.fixture(autouse=True)
def _clear_credentials_cache() -> None:
    _cached_credentials.cache_clear()


def test_get_shared_credentials_calls_google_auth_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_credentials = MagicMock(name="fake_credentials")
    mock_default = MagicMock(return_value=(fake_credentials, "adc-project"))
    monkeypatch.setattr("google.auth.default", mock_default)

    settings = Settings(_env_file=None)
    credentials, adc_project_id = get_shared_credentials(settings)

    assert credentials is fake_credentials
    assert adc_project_id == "adc-project"
    mock_default.assert_called_once()
    _, kwargs = mock_default.call_args
    assert kwargs["scopes"] == ["https://www.googleapis.com/auth/cloud-platform.read-only"]


def test_get_shared_credentials_wraps_impersonation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_base_credentials = MagicMock(name="fake_base_credentials")
    monkeypatch.setattr(
        "google.auth.default", MagicMock(return_value=(fake_base_credentials, None))
    )

    settings = Settings(
        _env_file=None, gcp_impersonate_service_account="robot@proj.iam.gserviceaccount.com"
    )
    credentials, _ = get_shared_credentials(settings)

    assert isinstance(credentials, impersonated_credentials.Credentials)


def test_get_shared_credentials_is_cached_per_config(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_default = MagicMock(return_value=(MagicMock(), None))
    monkeypatch.setattr("google.auth.default", mock_default)

    settings = Settings(_env_file=None)
    get_shared_credentials(settings)
    get_shared_credentials(settings)

    assert mock_default.call_count == 1


def test_client_factory_defers_credential_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructing a ClientFactory must never call google.auth.default --
    only actually building a client should."""

    def _fail(*_a: object, **_k: object) -> None:
        raise AssertionError("ClientFactory() must not resolve credentials eagerly")

    monkeypatch.setattr("google.auth.default", _fail)
    settings = Settings(_env_file=None)
    factory = ClientFactory(settings, ResourceContext(settings))
    assert factory is not None


def test_client_factory_caches_one_instance_per_client_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(MagicMock(), None)))
    settings = Settings(_env_file=None)
    factory = ClientFactory(settings, ResourceContext(settings))

    first = factory.networks()
    second = factory.networks()
    assert first is second
