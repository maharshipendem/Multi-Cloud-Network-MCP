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

Milestone 8 adds five more provider libraries
(``networkconnectivity_v1``, ``network_management_v1``,
``google.cloud.dns``, ``logging_v2``, ``monitoring_v3``), all constructed
through this same choke point. ``google.cloud.dns.Client`` is the one
exception to the "one instance per class for the whole process" rule:
unlike every gapic client this server uses, it is constructed *scoped to
one project* (``dns.Client(project=..., credentials=...)``), closer to
Azure's per-subscription client pattern -- so it is cached per project
ID instead, via ``dns_client()``.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

import google.cloud.dns as dns
from google.auth.credentials import Credentials
from google.cloud import compute_v1, monitoring_v3, network_management_v1, resourcemanager_v3
from google.cloud import networkconnectivity_v1 as ncc
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client

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
        self._dns_clients: dict[str, dns.Client] = {}

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

    def dns_client(self, project_id: str) -> dns.Client:
        client = self._dns_clients.get(project_id)
        if client is None:
            client = dns.Client(project=project_id, credentials=self._resolved_credentials())
            self._dns_clients[project_id] = client
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

    def vpn_gateways(self) -> compute_v1.VpnGatewaysClient:
        return self._client(compute_v1.VpnGatewaysClient)

    def vpn_tunnels(self) -> compute_v1.VpnTunnelsClient:
        return self._client(compute_v1.VpnTunnelsClient)

    def external_vpn_gateways(self) -> compute_v1.ExternalVpnGatewaysClient:
        return self._client(compute_v1.ExternalVpnGatewaysClient)

    def interconnects(self) -> compute_v1.InterconnectsClient:
        return self._client(compute_v1.InterconnectsClient)

    def interconnect_attachments(self) -> compute_v1.InterconnectAttachmentsClient:
        return self._client(compute_v1.InterconnectAttachmentsClient)

    def interconnect_locations(self) -> compute_v1.InterconnectLocationsClient:
        return self._client(compute_v1.InterconnectLocationsClient)

    def service_attachments(self) -> compute_v1.ServiceAttachmentsClient:
        """Private Service Connect: published services (producer side)."""
        return self._client(compute_v1.ServiceAttachmentsClient)

    def packet_mirrorings(self) -> compute_v1.PacketMirroringsClient:
        return self._client(compute_v1.PacketMirroringsClient)

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

    # --- Network Connectivity Center ------------------------------------------

    def ncc_hub_service(self) -> ncc.HubServiceClient:
        return self._client(ncc.HubServiceClient)

    # --- Network Management (Connectivity Tests, VPC Flow Logs config) --------

    def connectivity_tests(self) -> network_management_v1.ReachabilityServiceClient:
        return self._client(network_management_v1.ReachabilityServiceClient)

    def vpc_flow_logs(self) -> network_management_v1.VpcFlowLogsServiceClient:
        return self._client(network_management_v1.VpcFlowLogsServiceClient)

    def org_vpc_flow_logs(self) -> network_management_v1.OrganizationVpcFlowLogsServiceClient:
        return self._client(network_management_v1.OrganizationVpcFlowLogsServiceClient)

    # --- Observability (explicit-opt-in, narrowly bounded tools only) ---------

    def logs(self) -> LoggingServiceV2Client:
        return self._client(LoggingServiceV2Client)

    def metrics(self) -> monitoring_v3.MetricServiceClient:
        return self._client(monitoring_v3.MetricServiceClient)


__all__ = ["ClientFactory"]
