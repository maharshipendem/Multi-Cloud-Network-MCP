"""ARM service layer: current identity/context, without token details."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.models.identity import CallerIdentity

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def get_caller_identity(client_factory: ClientFactory) -> CallerIdentity:
    """Report the credential type and tenant/subscription context this
    server is configured with. Never calls ``credential.get_token()`` and
    never surfaces a token, secret, or other credential material -- see
    docs/security.md#credential-handling."""
    settings = client_factory.settings
    return CallerIdentity(
        credential_type=type(client_factory._credential).__name__,
        tenant_id=settings.azure_tenant_id,
        default_subscription_id=settings.azure_default_subscription_id,
        subscription_allowlist_configured=settings.subscription_allowlist is not None,
        tenant_allowlist_configured=settings.tenant_allowlist is not None,
    )


__all__ = ["get_caller_identity"]
