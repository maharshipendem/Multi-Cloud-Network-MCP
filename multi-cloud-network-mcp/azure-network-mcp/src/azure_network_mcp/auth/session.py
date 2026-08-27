"""Subscription/tenant allowlist enforcement.

Every tool that resolves a subscription ID (explicitly given, or falling
back to ``Settings.azure_default_subscription_id``) passes through
``SubscriptionContext.resolve_subscription_id`` before any ARM client is
built for it -- this is the choke point that makes an allowlist actually
enforced rather than merely documented. Unset allowlists mean "whatever
the configured identity's RBAC role permits," matching how this server's
AWS sibling defers resource-level scoping to IAM rather than
second-guessing it; a *configured* allowlist is an additional, optional
restriction this server enforces itself, independent of RBAC.
"""

from __future__ import annotations

from azure_network_mcp.config import Settings
from azure_network_mcp.exceptions import InvalidConfigurationError, SubscriptionNotAllowedError


class SubscriptionContext:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve_subscription_id(self, requested: str | None) -> str:
        """Resolve the subscription ID a tool call should operate against,
        falling back to the configured default, then validate it against
        the allowlist (if one is configured)."""
        subscription_id = requested or self._settings.azure_default_subscription_id
        if not subscription_id:
            raise InvalidConfigurationError(
                "No subscription_id was given and AZURE_DEFAULT_SUBSCRIPTION_ID is not "
                "configured. Pass subscription_id explicitly, or set a default."
            )
        self.assert_subscription_allowed(subscription_id)
        return subscription_id

    def assert_subscription_allowed(self, subscription_id: str) -> None:
        allowlist = self._settings.subscription_allowlist
        if allowlist is not None and subscription_id not in allowlist:
            raise SubscriptionNotAllowedError(
                f"Subscription '{subscription_id}' is not in the configured "
                "AZURE_SUBSCRIPTION_ALLOWLIST."
            )

    def assert_tenant_allowed(self, tenant_id: str | None) -> None:
        allowlist = self._settings.tenant_allowlist
        if allowlist is not None and (tenant_id is None or tenant_id not in allowlist):
            raise SubscriptionNotAllowedError(
                f"Tenant '{tenant_id}' is not in the configured AZURE_TENANT_ALLOWLIST."
            )


__all__ = ["SubscriptionContext"]
