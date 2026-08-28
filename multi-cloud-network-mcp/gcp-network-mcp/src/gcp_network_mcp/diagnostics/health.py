"""``gcp_get_network_health``'s orchestration: summarizes
``find_network_risks``'s findings into severity counts and a resource
inventory count, for a quick top-level health signal."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.diagnostics.models import Finding
from gcp_network_mcp.diagnostics.risks import find_network_risks
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot


class ResourceCounts(BaseModel):
    networks: int = 0
    subnetworks: int = 0
    routes: int = 0
    firewall_rules: int = 0
    routers: int = 0
    vpn_gateways: int = 0
    vpn_tunnels: int = 0
    interconnects: int = 0
    interconnect_attachments: int = 0
    ncc_hubs: int = 0
    ncc_spokes: int = 0


class NetworkHealthReport(BaseModel):
    project_id: str
    observed_at: str
    overall_status: str
    finding_counts_by_severity: dict[str, int] = Field(default_factory=dict)
    resource_counts: ResourceCounts
    findings: list[Finding] = Field(default_factory=list)
    collection_warning_count: int = 0


_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def _overall_status(counts: dict[str, int]) -> str:
    if counts.get("critical", 0) > 0:
        return "critical"
    if counts.get("high", 0) > 0:
        return "degraded"
    if counts.get("medium", 0) > 0:
        return "attention_needed"
    return "healthy"


def get_network_health(snapshot: HybridNetworkSnapshot) -> NetworkHealthReport:
    findings = find_network_risks(snapshot)
    counts = dict.fromkeys(_SEVERITY_ORDER, 0)
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    return NetworkHealthReport(
        project_id=snapshot.project_id,
        observed_at=snapshot.observed_at,
        overall_status=_overall_status(counts),
        finding_counts_by_severity=counts,
        resource_counts=ResourceCounts(
            networks=len(snapshot.networks),
            subnetworks=len(snapshot.subnetworks),
            routes=len(snapshot.routes),
            firewall_rules=len(snapshot.firewall_rules),
            routers=len(snapshot.routers),
            vpn_gateways=len(snapshot.vpn_gateways),
            vpn_tunnels=len(snapshot.vpn_tunnels),
            interconnects=len(snapshot.interconnects),
            interconnect_attachments=len(snapshot.interconnect_attachments),
            ncc_hubs=len(snapshot.ncc_hubs),
            ncc_spokes=len(snapshot.ncc_spokes),
        ),
        findings=findings,
        collection_warning_count=len(snapshot.warnings),
    )


__all__ = ["NetworkHealthReport", "ResourceCounts", "get_network_health"]
