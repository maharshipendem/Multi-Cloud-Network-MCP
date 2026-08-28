from __future__ import annotations

from gcp_network_mcp.diagnostics.routing import evaluate_route, find_cidr_overlaps
from gcp_network_mcp.models.routes import Route

FRESHNESS = "2026-08-27T00:00:00Z"
NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-1"
OTHER_NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-2"


def _route(
    name: str,
    dest_range: str,
    *,
    priority: int = 1000,
    next_hop_type: str = "instance",
    network_self_link: str = NETWORK,
) -> Route:
    return Route(
        name=name,
        project_id="p",
        observed_at=FRESHNESS,
        network_self_link=network_self_link,
        dest_range=dest_range,
        priority=priority,
        next_hop_type=next_hop_type,
    )


# --------------------------------------------------------------------------
# evaluate_route (ROUTE-001)
# --------------------------------------------------------------------------


def test_no_routes_for_network_is_indeterminate() -> None:
    routes = [_route("r1", "10.0.0.0/8", network_self_link=OTHER_NETWORK)]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="10.0.0.5", freshness=FRESHNESS
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "indeterminate"
    assert finding.evidence == []  # no routes at all -- nothing to cite


def test_no_matching_route_is_blocked() -> None:
    routes = [_route("r1", "10.1.0.0/16")]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="8.8.8.8", freshness=FRESHNESS
    )
    assert verdict == "blocked"
    assert finding.severity == "medium"
    assert finding.confidence == "high"
    assert finding.evidence  # non-empty


def test_longest_prefix_match_wins_is_routable() -> None:
    routes = [
        _route("broad", "10.0.0.0/8", priority=1000),
        _route("narrow", "10.0.1.0/24", priority=1000),
    ]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="10.0.1.5", freshness=FRESHNESS
    )
    assert verdict == "routable"
    assert finding.confidence == "high"
    assert "narrow" in finding.summary
    assert finding.evidence
    assert finding.evidence[0].source == "route:narrow"


def test_priority_tiebreak_lower_number_wins() -> None:
    routes = [
        _route("high-priority-number", "10.0.1.0/24", priority=2000),
        _route("low-priority-number", "10.0.1.0/24", priority=100),
    ]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="10.0.1.5", freshness=FRESHNESS
    )
    assert verdict == "routable"
    assert "low-priority-number" in finding.summary


def test_opaque_next_hop_type_is_indeterminate_with_limitations() -> None:
    routes = [_route("via-vpn", "10.0.1.0/24", next_hop_type="vpn_tunnel")]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="10.0.1.5", freshness=FRESHNESS
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "medium"
    assert finding.limitations
    assert finding.evidence


def test_non_opaque_next_hop_type_is_high_confidence() -> None:
    routes = [_route("via-instance", "10.0.1.0/24", next_hop_type="instance")]
    verdict, finding = evaluate_route(
        network_self_link=NETWORK, routes=routes, destination_ip="10.0.1.5", freshness=FRESHNESS
    )
    assert verdict == "routable"
    assert finding.confidence == "high"
    assert finding.limitations == []


# --------------------------------------------------------------------------
# find_cidr_overlaps (ROUTE-002)
# --------------------------------------------------------------------------


def test_no_overlap_produces_no_findings() -> None:
    routes = [_route("a", "10.0.0.0/24"), _route("b", "10.0.1.0/24")]
    findings = find_cidr_overlaps(network_self_link=NETWORK, routes=routes, freshness=FRESHNESS)
    assert findings == []


def test_genuinely_overlapping_non_default_cidrs_are_flagged() -> None:
    routes = [
        _route("wide", "10.0.0.0/16", priority=1000),
        _route("narrow", "10.0.1.0/24", priority=500),
    ]
    findings = find_cidr_overlaps(network_self_link=NETWORK, routes=routes, freshness=FRESHNESS)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "medium"
    assert finding.confidence == "high"
    assert len(finding.evidence) == 2
    # lower priority *number* wins -- "narrow" (500) beats "wide" (1000)
    assert "narrow" in finding.summary
    assert "wins the overlapping range over wide" in finding.summary


def test_default_route_against_specific_route_is_excluded_as_noise() -> None:
    """A single 0.0.0.0/0 default route technically 'overlaps' every other
    route by set-containment, but that pairing is deliberately excluded
    (see routing.py's docstring/comment) since every normal network has a
    default route and it always yields to anything more specific."""
    routes = [_route("default", "0.0.0.0/0"), _route("specific", "10.0.0.0/8")]
    findings = find_cidr_overlaps(network_self_link=NETWORK, routes=routes, freshness=FRESHNESS)
    assert findings == []


def test_two_distinct_default_routes_are_still_flagged() -> None:
    """Per routing.py's own docstring: 'two distinct 0.0.0.0/0 routes
    overlapping each other is still flagged' -- the exclusion only applies
    to a default-vs-specific pairing, not default-vs-default. The code
    implements this via an XOR on prefixlen==0: it skips only when
    *exactly one* side is the default route."""
    routes = [
        _route("default-a", "0.0.0.0/0", priority=1000),
        _route("default-b", "0.0.0.0/0", priority=500),
    ]
    findings = find_cidr_overlaps(network_self_link=NETWORK, routes=routes, freshness=FRESHNESS)
    assert len(findings) == 1
    assert findings[0].evidence


def test_overlap_only_considered_within_same_network() -> None:
    routes = [
        _route("a", "10.0.0.0/16", network_self_link=NETWORK),
        _route("b", "10.0.1.0/24", network_self_link=OTHER_NETWORK),
    ]
    findings = find_cidr_overlaps(network_self_link=NETWORK, routes=routes, freshness=FRESHNESS)
    assert findings == []
