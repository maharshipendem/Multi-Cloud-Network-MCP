"""The single GCP-bridging seam for the diagnostics engine.

``collect_hybrid_snapshot`` is the only function in ``diagnostics.*``
that touches ``gcp.*`` (and therefore, transitively, the GCP client
libraries) -- every rule module downstream is a pure function of the
``HybridNetworkSnapshot`` this module produces, mirroring the AWS/Azure
siblings' own snapshot seam. It adds zero new GCP API surface beyond
what Milestones 7 and 8's own ``gcp.*`` collectors already provide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from gcp_network_mcp.gcp.bgp import get_router_status
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.connectivity_center import (
    list_hubs,
    list_ncc_routes,
    list_route_tables,
    list_spokes,
)
from gcp_network_mcp.gcp.dns import list_dns_zones
from gcp_network_mcp.gcp.firewall import (
    list_firewall_rules,
    list_hierarchical_firewall_policies,
    list_network_firewall_policies,
)
from gcp_network_mcp.gcp.interconnect import (
    get_interconnect_diagnostics,
    list_interconnect_attachments,
    list_interconnects,
)
from gcp_network_mcp.gcp.load_balancing import list_forwarding_rules
from gcp_network_mcp.gcp.nat import list_routers
from gcp_network_mcp.gcp.networking import extract_peerings, list_networks, list_subnetworks
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.gcp.routes import list_routes
from gcp_network_mcp.gcp.shared_vpc import get_shared_vpc_host_status
from gcp_network_mcp.gcp.vpn import get_vpn_gateway_status, list_vpn_gateways, list_vpn_tunnels
from gcp_network_mcp.models.bgp import RouterStatusSummary
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.connectivity_center import NccHub, NccRoute, NccRouteTable, NccSpoke
from gcp_network_mcp.models.dns import DnsZone
from gcp_network_mcp.models.firewall import FirewallPolicy, FirewallRule, implied_firewall_rules
from gcp_network_mcp.models.interconnect import (
    Interconnect,
    InterconnectAttachment,
    InterconnectDiagnostics,
)
from gcp_network_mcp.models.load_balancing import ForwardingRuleSummary
from gcp_network_mcp.models.nat import RouterSummary
from gcp_network_mcp.models.networking import Network, Subnetwork
from gcp_network_mcp.models.peering import NetworkPeering
from gcp_network_mcp.models.routes import Route
from gcp_network_mcp.models.shared_vpc import SharedVpcHostStatus
from gcp_network_mcp.models.vpn import VpnGateway, VpnGatewayStatus, VpnTunnel

if TYPE_CHECKING:
    from gcp_network_mcp.gcp.client_factory import ClientFactory


class HybridNetworkSnapshot(BaseModel):
    """Every fact the diagnostics engine's rules reason over, for one
    project. A pure data container -- collection (this module) and
    reasoning (routing.py/firewall.py/nat.py/exposure.py/peering.py/
    ncc.py/vpn_bgp_interconnect.py/dns.py) are fully separate."""

    project_id: str
    observed_at: str

    networks: list[Network] = Field(default_factory=list)
    subnetworks: list[Subnetwork] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    peerings: list[NetworkPeering] = Field(default_factory=list)
    firewall_rules: list[FirewallRule] = Field(default_factory=list)
    network_firewall_policies: list[FirewallPolicy] = Field(default_factory=list)
    hierarchical_firewall_policies: list[FirewallPolicy] = Field(default_factory=list)
    forwarding_rules: list[ForwardingRuleSummary] = Field(default_factory=list)
    routers: list[RouterSummary] = Field(default_factory=list)
    router_statuses: list[RouterStatusSummary] = Field(default_factory=list)

    ncc_hubs: list[NccHub] = Field(default_factory=list)
    ncc_spokes: list[NccSpoke] = Field(default_factory=list)
    ncc_route_tables: list[NccRouteTable] = Field(default_factory=list)
    ncc_routes: list[NccRoute] = Field(default_factory=list)

    vpn_gateways: list[VpnGateway] = Field(default_factory=list)
    vpn_gateway_statuses: list[VpnGatewayStatus] = Field(default_factory=list)
    vpn_tunnels: list[VpnTunnel] = Field(default_factory=list)

    interconnects: list[Interconnect] = Field(default_factory=list)
    interconnect_attachments: list[InterconnectAttachment] = Field(default_factory=list)
    interconnect_diagnostics: list[InterconnectDiagnostics] = Field(default_factory=list)

    shared_vpc_host_status: SharedVpcHostStatus | None = None

    dns_zones: list[DnsZone] = Field(default_factory=list)

    warnings: list[CollectionWarning] = Field(default_factory=list)


def collect_hybrid_snapshot(
    client_factory: ClientFactory,
    *,
    project_id: str,
    hierarchical_firewall_parent_id: str | None = None,
    max_fanout: int = 50,
) -> HybridNetworkSnapshot:
    """Collect every fact the diagnostics engine needs for one project.
    Best-effort per resource family: a family this identity lacks IAM
    permission for (or that doesn't exist in this project -- e.g. no NCC
    hubs, no VPN gateways) contributes an empty list plus a
    ``CollectionWarning`` rather than failing the whole snapshot -- see
    ``_collect`` below. ``hierarchical_firewall_parent_id`` is optional
    because hierarchical Firewall Policies are org/folder-scoped, not
    derivable from a project ID alone; omitting it means hierarchical
    policy interaction (``FW-002``) runs at ``confidence="indeterminate"``.
    Per-resource computed-status calls (VPN gateway status, router BGP
    status, Interconnect diagnostics) are capped at ``max_fanout``
    resources each, with a warning if the cap is hit.
    """
    warnings: list[CollectionWarning] = []

    def _collect(resource_type: str, func: Any, *args: Any, **kwargs: Any) -> list[Any]:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any collection
            # failure degrades to an empty, warned family rather than
            # failing the whole snapshot (partial IAM, a disabled API,
            # throttling all land here).
            warnings.append(
                CollectionWarning(
                    resource_type=resource_type,
                    code="COLLECTION_FAILED",
                    message=f"Could not collect {resource_type}: {exc}",
                    project_id=project_id,
                )
            )
            return []
        if isinstance(result, CollectionResult):
            warnings.extend(result.warnings)
            return list(result.data)
        return list(result)

    networks = _collect("network", list_networks, client_factory, project_id=project_id)
    # extract_peerings needs the raw compute_v1.Network, which
    # list_networks doesn't retain post-normalization -- re-derive
    # peerings the same way gcp.peering.list_network_peerings does, via
    # one extra raw list() call rather than a per-network fetch.
    peerings = _collect(
        "network_peering", _peerings_via_raw_networks, client_factory, project_id=project_id
    )

    subnetworks = _collect("subnetwork", list_subnetworks, client_factory, project_id=project_id)

    routes = _collect("route", list_routes, client_factory, project_id=project_id)

    firewall_rules = _collect(
        "firewall_rule", list_firewall_rules, client_factory, project_id=project_id
    )
    for network in networks:
        if network.self_link:
            firewall_rules.extend(
                implied_firewall_rules(
                    network_self_link=network.self_link, network_name=network.name
                )
            )

    network_firewall_policies = _collect(
        "network_firewall_policy",
        list_network_firewall_policies,
        client_factory,
        project_id=project_id,
    )
    hierarchical_firewall_policies: list[FirewallPolicy] = []
    if hierarchical_firewall_parent_id:
        hierarchical_firewall_policies = _collect(
            "firewall_policy",
            list_hierarchical_firewall_policies,
            client_factory,
            parent_id=hierarchical_firewall_parent_id,
        )

    forwarding_rules = _collect(
        "forwarding_rule", list_forwarding_rules, client_factory, project_id=project_id
    )

    routers = _collect("router", list_routers, client_factory, project_id=project_id)
    router_statuses: list[RouterStatusSummary] = []
    for router in routers[:max_fanout]:
        if router.region is None:
            continue
        router_statuses.extend(
            _collect(
                "router_status",
                lambda r=router: [
                    get_router_status(
                        client_factory, project_id=project_id, region=r.region, router_name=r.name
                    )
                ],
            )
        )
    if len(routers) > max_fanout:
        warnings.append(
            CollectionWarning(
                resource_type="router_status",
                code="FANOUT_CAP_REACHED",
                message=(
                    f"Only the first {max_fanout} of {len(routers)} routers had "
                    "their BGP status collected."
                ),
                project_id=project_id,
            )
        )

    ncc_hubs = _collect("ncc_hub", list_hubs, client_factory, project_id=project_id)
    ncc_spokes = _collect("ncc_spoke", list_spokes, client_factory, project_id=project_id)
    ncc_route_tables: list[NccRouteTable] = []
    ncc_routes: list[NccRoute] = []
    for hub in ncc_hubs[:max_fanout]:
        route_tables = _collect(
            "ncc_route_table",
            list_route_tables,
            client_factory,
            hub_name=hub.name,
            project_id=project_id,
        )
        ncc_route_tables.extend(route_tables)
        for route_table in route_tables:
            ncc_routes.extend(
                _collect(
                    "ncc_route",
                    list_ncc_routes,
                    client_factory,
                    route_table_name=route_table.name,
                    project_id=project_id,
                )
            )

    vpn_gateways = _collect("vpn_gateway", list_vpn_gateways, client_factory, project_id=project_id)
    vpn_gateway_statuses: list[VpnGatewayStatus] = []
    for gateway in vpn_gateways[:max_fanout]:
        if gateway.region is None:
            continue
        vpn_gateway_statuses.extend(
            _collect(
                "vpn_gateway_status",
                lambda g=gateway: [
                    get_vpn_gateway_status(
                        client_factory,
                        project_id=project_id,
                        region=g.region,
                        vpn_gateway_name=g.name,
                    )
                ],
            )
        )

    vpn_tunnels = _collect("vpn_tunnel", list_vpn_tunnels, client_factory, project_id=project_id)

    interconnects = _collect(
        "interconnect", list_interconnects, client_factory, project_id=project_id
    )
    interconnect_diagnostics: list[InterconnectDiagnostics] = []
    for interconnect in interconnects[:max_fanout]:
        interconnect_diagnostics.extend(
            _collect(
                "interconnect_diagnostics",
                lambda ic=interconnect: [
                    get_interconnect_diagnostics(
                        client_factory, project_id=project_id, interconnect_name=ic.name
                    )
                ],
            )
        )
    interconnect_attachments = _collect(
        "interconnect_attachment",
        list_interconnect_attachments,
        client_factory,
        project_id=project_id,
    )

    dns_zones = _collect("dns_zone", list_dns_zones, client_factory, project_id=project_id)

    shared_vpc_host_status_list = _collect(
        "shared_vpc_host_status",
        lambda: [get_shared_vpc_host_status(client_factory, project_id=project_id)],
    )
    shared_vpc_host_status = shared_vpc_host_status_list[0] if shared_vpc_host_status_list else None

    return HybridNetworkSnapshot(
        project_id=project_id,
        observed_at=now_iso(),
        networks=networks,
        subnetworks=subnetworks,
        routes=routes,
        peerings=peerings,
        firewall_rules=firewall_rules,
        network_firewall_policies=network_firewall_policies,
        hierarchical_firewall_policies=hierarchical_firewall_policies,
        forwarding_rules=forwarding_rules,
        routers=routers,
        router_statuses=router_statuses,
        ncc_hubs=ncc_hubs,
        ncc_spokes=ncc_spokes,
        ncc_route_tables=ncc_route_tables,
        ncc_routes=ncc_routes,
        vpn_gateways=vpn_gateways,
        vpn_gateway_statuses=vpn_gateway_statuses,
        vpn_tunnels=vpn_tunnels,
        interconnects=interconnects,
        interconnect_attachments=interconnect_attachments,
        interconnect_diagnostics=interconnect_diagnostics,
        shared_vpc_host_status=shared_vpc_host_status,
        dns_zones=dns_zones,
        warnings=warnings,
    )


def _peerings_via_raw_networks(
    client_factory: ClientFactory, *, project_id: str
) -> list[NetworkPeering]:
    raw_networks = paginate(
        client_factory.networks(),
        "list",
        resource_type="network",
        project_id=project_id,
        project=project_id,
    )
    peerings: list[NetworkPeering] = []
    for raw_network in raw_networks:
        peerings.extend(extract_peerings(raw_network))
    return peerings


__all__ = ["HybridNetworkSnapshot", "collect_hybrid_snapshot"]
