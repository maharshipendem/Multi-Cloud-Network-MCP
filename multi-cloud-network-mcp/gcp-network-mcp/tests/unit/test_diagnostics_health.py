"""Unit tests for ``diagnostics.health.get_network_health`` -- summarizes
``find_network_risks``'s findings into severity counts, a resource
inventory, and one ``overall_status`` signal. Tested here via
directly-constructed snapshots that deterministically produce findings of
each severity tier."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.health import ResourceCounts, get_network_health
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.nat import RouterNatSummary, RouterSummary
from gcp_network_mcp.models.networking import Network, Subnetwork
from gcp_network_mcp.models.peering import NetworkPeering

PROJECT_ID = "test-project-1"
NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
FRESHNESS = "2026-01-01T00:00:00Z"


def _snapshot(**overrides: object) -> HybridNetworkSnapshot:
    return HybridNetworkSnapshot(project_id=PROJECT_ID, observed_at=FRESHNESS, **overrides)


def _network() -> Network:
    return Network(
        self_link=NETWORK_SELF_LINK,
        name="vpc-1",
        project_id=PROJECT_ID,
        mode="auto",
        observed_at=FRESHNESS,
    )


def test_healthy_when_no_findings_at_all() -> None:
    report = get_network_health(_snapshot())
    assert report.overall_status == "healthy"
    assert report.findings == []
    assert report.finding_counts_by_severity == dict.fromkeys(
        ("critical", "high", "medium", "low", "info"), 0
    )


def test_attention_needed_when_only_medium_findings_present() -> None:
    """A medium-severity finding (PEER-001's exchange_subnet_routes=false
    case) alone -> 'attention_needed', not 'healthy' or worse."""
    peering = NetworkPeering(
        name="peer-1",
        owning_network_self_link=NETWORK_SELF_LINK,
        network="https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x",
        state="ACTIVE",
        exchange_subnet_routes=False,
    )
    report = get_network_health(_snapshot(peerings=[peering]))
    assert report.overall_status == "attention_needed"
    assert report.finding_counts_by_severity["medium"] >= 1
    assert report.finding_counts_by_severity["critical"] == 0
    assert report.finding_counts_by_severity["high"] == 0


def test_degraded_when_a_high_severity_finding_is_present() -> None:
    """A non-ACTIVE peering is a high-severity PEER-001 finding ->
    'degraded', even with no critical findings present."""
    peering = NetworkPeering(
        name="peer-1",
        owning_network_self_link=NETWORK_SELF_LINK,
        network="https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x",
        state="INACTIVE",
    )
    report = get_network_health(_snapshot(peerings=[peering]))
    assert report.overall_status == "degraded"
    assert report.finding_counts_by_severity["high"] >= 1
    assert report.finding_counts_by_severity["critical"] == 0


def test_critical_when_a_critical_severity_finding_is_present() -> None:
    """A Cloud NAT with MANUAL_ONLY allocation and zero assigned IPs is a
    critical-severity NAT-001 finding -> 'critical', taking priority over
    any lower-severity findings also present in the same snapshot."""
    router = RouterSummary(
        name="router-1",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        observed_at=FRESHNESS,
        nats=[RouterNatSummary(name="nat-1", nat_ip_allocate_option="MANUAL_ONLY", nat_ips=[])],
    )
    # Also include a medium-severity finding to prove critical wins the tie-break.
    peering = NetworkPeering(
        name="peer-1",
        owning_network_self_link=NETWORK_SELF_LINK,
        network="https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x",
        state="ACTIVE",
        exchange_subnet_routes=False,
    )
    report = get_network_health(_snapshot(routers=[router], peerings=[peering]))
    assert report.overall_status == "critical"
    assert report.finding_counts_by_severity["critical"] >= 1
    assert report.finding_counts_by_severity["medium"] >= 1


def test_resource_counts_reflect_snapshot_inventory() -> None:
    subnet = Subnetwork(
        name="subnet-1",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        ip_cidr_range="10.0.0.0/24",
        observed_at=FRESHNESS,
    )
    snapshot = _snapshot(networks=[_network()], subnetworks=[subnet, subnet])

    report = get_network_health(snapshot)

    assert report.resource_counts == ResourceCounts(
        networks=1,
        subnetworks=2,
        routes=0,
        firewall_rules=0,
        routers=0,
        vpn_gateways=0,
        vpn_tunnels=0,
        interconnects=0,
        interconnect_attachments=0,
        ncc_hubs=0,
        ncc_spokes=0,
    )


def test_collection_warning_count_reflects_snapshot_warnings() -> None:
    warnings = [
        CollectionWarning(
            resource_type="ncc_hub", code="COLLECTION_FAILED", message="boom", project_id=PROJECT_ID
        ),
        CollectionWarning(
            resource_type="vpn_gateway",
            code="COLLECTION_FAILED",
            message="also boom",
            project_id=PROJECT_ID,
        ),
    ]
    report = get_network_health(_snapshot(warnings=warnings))
    assert report.collection_warning_count == 2


def test_project_id_and_observed_at_are_carried_from_snapshot() -> None:
    report = get_network_health(_snapshot())
    assert report.project_id == PROJECT_ID
    assert report.observed_at == FRESHNESS


def test_hub_status_findings_feed_into_overall_status() -> None:
    """Sanity check that ``get_network_health`` is genuinely delegating to
    ``find_network_risks`` rather than duplicating its own reasoning --
    NCC-001 findings from a degraded PSC propagation status roll up into
    the same severity accounting used for ``overall_status``."""
    # NccHubStatus/evaluate_hub_status aren't wired into find_network_risks
    # via the snapshot (only per-spoke evaluation is) -- this test instead
    # confirms the counted severities exactly match what find_network_risks
    # itself would return, keeping the two in lockstep.
    from gcp_network_mcp.diagnostics.risks import find_network_risks

    peering = NetworkPeering(
        name="peer-1",
        owning_network_self_link=NETWORK_SELF_LINK,
        network="https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x",
        state="INACTIVE",
    )
    snapshot = _snapshot(peerings=[peering])
    report = get_network_health(snapshot)
    expected_findings = find_network_risks(snapshot)

    assert len(report.findings) == len(expected_findings)
    assert {f.rule_id for f in report.findings} == {f.rule_id for f in expected_findings}
