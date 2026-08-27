from __future__ import annotations

from datetime import UTC, datetime, timedelta

from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.config import Settings


@mock_aws
def test_get_session_without_role_arn_returns_base_session(settings: Settings) -> None:
    manager = SessionManager(settings)
    session = manager.get_session()
    assert session is manager.get_session()  # same base session object reused


@mock_aws
def test_get_session_with_role_arn_assumes_role_and_caches(settings: Settings) -> None:
    manager = SessionManager(settings)
    role_arn = "arn:aws:iam::123456789012:role/example-role"

    first = manager.get_session(role_arn=role_arn)
    second = manager.get_session(role_arn=role_arn)

    assert first is second  # cached, not re-assumed
    creds = first.get_credentials()
    assert creds is not None


@mock_aws
def test_get_session_refreshes_expired_assumed_role(settings: Settings) -> None:
    manager = SessionManager(settings)
    role_arn = "arn:aws:iam::123456789012:role/example-role"

    first = manager.get_session(role_arn=role_arn)

    # Force the cached credentials to look expired.
    stale_creds, _ = manager._assumed_cache[role_arn]
    expired = stale_creds.__class__(
        access_key=stale_creds.access_key,
        secret_key=stale_creds.secret_key,
        session_token=stale_creds.session_token,
        expiration=datetime.now(UTC) - timedelta(seconds=5),
    )
    manager._assumed_cache[role_arn] = (expired, first)

    second = manager.get_session(role_arn=role_arn)
    assert second is not None  # a fresh session/credentials were obtained
