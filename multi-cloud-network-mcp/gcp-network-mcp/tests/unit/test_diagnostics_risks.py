"""Unit tests for ``diagnostics.risks.find_network_risks`` -- orchestrates
every diagnostic rule against an already-collected ``HybridNetworkSnapshot``.
Tested here via directly-constructed snapshots exercising several distinct
rule modules at once, proving the orchestration wires them all in (each
individual rule's own logic is covered by its own dedicated test module,
not re-verified here)."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.risks import find_network_risks
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.connectivity_center import NccSpoke
from gcp_network_mcp.models.dns import DnsZone
from gcp_network_mcp.models.nat import RouterNatSummary, RouterSummary
from gcp_network_mcp.models.networking import Network
from gcp_network_mcp.models.peering import NetworkPeering
from gcp_network_mcp.models.routes import Route

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


def test_empty_snapshot_yields_no_findings() -> None:
    assert find_network_risks(_snapshot()) == []


def test_finds_risks_across_multiple_distinct_rule_ids() -> None:
    """Construct a snapshot that should trigger PEER-001 (non-ACTIVE
    peering), NAT-001 (Cloud NAT fully blocked), NCC-001 (inactive spoke),
    and ROUTE-002 (overlapping CIDR routes) simultaneously -- proving
    ``find_network_risks`` fans out to every rule module, not just one."""
    network = _network()
    peering = NetworkPeering(
        name="peer-1",
        owning_network_self_link=NETWORK_SELF_LINK,
        network="https://www.googleapis.com/compute/v1/projects/other/global/networks/vpc-x",
        state="INACTIVE",  # PEER-001
    )
    router = RouterSummary(
        name="router-1",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        observed_at=FRESHNESS,
        nats=[
            RouterNatSummary(
                name="nat-1",
                nat_ip_allocate_option="MANUAL_ONLY",
                nat_ips=[],  # NAT-001
            )
        ],
    )
    spoke = NccSpoke(
        name="spoke-1",
        project_id=PROJECT_ID,
        hub="hub-1",
        spoke_type="VPC_NETWORK",
        state="INACTIVE",  # NCC-001
        observed_at=FRESHNESS,
    )
    route_a = Route(
        name="route-a",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        dest_range="10.0.0.0/24",
        priority=1000,
        next_hop_type="instance",
        observed_at=FRESHNESS,
    )
    route_b = Route(
        name="route-b",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        dest_range="10.0.0.0/25",  # overlaps route_a -- ROUTE-002
        priority=900,
        next_hop_type="instance",
        observed_at=FRESHNESS,
    )

    snapshot = _snapshot(
        networks=[network],
        peerings=[peering],
        routers=[router],
        ncc_spokes=[spoke],
        routes=[route_a, route_b],
        hierarchical_firewall_policies=[],  # triggers the FW-002 advisory too
    )

    findings = find_network_risks(snapshot)
    rule_ids = {f.rule_id for f in findings}

    assert "PEER-001" in rule_ids
    assert "NAT-001" in rule_ids
    assert "NCC-001" in rule_ids
    assert "ROUTE-002" in rule_ids
    assert "FW-002" in rule_ids
    assert len(rule_ids) >= 5


def test_healthy_ncc_spoke_produces_no_finding() -> None:
    spoke = NccSpoke(
        name="spoke-1",
        project_id=PROJECT_ID,
        hub="hub-1",
        spoke_type="VPC_NETWORK",
        state="ACTIVE",
        observed_at=FRESHNESS,
    )
    findings = find_network_risks(_snapshot(ncc_spokes=[spoke]))
    assert findings == []


def test_fw002_advisory_appears_once_regardless_of_network_count() -> None:
    """FW-002's "no hierarchical policies supplied" advisory is a single,
    snapshot-wide finding (not tied to -- or duplicated per -- an
    arbitrary individual network) whenever the snapshot has at least one
    network and no hierarchical Firewall Policies."""
    network_2 = Network(
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-2"
        ),
        name="vpc-2",
        project_id=PROJECT_ID,
        mode="custom",
        observed_at=FRESHNESS,
    )
    snapshot = _snapshot(networks=[_network(), network_2], hierarchical_firewall_policies=[])

    findings = find_network_risks(snapshot)
    fw002_findings = [f for f in findings if f.rule_id == "FW-002"]

    assert len(fw002_findings) == 1
    assert fw002_findings[0].confidence == "indeterminate"
    assert set(fw002_findings[0].affected_resources) == {NETWORK_SELF_LINK, network_2.self_link}


def test_fw002_advisory_absent_when_hierarchical_policies_supplied() -> None:
    from gcp_network_mcp.models.firewall import FirewallPolicy

    snapshot = _snapshot(
        networks=[_network()],
        hierarchical_firewall_policies=[
            FirewallPolicy(name="org-policy", scope="hierarchical", observed_at=FRESHNESS)
        ],
    )
    findings = find_network_risks(snapshot)
    assert not any(f.rule_id == "FW-002" for f in findings)


def test_fw002_advisory_absent_when_no_networks_at_all() -> None:
    """The advisory is gated on ``snapshot.networks`` being non-empty --
    an empty snapshot with no hierarchical policies still shouldn't
    fabricate an advisory about nothing."""
    snapshot = _snapshot(networks=[], hierarchical_firewall_policies=[])
    findings = find_network_risks(snapshot)
    assert findings == []


def test_dns_zones_are_evaluated_by_dns_001() -> None:
    """``DnsZone`` is a real field on ``HybridNetworkSnapshot`` and
    ``find_network_risks`` must evaluate every zone through DNS-001 --
    ``evaluate_zone`` always returns a Finding (never None, unlike most
    other rules here), so one zone must yield exactly one DNS-001 finding,
    at ``confidence="indeterminate"`` for a zone that does have name
    servers assigned (the forwarding-chain aspect this rule can't see)."""
    zone = DnsZone(
        name="prod-zone",
        project_id=PROJECT_ID,
        dns_name="prod.example.com.",
        name_servers=["ns-cloud-a1.googledomains.com."],
        observed_at=FRESHNESS,
    )
    findings = find_network_risks(_snapshot(dns_zones=[zone]))
    dns_findings = [f for f in findings if f.rule_id == "DNS-001"]
    assert len(dns_findings) == 1
    assert dns_findings[0].confidence == "indeterminate"


def test_dns_zone_with_no_name_servers_is_high_confidence() -> None:
    zone = DnsZone(
        name="bare-zone",
        project_id=PROJECT_ID,
        dns_name="bare.example.com.",
        name_servers=[],
        observed_at=FRESHNESS,
    )
    findings = find_network_risks(_snapshot(dns_zones=[zone]))
    dns_findings = [f for f in findings if f.rule_id == "DNS-001"]
    assert len(dns_findings) == 1
    assert dns_findings[0].confidence == "high"


def test_indeterminate_confidence_findings_are_not_filtered_out() -> None:
    """``confidence="indeterminate"`` findings are first-class output --
    the FW-002 advisory itself is one, and must survive into the result."""
    snapshot = _snapshot(networks=[_network()], hierarchical_firewall_policies=[])
    findings = find_network_risks(snapshot)
    assert any(f.confidence == "indeterminate" for f in findings)
