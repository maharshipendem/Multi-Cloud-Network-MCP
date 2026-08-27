"""Normalized identity/context models.

Deliberately excludes any access token, refresh token, or credential
material -- "current identity/context (without token details)" per this
milestone's own requirement. ``CallerIdentity`` reports only what
identity is in use and which tenant/subscription it resolved against.
"""

from __future__ import annotations

from pydantic import BaseModel


class CallerIdentity(BaseModel):
    """The identity this server is currently authenticating as, and the
    tenant/subscription context it resolved -- never a token, a secret,
    or any credential material."""

    credential_type: str
    tenant_id: str | None = None
    default_subscription_id: str | None = None
    subscription_allowlist_configured: bool
    tenant_allowlist_configured: bool


__all__ = ["CallerIdentity"]
