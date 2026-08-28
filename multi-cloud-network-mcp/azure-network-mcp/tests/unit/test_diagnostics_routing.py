from __future__ import annotations

from azure_network_mcp.diagnostics.routing import evaluate_route
from azure_network_mcp.models.network_resources import EffectiveRoute

NIC_ID = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/networkInterfaces/nic-1"


def _route(prefix: str, next_hop_type: str, state: str = "Active") -> EffectiveRoute:
    return EffectiveRoute(
        name=f"route-{prefix}",
        address_prefixes=[prefix],
        next_hop_type=next_hop_type,
        source="Default",
        state=state,
    )


def test_no_effective_routes_is_indeterminate() -> None:
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=[], destination_ip="10.0.1.5", freshness="now"
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "indeterminate"


def test_no_matching_route_is_blocked() -> None:
    routes = [_route("10.1.0.0/16", "VnetLocal")]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="8.8.8.8", freshness="now"
    )
    assert verdict == "blocked"
    assert finding.severity == "medium"


def test_longest_prefix_match_wins() -> None:
    routes = [
        _route("10.0.0.0/8", "VirtualAppliance"),
        _route("10.0.1.0/24", "VnetLocal"),
    ]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="10.0.1.5", freshness="now"
    )
    assert verdict == "routable"
    assert "10.0.1.0/24" in finding.summary


def test_blackhole_route_is_blocked_high_severity() -> None:
    routes = [_route("10.0.1.0/24", "None")]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="10.0.1.5", freshness="now"
    )
    assert verdict == "blocked"
    assert finding.severity == "high"
    assert finding.remediation is not None


def test_route_to_internet_is_indeterminate() -> None:
    routes = [_route("0.0.0.0/0", "Internet")]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="8.8.8.8", freshness="now"
    )
    assert verdict == "indeterminate"
    assert finding.confidence == "medium"
    assert finding.limitations


def test_route_to_virtual_network_gateway_is_indeterminate() -> None:
    """Traffic destined for on-premises via a VPN/ExpressRoute gateway --
    this rule cannot trace further without visibility into that hop."""
    routes = [_route("192.168.0.0/16", "VirtualNetworkGateway")]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID,
        effective_routes=routes,
        destination_ip="192.168.1.5",
        freshness="now",
    )
    assert verdict == "indeterminate"


def test_inactive_routes_are_excluded_from_matching() -> None:
    routes = [_route("10.0.1.0/24", "VnetLocal", state="Invalid")]
    verdict, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="10.0.1.5", freshness="now"
    )
    assert verdict == "blocked"


def test_route_evidence_traces_back_to_matched_route() -> None:
    routes = [_route("10.0.1.0/24", "VnetLocal")]
    _, finding = evaluate_route(
        source_nic_id=NIC_ID, effective_routes=routes, destination_ip="10.0.1.5", freshness="now"
    )
    assert finding.evidence
    assert "10.0.1.0/24" in finding.evidence[0].source
