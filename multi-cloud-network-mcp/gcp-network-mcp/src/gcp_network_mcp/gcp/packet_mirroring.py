"""Service-layer function for Packet Mirroring *configuration* --
never mirrored packet content (this server has no code path that could
even reach captured traffic; the API this module calls only ever returns
policy configuration)."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_aggregated
from gcp_network_mcp.models.packet_mirroring import (
    PacketMirroringFilterSummary,
    PacketMirroringPolicy,
)


def normalize_packet_mirroring(
    policy: compute_v1.PacketMirroring, *, project_id: str
) -> PacketMirroringPolicy:
    filter_summary = None
    if "filter" in policy:
        filter_summary = PacketMirroringFilterSummary(
            ip_protocols=list(policy.filter.I_p_protocols),
            cidr_ranges=list(policy.filter.cidr_ranges),
            direction=policy.filter.direction or None,
        )
    mirrored_instances: list[str] = []
    mirrored_subnetworks: list[str] = []
    mirrored_tags: list[str] = []
    if "mirrored_resources" in policy:
        mirrored_instances = [i.url for i in policy.mirrored_resources.instances if i.url]
        mirrored_subnetworks = [s.url for s in policy.mirrored_resources.subnetworks if s.url]
        mirrored_tags = list(policy.mirrored_resources.tags)
    return PacketMirroringPolicy(
        self_link=policy.self_link or None,
        id=str(policy.id) if policy.id else None,
        name=policy.name,
        project_id=project_id,
        region=policy.region.rsplit("/", 1)[-1] if policy.region else None,
        network_self_link=policy.network.url if "network" in policy else "",
        collector_ilb_forwarding_rule=policy.collector_ilb.url
        if "collector_ilb" in policy
        else None,
        enable=policy.enable or None,
        priority=policy.priority or None,
        mirrored_instance_self_links=mirrored_instances,
        mirrored_subnetwork_self_links=mirrored_subnetworks,
        mirrored_tags=mirrored_tags,
        filter=filter_summary,
        observed_at=now_iso(),
        source_api="PacketMirroringsClient.aggregated_list",
    )


def list_packet_mirroring_policies(
    client_factory: ClientFactory, *, project_id: str
) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.packet_mirrorings(),
        "aggregated_list",
        items_field="packet_mirrorings",
        resource_type="packet_mirroring_policy",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_packet_mirroring(p, project_id=project_id) for p in raw], warnings=warnings
    )


__all__ = ["list_packet_mirroring_policies", "normalize_packet_mirroring"]
