from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gcp_network_mcp.auth.credentials import _cached_credentials
from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.identity import get_caller_identity


@pytest.fixture(autouse=True)
def _clear_credentials_cache() -> None:
    _cached_credentials.cache_clear()


def test_get_caller_identity_resolves_service_account_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_credentials = MagicMock()
    fake_credentials.service_account_email = "robot@proj.iam.gserviceaccount.com"
    monkeypatch.setattr(
        "google.auth.default", MagicMock(return_value=(fake_credentials, "adc-project"))
    )
    settings = Settings(_env_file=None)
    identity = get_caller_identity(settings)
    assert identity.principal == "robot@proj.iam.gserviceaccount.com"
    assert identity.adc_project_id == "adc-project"
    assert identity.impersonated_service_account is None


def test_get_caller_identity_never_exposes_token_material(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_credentials = MagicMock()
    fake_credentials.service_account_email = None
    fake_credentials.signer_email = None
    fake_credentials.token = "super-secret-token"  # must never surface
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(fake_credentials, None)))
    settings = Settings(_env_file=None)
    identity = get_caller_identity(settings)
    dumped = identity.model_dump()
    assert "super-secret-token" not in str(dumped)
    assert identity.principal is None


def test_get_caller_identity_reports_impersonation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_base = MagicMock()
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(fake_base, None)))
    settings = Settings(
        _env_file=None, gcp_impersonate_service_account="robot@proj.iam.gserviceaccount.com"
    )
    identity = get_caller_identity(settings)
    assert identity.credential_type == "impersonated_service_account"
    assert identity.impersonated_service_account == "robot@proj.iam.gserviceaccount.com"
