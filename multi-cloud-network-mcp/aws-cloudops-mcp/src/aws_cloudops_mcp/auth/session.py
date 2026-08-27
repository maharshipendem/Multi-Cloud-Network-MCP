"""Boto3 session caching and cross-account AssumeRole management.

Design decision: sessions (not individual boto3 clients) are what gets
cached here, keyed by role ARN. Client construction from an existing
session is cheap and stateless in boto3, so there is no need to cache
clients themselves -- only the credential material, which is comparatively
expensive (and, for AssumeRole, rate-limited) to obtain.

Credentials are refreshed proactively a safety margin before they expire
and are never retained past that point, satisfying the "do not cache
credentials beyond their safe lifetime" requirement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3

from aws_cloudops_mcp.auth.credentials import (
    AssumedRoleCredentials,
    assume_role,
    build_base_session,
)
from aws_cloudops_mcp.config import Settings

_REFRESH_MARGIN = timedelta(seconds=60)


class SessionManager:
    """Resolves and caches boto3 Sessions for the base identity and assumed roles."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_session: boto3.Session | None = None
        self._assumed_cache: dict[str, tuple[AssumedRoleCredentials, boto3.Session]] = {}

    def _get_base_session(self) -> boto3.Session:
        if self._base_session is None:
            self._base_session = build_base_session(self._settings)
        return self._base_session

    def get_session(self, role_arn: str | None = None) -> boto3.Session:
        """Return a boto3 Session for ``role_arn``, or the base session if None."""
        if not role_arn:
            return self._get_base_session()

        cached = self._assumed_cache.get(role_arn)
        if cached is not None:
            creds, session = cached
            if creds.expiration - _REFRESH_MARGIN > datetime.now(UTC):
                return session

        creds = assume_role(
            self._get_base_session(),
            role_arn=role_arn,
            session_name=self._settings.aws_session_name,
            external_id=self._settings.aws_external_id,
        )
        session = boto3.Session(
            aws_access_key_id=creds.access_key,
            aws_secret_access_key=creds.secret_key,
            aws_session_token=creds.session_token,
            region_name=self._settings.aws_default_region,
        )
        self._assumed_cache[role_arn] = (creds, session)
        return session

    def invalidate(self, role_arn: str | None = None) -> None:
        """Drop cached credentials for ``role_arn`` (or the base session)."""
        if role_arn:
            self._assumed_cache.pop(role_arn, None)
        else:
            self._base_session = None
            self._assumed_cache.clear()
