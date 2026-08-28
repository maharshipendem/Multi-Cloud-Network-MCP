"""ROUTE-001: effective-route resolution for one source NIC toward one
destination IP.

Unlike this project's AWS sibling (which reimplements route-table
longest-prefix-match and static-vs-propagated tie-breaking from scratch),
this rule leverages Azure's own effective route table computation
(``azure_get_effective_route_table`` / ``arm.route_tables.get_effective_route_table``)
-- Azure has already merged system routes, user-defined routes, and
BGP-propagated routes (including vWAN hub route-map/routing-intent
effects) into one list before this rule ever runs. This rule's own job is
only the final longest-prefix match against the destination and next-hop
classification, not route merging.
"""

from __future__ import annotations

import ipaddress

from azure_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from azure_network_mcp.models.network_resources import EffectiveRoute

RULE_ID = "ROUTE-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Effective route resolution",
    description=(
        "Resolves the effective route (from Azure's own merged system/UDR/BGP "
        "route computation) a source NIC would use to reach a destination IP, "
        "and classifies the next hop."
    ),
    default_severity="info",
)

# Next-hop types that terminate the path outside this analysis's visibility
# (a hop this rule cannot itself trace further) rather than a local/known target.
_OPAQUE_NEXT_HOP_TYPES = {
    "Internet",
    "VirtualNetworkGateway",
    "VirtualNetworkServiceEndpoint",
    "HyperNetGateway",
}


def _longest_prefix_match(
    effective_routes: list[EffectiveRoute], destination_ip: str
) -> EffectiveRoute | None:
    try:
        dest = ipaddress.ip_address(destination_ip)
    except ValueError:
        return None

    best: EffectiveRoute | None = None
    best_prefix_len = -1
    for route in effective_routes:
        if route.state and route.state != "Active":
            continue
        for prefix in route.address_prefixes:
            try:
                network = ipaddress.ip_network(prefix, strict=False)
            except ValueError:
                continue
            if dest in network and network.prefixlen > best_prefix_len:
                best = route
                best_prefix_len = network.prefixlen
    return best


def evaluate_route(
    *,
    source_nic_id: str,
    effective_routes: list[EffectiveRoute],
    destination_ip: str,
    freshness: str,
) -> tuple[str, Finding]:
    """Return ``(route_verdict, Finding)`` for one source NIC -> destination
    IP evaluation. ``route_verdict`` is one of ``"routable"``,
    ``"blocked"``, or ``"indeterminate"``."""
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []

    if not effective_routes:
        return (
            "indeterminate",
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="info",
                confidence="indeterminate",
                summary=(
                    f"No effective routes were available for NIC {source_nic_id}; route "
                    "resolution toward the destination could not be determined."
                ),
                affected_resources=[source_nic_id],
                freshness=freshness,
                limitations=[
                    "The effective route table for this NIC returned no entries -- it may "
                    "not exist, may be in a subnet without a route table, or the identity "
                    "may lack the effectiveRouteTable/action permission."
                ],
            ),
        )

    match = _longest_prefix_match(effective_routes, destination_ip)
    reasoning.append(
        ReasoningStep(
            step=1,
            description=(
                f"Searched {len(effective_routes)} effective route(s) on NIC {source_nic_id} "
                f"for the longest prefix match containing {destination_ip}."
            ),
        )
    )

    if match is None:
        evidence.append(
            Evidence(
                source=f"effective_route_table:{source_nic_id}",
                detail=f"No effective route matches destination {destination_ip}.",
            )
        )
        return (
            "blocked",
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="medium",
                confidence="high",
                summary=(
                    f"No effective route on NIC {source_nic_id} covers destination "
                    f"{destination_ip}; traffic to it has no path."
                ),
                affected_resources=[source_nic_id],
                evidence=evidence,
                reasoning=reasoning,
                freshness=freshness,
            ),
        )

    prefixes = ", ".join(match.address_prefixes)
    evidence.append(
        Evidence(
            source=f"effective_route:{prefixes}",
            detail=(
                f"next_hop_type={match.next_hop_type}, source={match.source}, state={match.state}"
            ),
        )
    )
    reasoning.append(
        ReasoningStep(
            step=2,
            description=f"Matched route {prefixes} (source={match.source}).",
            evidence_indices=[0],
        )
    )

    if match.next_hop_type == "None":
        return (
            "blocked",
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="high",
                confidence="high",
                summary=(
                    f"Route {prefixes} on NIC {source_nic_id} has next_hop_type='None' "
                    f"(a deliberate blackhole/drop route) -- traffic to {destination_ip} "
                    "is dropped."
                ),
                affected_resources=[source_nic_id],
                evidence=evidence,
                reasoning=reasoning,
                freshness=freshness,
                remediation=(
                    "If this route is unintentional, review the user-defined route table "
                    "associated with this NIC's subnet."
                ),
            ),
        )

    verdict = "indeterminate" if match.next_hop_type in _OPAQUE_NEXT_HOP_TYPES else "routable"
    confidence = "medium" if verdict == "indeterminate" else "high"
    limitations = (
        [
            f"next_hop_type={match.next_hop_type} leaves the analyzed scope "
            "(a VPN/ExpressRoute gateway, the internet, or a service endpoint) -- this "
            "rule cannot trace the path further without visibility into that target."
        ]
        if verdict == "indeterminate"
        else []
    )
    return (
        verdict,
        Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="info",
            confidence=confidence,
            summary=(
                f"Route {prefixes} on NIC {source_nic_id} directs traffic to "
                f"{destination_ip} via next_hop_type={match.next_hop_type}."
            ),
            affected_resources=[source_nic_id],
            evidence=evidence,
            reasoning=reasoning,
            limitations=limitations,
            freshness=freshness,
        ),
    )


__all__ = ["RULE_ID", "evaluate_route"]
