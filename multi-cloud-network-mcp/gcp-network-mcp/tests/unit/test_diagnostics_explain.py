"""Unit tests for ``diagnostics.explain.explain_network_path`` -- runs
ROUTE-001/FW-001/FW-002 against an already-collected
``HybridNetworkSnapshot`` and combines their verdicts into one
``overall_verdict``. Tested here via directly-constructed snapshots."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.explain import explain_network_path
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.firewall import (
    FirewallPolicy,
    FirewallPolicyRule,
    FirewallRule,
    ProtocolPorts,
    implied_firewall_rules,
)
from gcp_network_mcp.models.routes import Route

PROJECT_ID = "test-project-1"
NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
FRESHNESS = "2026-01-01T00:00:00Z"


def _snapshot(**overrides: object) -> HybridNetworkSnapshot:
    return HybridNetworkSnapshot(project_id=PROJECT_ID, observed_at=FRESHNESS, **overrides)


def _route(*, dest_range: str = "10.0.0.0/24", priority: int = 1000) -> Route:
    return Route(
        name="route-1",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        dest_range=dest_range,
        priority=priority,
        next_hop_type="instance",
        next_hop_target="some-instance",
        observed_at=FRESHNESS,
    )


def _allow_ingress_rule(*, priority: int = 1000) -> FirewallRule:
    return FirewallRule(
        name="allow-ssh",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        direction="INGRESS",
        priority=priority,
        disabled=False,
        action="ALLOW",
        allowed=[ProtocolPorts(ip_protocol="tcp", ports=["22"])],
        source_ranges=["0.0.0.0/0"],
        observed_at=FRESHNESS,
    )


def _hierarchical_policy(*, action: str, priority: int = 100) -> FirewallPolicy:
    return FirewallPolicy(
        name="org-policy",
        scope="hierarchical",
        observed_at=FRESHNESS,
        rules=[
            FirewallPolicyRule(
                priority=priority,
                action=action,
                direction="INGRESS",
                disabled=False,
                rule_name="org-rule",
            )
        ],
    )


def test_overall_allowed_only_when_every_layer_agrees() -> None:
    """route routable + firewall ALLOW + no hierarchical override => allowed."""
    snapshot = _snapshot(
        routes=[_route(dest_range="10.0.0.0/24")],
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "routable"
    assert result.firewall_verdict == "ALLOW"
    assert result.overall_verdict == "allowed"
    assert len(result.findings) == 3


def test_overall_blocked_when_network_level_firewall_denies() -> None:
    """A DENY at the network-level layer alone (no hierarchical policies
    supplied) is enough to force 'blocked', even though the route itself
    is perfectly routable."""
    snapshot = _snapshot(
        routes=[_route(dest_range="10.0.0.0/24")],
        # No custom ALLOW rule -- only the implied deny-all-ingress default applies.
        firewall_rules=implied_firewall_rules(
            network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"
        ),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "routable"
    assert result.firewall_verdict == "DENY"
    assert result.overall_verdict == "blocked"


def test_overall_blocked_when_route_itself_has_no_path() -> None:
    snapshot = _snapshot(
        routes=[_route(dest_range="192.168.0.0/24")],  # doesn't cover 10.0.0.5
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "blocked"
    assert result.overall_verdict == "blocked"


def test_hierarchical_deny_overrides_network_level_allow_to_force_blocked() -> None:
    """Regression: even when the route AND the network-level firewall
    rules would both independently conclude 'allowed', a hierarchical
    Firewall Policy DENY at higher precedence must still force
    'blocked' overall -- GCP evaluates hierarchical policies before VPC
    rules for ingress traffic, so a hierarchical DENY always wins."""
    snapshot = _snapshot(
        routes=[_route(dest_range="10.0.0.0/24")],
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
        hierarchical_firewall_policies=[_hierarchical_policy(action="deny")],
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    # Absent the hierarchical override, both underlying layers would say allowed.
    assert result.route_verdict == "routable"
    # The network-level firewall verdict was ALLOW, but the reported
    # firewall_verdict reflects the hierarchical override.
    assert result.firewall_verdict == "DENY"
    assert result.overall_verdict == "blocked"


def test_hierarchical_allow_agreeing_with_network_level_allow_stays_allowed() -> None:
    snapshot = _snapshot(
        routes=[_route(dest_range="10.0.0.0/24")],
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
        hierarchical_firewall_policies=[_hierarchical_policy(action="allow")],
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.overall_verdict == "allowed"


def test_overall_partially_evaluated_when_route_evidence_incomplete_never_upgraded_to_allowed() -> (
    None
):
    """Regression: when a layer's evidence is incomplete (here: no routes
    at all for this network, so ROUTE-001 returns 'indeterminate'), the
    overall verdict must be 'partially_evaluated' -- never silently
    upgraded to 'allowed' even though the firewall layer alone would say
    ALLOW."""
    snapshot = _snapshot(
        routes=[],  # no routes at all for this network -> route_verdict == "indeterminate"
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "indeterminate"
    assert result.firewall_verdict == "ALLOW"
    assert result.overall_verdict == "partially_evaluated"
    assert result.overall_verdict != "allowed"


def test_overall_partially_evaluated_when_firewall_evidence_incomplete() -> None:
    """Same regression, from the firewall layer's side: no firewall rules
    at all (not even the implied defaults) makes FW-001 'indeterminate';
    overall must be 'partially_evaluated', not 'allowed'."""
    snapshot = _snapshot(routes=[_route(dest_range="10.0.0.0/24")], firewall_rules=[])

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "routable"
    assert result.firewall_verdict == "indeterminate"
    assert result.overall_verdict == "partially_evaluated"


def test_route_via_opaque_next_hop_is_indeterminate_not_blocked_or_allowed() -> None:
    """A route whose next hop is opaque (e.g. a VPN tunnel) can't be
    traced further by ROUTE-001 -- it's 'indeterminate', not 'routable'
    or 'blocked', and the overall verdict reflects that."""
    opaque_route = Route(
        name="route-vpn",
        project_id=PROJECT_ID,
        network_self_link=NETWORK_SELF_LINK,
        dest_range="10.0.0.0/24",
        priority=1000,
        next_hop_type="vpn_tunnel",
        next_hop_target="some-tunnel",
        observed_at=FRESHNESS,
    )
    snapshot = _snapshot(
        routes=[opaque_route],
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.route_verdict == "indeterminate"
    assert result.overall_verdict == "partially_evaluated"


def test_findings_and_metadata_are_carried_through() -> None:
    snapshot = _snapshot(
        routes=[_route(dest_range="10.0.0.0/24")],
        firewall_rules=[_allow_ingress_rule()]
        + implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1"),
    )

    result = explain_network_path(
        snapshot,
        network_self_link=NETWORK_SELF_LINK,
        destination_ip="10.0.0.5",
        destination_port=22,
        protocol="tcp",
    )

    assert result.network_self_link == NETWORK_SELF_LINK
    assert result.destination_ip == "10.0.0.5"
    assert result.destination_port == 22
    assert result.protocol == "tcp"
    rule_ids = {f.rule_id for f in result.findings}
    assert rule_ids == {"ROUTE-001", "FW-001", "FW-002"}
