"""Service-layer functions for Cloud Routers and their embedded Cloud
NAT configurations."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.bgp import normalize_bgp_peer_config
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_aggregated
from gcp_network_mcp.models.common import parse_self_link
from gcp_network_mcp.models.nat import RouterNatSummary, RouterSummary


def _normalize_nat(nat: compute_v1.RouterNat) -> RouterNatSummary:
    return RouterNatSummary(
        name=nat.name,
        nat_ip_allocate_option=nat.nat_ip_allocate_option or None,
        source_subnetwork_ip_ranges_to_nat=nat.source_subnetwork_ip_ranges_to_nat or None,
        nat_ips=list(nat.nat_ips),
        min_ports_per_vm=nat.min_ports_per_vm or None,
        max_ports_per_vm=nat.max_ports_per_vm or None,
        enable_endpoint_independent_mapping=nat.enable_endpoint_independent_mapping,
    )


def normalize_router(router: compute_v1.Router, *, project_id: str) -> RouterSummary:
    parsed = parse_self_link(router.self_link) if router.self_link else None
    return RouterSummary(
        self_link=router.self_link or None,
        id=str(router.id) if router.id else None,
        name=router.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        network_self_link=router.network,
        bgp_asn=router.bgp.asn if "bgp" in router else None,
        nats=[_normalize_nat(n) for n in router.nats],
        bgp_peers=[normalize_bgp_peer_config(p) for p in router.bgp_peers],
        observed_at=now_iso(),
        source_api="RoutersClient.aggregated_list",
    )


def list_routers(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    """List every Cloud Router (and its embedded Cloud NAT config) across
    every region in one project -- GCP has no separate NAT-listing API."""
    raw, warnings = paginate_aggregated(
        client_factory.routers(),
        "aggregated_list",
        items_field="routers",
        resource_type="router",
        project_id=project_id,
        project=project_id,
    )
    data = [normalize_router(r, project_id=project_id) for r in raw]
    return CollectionResult(data=data, warnings=warnings)


__all__ = ["list_routers", "normalize_router"]
