"""ARM service layer: subscriptions, tenants, and locations.

``SubscriptionClient`` is tenant-scoped (built once, not per subscription
-- see ``ClientFactory.get_subscription_client``). Results are filtered
to the configured subscription allowlist (if any) *after* collection --
Azure's own ``ListSubscriptions`` has no server-side allowlist filter, so
this is the same "collect broadly, then apply the configured allowlist"
pattern ``SubscriptionContext`` uses everywhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.models.subscriptions import Location, Subscription, Tenant

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_subscriptions(client_factory: ClientFactory) -> list[Subscription]:
    """Call SubscriptionClient.subscriptions.list, filtered to the
    configured allowlist (if any)."""
    client = client_factory.get_subscription_client()
    settings = client_factory.settings
    allowlist = settings.subscription_allowlist

    raw = paginate(client.subscriptions, "list", max_items=settings.max_page_results)
    subscriptions = [
        Subscription(
            subscription_id=s.subscription_id,
            display_name=s.display_name,
            state=s.state,
        )
        for s in raw
        if s.subscription_id
    ]
    if allowlist is not None:
        subscriptions = [s for s in subscriptions if s.subscription_id in allowlist]
    return subscriptions


def list_tenants(client_factory: ClientFactory) -> list[Tenant]:
    """Call SubscriptionClient.tenants.list, filtered to the configured
    tenant allowlist (if any)."""
    client = client_factory.get_subscription_client()
    settings = client_factory.settings
    allowlist = settings.tenant_allowlist

    raw = paginate(client.tenants, "list", max_items=settings.max_page_results)
    tenants = [Tenant(tenant_id=t.tenant_id) for t in raw if t.tenant_id]
    if allowlist is not None:
        tenants = [t for t in tenants if t.tenant_id in allowlist]
    return tenants


def list_locations(client_factory: ClientFactory, *, subscription_id: str) -> list[Location]:
    """Call SubscriptionClient.subscriptions.list_locations for one
    (allowlist-validated) subscription."""
    client_factory.subscription_context.assert_subscription_allowed(subscription_id)
    client = client_factory.get_subscription_client()
    settings = client_factory.settings

    raw = paginate(
        client.subscriptions,
        "list_locations",
        max_items=settings.max_page_results,
        subscription_id=subscription_id,
    )
    return [
        Location(
            name=location.name,
            display_name=location.display_name,
            subscription_id=subscription_id,
        )
        for location in raw
        if location.name
    ]


__all__ = ["list_locations", "list_subscriptions", "list_tenants"]
