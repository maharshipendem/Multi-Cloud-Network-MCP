"""Centralized boto3 client construction.

This is the ONLY place boto3 clients are constructed. Tool and service-layer
code calls ``ClientFactory.get_client(...)`` instead of ``boto3.client(...)``
directly, so region selection, authentication, AssumeRole, retry/timeout
configuration, and account-identity caching are all handled consistently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.config import Config as BotocoreConfig

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.config import Settings

if TYPE_CHECKING:
    from aws_cloudops_mcp.models.common import CallerIdentity


class ClientFactory:
    """Builds boto3 clients with consistent auth, region, and SDK configuration."""

    def __init__(self, settings: Settings, session_manager: SessionManager) -> None:
        self.settings = settings
        self._session_manager = session_manager
        self._account_id_cache: dict[str, str] = {}

    def get_client(
        self,
        service: str,
        *,
        region: str | None = None,
        role_arn: str | None = None,
    ) -> Any:
        """Return a boto3 client for ``service`` in ``region``.

        ``role_arn`` overrides the server-wide default (``AWS_ROLE_ARN``)
        for this specific call, enabling future per-call cross-account
        access; when omitted, the configured default role (if any) is used.
        """
        resolved_region = region or self.settings.aws_default_region
        resolved_role_arn = role_arn if role_arn is not None else self.settings.aws_role_arn

        session = self._session_manager.get_session(role_arn=resolved_role_arn)
        client_config = BotocoreConfig(
            region_name=resolved_region,
            retries={"max_attempts": self.settings.aws_max_attempts, "mode": "standard"},
            connect_timeout=self.settings.aws_connect_timeout,
            read_timeout=self.settings.aws_read_timeout,
        )
        # `service` is a runtime string, not a Literal, so it can't match any
        # single overload of boto3-stubs' Session.client(); this factory is
        # intentionally generic across services.
        return session.client(service, config=client_config)  # type: ignore[call-overload]

    def get_account_id(self, role_arn: str | None = None) -> str:
        """Return the AWS account ID for ``role_arn`` (or the base identity), cached."""
        resolved_role_arn = role_arn if role_arn is not None else self.settings.aws_role_arn
        cache_key = resolved_role_arn or "__base__"

        if cache_key not in self._account_id_cache:
            identity = self._fetch_caller_identity(role_arn=resolved_role_arn)
            self._account_id_cache[cache_key] = identity.account_id

        return self._account_id_cache[cache_key]

    def _fetch_caller_identity(self, role_arn: str | None) -> CallerIdentity:
        from aws_cloudops_mcp.aws.accounts import get_caller_identity

        return get_caller_identity(self, role_arn=role_arn)
