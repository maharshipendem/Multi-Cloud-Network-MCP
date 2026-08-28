from __future__ import annotations

from gcp_network_mcp.diagnostics.dns import evaluate_zone
from gcp_network_mcp.models.dns import DnsZone

FRESHNESS = "2026-08-27T00:00:00Z"


def _zone(*, name_servers: list[str] | None = None) -> DnsZone:
    return DnsZone(
        name="zone-1",
        project_id="p",
        dns_name="example.com.",
        name_servers=name_servers if name_servers is not None else ["ns1.example.com."],
        observed_at=FRESHNESS,
    )


def test_zone_with_no_name_servers_is_flagged_at_full_confidence() -> None:
    """This is the one fact evaluate_zone CAN check directly, so it does
    not degrade to indeterminate the way the forwarding-chain check does."""
    finding = evaluate_zone(zone=_zone(name_servers=[]), freshness=FRESHNESS)
    assert finding.severity == "medium"
    assert finding.confidence == "high"
    assert finding.confidence != "indeterminate"
    assert finding.evidence
    assert finding.limitations


def test_zone_with_name_servers_is_indeterminate_by_design() -> None:
    """No available Google-published client library exposes forwarding/
    peering/Policy/Response-Policy configuration -- evaluate_zone is
    deliberately confidence='indeterminate' for every zone that does have
    name servers, per the module's own docstring."""
    finding = evaluate_zone(
        zone=_zone(name_servers=["ns1.example.com.", "ns2.example.com."]), freshness=FRESHNESS
    )
    assert finding.confidence == "indeterminate"
    assert finding.severity == "info"
    assert finding.evidence
    assert finding.limitations
    assert "forwarding" in finding.limitations[0].lower() or "forwarding" in finding.summary.lower()


def test_zone_evidence_cites_the_zone_by_name() -> None:
    finding = evaluate_zone(zone=_zone(), freshness=FRESHNESS)
    assert finding.evidence[0].source == "dns_zone:zone-1"


def test_no_name_servers_vs_has_name_servers_differ_in_confidence() -> None:
    no_ns = evaluate_zone(zone=_zone(name_servers=[]), freshness=FRESHNESS)
    has_ns = evaluate_zone(zone=_zone(name_servers=["ns1.example.com."]), freshness=FRESHNESS)
    assert no_ns.confidence != has_ns.confidence
    assert no_ns.confidence == "high"
    assert has_ns.confidence == "indeterminate"
