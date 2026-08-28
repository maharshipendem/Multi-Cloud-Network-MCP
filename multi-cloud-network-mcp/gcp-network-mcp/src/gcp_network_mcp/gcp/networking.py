"""Service-layer functions for VPC Networks and Subnetworks."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate, paginate_aggregated
from gcp_network_mcp.models.common import parse_self_link
from gcp_network_mcp.models.networking import Network, SecondaryRange, Subnetwork
from gcp_network_mcp.models.peering import NetworkPeering


def normalize_network(network: compute_v1.Network, *, project_id: str) -> Network:
    return Network(
        self_link=network.self_link or None,
        id=str(network.id) if network.id else None,
        name=network.name,
        project_id=project_id,
        mode="auto" if network.auto_create_subnetworks else "custom",
        mtu=network.mtu or None,
        subnetwork_self_links=list(network.subnetworks),
        peering_names=[p.name for p in network.peerings],
        firewall_policy_self_link=network.firewall_policy or None,
        network_firewall_policy_enforcement_order=network.network_firewall_policy_enforcement_order
        or None,
        routing_mode=network.routing_config.routing_mode if "routing_config" in network else None,
        internal_ipv6_range=network.internal_ipv6_range or None,
        observed_at=now_iso(),
        source_api="NetworksClient.list",
    )


def extract_peerings(network: compute_v1.Network) -> list[NetworkPeering]:
    """Extract VPC Network Peerings embedded on a Network -- GCP has no
    separate peering-listing API."""
    return [
        NetworkPeering(
            name=p.name,
            owning_network_self_link=network.self_link,
            network=p.network,
            state=p.state or None,
            state_details=p.state_details or None,
            exchange_subnet_routes=p.exchange_subnet_routes,
            export_custom_routes=p.export_custom_routes,
            import_custom_routes=p.import_custom_routes,
            auto_create_routes=p.auto_create_routes,
            stack_type=p.stack_type or None,
        )
        for p in network.peerings
    ]


def list_networks(client_factory: ClientFactory, *, project_id: str) -> list[Network]:
    raw = paginate(
        client_factory.networks(),
        "list",
        resource_type="network",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_network(n, project_id=project_id) for n in raw]


def _normalize_secondary_range(raw: compute_v1.SubnetworkSecondaryRange) -> SecondaryRange:
    return SecondaryRange(range_name=raw.range_name, ip_cidr_range=raw.ip_cidr_range)


def normalize_subnetwork(subnetwork: compute_v1.Subnetwork, *, project_id: str) -> Subnetwork:
    parsed = parse_self_link(subnetwork.self_link) if subnetwork.self_link else None
    return Subnetwork(
        self_link=subnetwork.self_link or None,
        id=str(subnetwork.id) if subnetwork.id else None,
        name=subnetwork.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        network_self_link=subnetwork.network,
        ip_cidr_range=subnetwork.ip_cidr_range,
        gateway_address=subnetwork.gateway_address or None,
        purpose=subnetwork.purpose or None,
        role=subnetwork.role or None,
        stack_type=subnetwork.stack_type or None,
        ipv6_cidr_range=subnetwork.ipv6_cidr_range or None,
        private_ip_google_access=subnetwork.private_ip_google_access,
        private_ipv6_google_access=subnetwork.private_ipv6_google_access or None,
        enable_flow_logs=subnetwork.enable_flow_logs if "enable_flow_logs" in subnetwork else None,
        state=subnetwork.state or None,
        secondary_ip_ranges=[_normalize_secondary_range(r) for r in subnetwork.secondary_ip_ranges],
        observed_at=now_iso(),
        source_api="SubnetworksClient.aggregated_list",
    )


def list_subnetworks(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    """List every Subnetwork across every region in one project."""
    raw, warnings = paginate_aggregated(
        client_factory.subnetworks(),
        "aggregated_list",
        items_field="subnetworks",
        resource_type="subnetwork",
        project_id=project_id,
        project=project_id,
    )
    data = [normalize_subnetwork(s, project_id=project_id) for s in raw]
    return CollectionResult(data=data, warnings=warnings)


__all__ = [
    "extract_peerings",
    "list_networks",
    "list_subnetworks",
    "normalize_network",
    "normalize_subnetwork",
]
