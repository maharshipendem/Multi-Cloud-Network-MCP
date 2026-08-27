"""The **only** place an Azure ARM SDK client is constructed.

Mirrors the layering discipline of this server's AWS sibling: every
service-layer function reaches Azure exclusively through
``ClientFactory``, which owns credential resolution, subscription
allowlist enforcement, retry/timeout configuration, and client caching
(a ``NetworkManagementClient``/``ResourceManagementClient`` is
subscription-scoped in the Azure SDK, so one is cached per subscription
ID rather than built fresh per call).
"""

from __future__ import annotations

from typing import Any

from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient

from azure_network_mcp.auth.credentials import get_shared_credential
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings


class ClientFactory:
    def __init__(self, settings: Settings, subscription_context: SubscriptionContext) -> None:
        self.settings = settings
        self.subscription_context = subscription_context
        self._credential = get_shared_credential(settings)
        self._network_clients: dict[str, NetworkManagementClient] = {}
        self._resource_clients: dict[str, ResourceManagementClient] = {}
        self._subscription_client: SubscriptionClient | None = None
        # This SDK's Subscription model carries no tenant_id field (some
        # newer ARM API versions add one; this one doesn't), so a
        # per-subscription tenant check isn't possible via the API this
        # server calls. What *is* enforceable: the tenant the credential
        # itself was explicitly configured against, checked once here --
        # see auth/session.py::assert_tenant_allowed.
        subscription_context.assert_tenant_allowed(settings.azure_tenant_id)

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "retry_total": self.settings.azure_max_retries,
            "connection_timeout": self.settings.azure_connection_timeout,
            "read_timeout": self.settings.azure_read_timeout,
        }

    def get_network_client(self, subscription_id: str) -> NetworkManagementClient:
        """Return a cached ``NetworkManagementClient`` for ``subscription_id``.

        Validates ``subscription_id`` against the configured allowlist
        (if any) before ever constructing a client for it -- a client
        that never gets built can never issue a request.
        """
        self.subscription_context.assert_subscription_allowed(subscription_id)
        client = self._network_clients.get(subscription_id)
        if client is None:
            client = NetworkManagementClient(
                self._credential, subscription_id, **self._client_kwargs()
            )
            self._network_clients[subscription_id] = client
        return client

    def get_resource_client(self, subscription_id: str) -> ResourceManagementClient:
        self.subscription_context.assert_subscription_allowed(subscription_id)
        client = self._resource_clients.get(subscription_id)
        if client is None:
            client = ResourceManagementClient(
                self._credential, subscription_id, **self._client_kwargs()
            )
            self._resource_clients[subscription_id] = client
        return client

    def get_subscription_client(self) -> SubscriptionClient:
        """Return the cached, tenant-scoped ``SubscriptionClient`` used for
        listing subscriptions, tenants, and locations -- not subscription-
        scoped, so exactly one instance is cached regardless of how many
        subscriptions this server ends up operating against."""
        if self._subscription_client is None:
            self._subscription_client = SubscriptionClient(
                self._credential, **self._client_kwargs()
            )
        return self._subscription_client


__all__ = ["ClientFactory"]
