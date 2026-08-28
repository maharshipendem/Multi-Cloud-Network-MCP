"""The **only** place a GCP client library service client is constructed.

Every service-layer function reaches GCP exclusively through
``ClientFactory``, which owns credential resolution and client caching.
Unlike Azure's mgmt SDK (where a client is scoped to one subscription at
construction time), GCP's ``google-cloud-compute``/
``google-cloud-resource-manager`` clients are **not** project-scoped --
``project`` is passed as a parameter on each individual call
(``client.list(project="my-project", ...)``), so exactly one instance of
each client class is constructed and cached for the whole process,
regardless of how many projects this server ends up querying.

Credential resolution itself is deferred to first use (the first
``_client()`` call), not done at ``ClientFactory`` construction time.
Unlike Azure's ``DefaultAzureCredential`` (whose constructor never
touches the network -- it only resolves a credential lazily, on first
token request), ``google.auth.default()`` eagerly validates ADC
synchronously when called. Resolving it eagerly in ``__init__`` would
mean ``build_server()`` itself fails outside an ADC-configured
environment -- including the offline MCP smoke tests, which build a real
server and only mock the GCP client classes, not credential resolution.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from google.auth.credentials import Credentials
from google.cloud import compute_v1, resourcemanager_v3

from gcp_network_mcp.auth.credentials import get_shared_credentials
from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings


class _SupportsCredentialedInit(Protocol):
    def __init__(self, *, credentials: Credentials) -> None: ...


T = TypeVar("T", bound=_SupportsCredentialedInit)


class ClientFactory:
    def __init__(self, settings: Settings, resource_context: ResourceContext) -> None:
        self.settings = settings
        self.resource_context = resource_context
        self._credentials: Credentials | None = None
        self._adc_project_id: str | None = None
        self._clients: dict[type, Any] = {}

    def _resolved_credentials(self) -> Credentials:
        if self._credentials is None:
            self._credentials, self._adc_project_id = get_shared_credentials(self.settings)
        return self._credentials

    def _client(self, client_cls: type[T]) -> T:
        client = self._clients.get(client_cls)
        if client is None:
            client = client_cls(credentials=self._resolved_credentials())
            self._clients[client_cls] = client
        return client

    # --- Compute Engine (networking) -----------------------------------------

    def networks(self) -> compute_v1.NetworksClient:
        return self._client(compute_v1.NetworksClient)

    def subnetworks(self) -> compute_v1.SubnetworksClient:
        return self._client(compute_v1.SubnetworksClient)

    def routes(self) -> compute_v1.RoutesClient:
        return self._client(compute_v1.RoutesClient)

    def firewalls(self) -> compute_v1.FirewallsClient:
        return self._client(compute_v1.FirewallsClient)

    def firewall_policies(self) -> compute_v1.FirewallPoliciesClient:
        return self._client(compute_v1.FirewallPoliciesClient)

    def network_firewall_policies(self) -> compute_v1.NetworkFirewallPoliciesClient:
        return self._client(compute_v1.NetworkFirewallPoliciesClient)

    def instances(self) -> compute_v1.InstancesClient:
        return self._client(compute_v1.InstancesClient)

    def addresses(self) -> compute_v1.AddressesClient:
        return self._client(compute_v1.AddressesClient)

    def global_addresses(self) -> compute_v1.GlobalAddressesClient:
        return self._client(compute_v1.GlobalAddressesClient)

    def forwarding_rules(self) -> compute_v1.ForwardingRulesClient:
        return self._client(compute_v1.ForwardingRulesClient)

    def global_forwarding_rules(self) -> compute_v1.GlobalForwardingRulesClient:
        return self._client(compute_v1.GlobalForwardingRulesClient)

    def target_http_proxies(self) -> compute_v1.TargetHttpProxiesClient:
        return self._client(compute_v1.TargetHttpProxiesClient)

    def target_https_proxies(self) -> compute_v1.TargetHttpsProxiesClient:
        return self._client(compute_v1.TargetHttpsProxiesClient)

    def backend_services(self) -> compute_v1.BackendServicesClient:
        return self._client(compute_v1.BackendServicesClient)

    def region_backend_services(self) -> compute_v1.RegionBackendServicesClient:
        return self._client(compute_v1.RegionBackendServicesClient)

    def routers(self) -> compute_v1.RoutersClient:
        return self._client(compute_v1.RoutersClient)

    def compute_projects(self) -> compute_v1.ProjectsClient:
        """The Compute Engine Projects client -- used only for Shared VPC
        host/service-project discovery (``get_xpn_host``/
        ``get_xpn_resources``/``list_xpn_hosts``), not general project
        metadata (see ``resource_manager_projects`` for that)."""
        return self._client(compute_v1.ProjectsClient)

    # --- Resource Manager (project/folder/organization context) -----------------

    def resource_manager_projects(self) -> resourcemanager_v3.ProjectsClient:
        return self._client(resourcemanager_v3.ProjectsClient)

    def resource_manager_folders(self) -> resourcemanager_v3.FoldersClient:
        return self._client(resourcemanager_v3.FoldersClient)

    def resource_manager_organizations(self) -> resourcemanager_v3.OrganizationsClient:
        return self._client(resourcemanager_v3.OrganizationsClient)


__all__ = ["ClientFactory"]
