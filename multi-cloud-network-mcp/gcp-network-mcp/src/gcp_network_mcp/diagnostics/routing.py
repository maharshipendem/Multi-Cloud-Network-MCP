"""ROUTE-001: route resolution for one network toward one destination IP.
ROUTE-002: CIDR overlap detection across a network's subnetworks/routes.

Unlike Azure (which has a separate "effective route table" computation
merging system/UDR/BGP routes), GCP's ``RoutesClient.list`` already
returns every route -- subnet, static, dynamic (BGP-learned), and
peering -- as one flat list; this rule's own job is the final
longest-prefix match plus GCP's own priority tie-break, not route
merging.
"""

from __future__ import annotations

import ipaddress

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.routes import Route

ROUTE_RESOLUTION_RULE_ID = "ROUTE-001"
register_rule(
    rule_id=ROUTE_RESOLUTION_RULE_ID,
    version="1.0.0",
    title="Route resolution",
    description=(
        "Resolves the route a network would use to reach a destination IP via "
        "longest-prefix match (ties broken by GCP's own priority field, lower wins), "
        "and classifies the next hop."
    ),
    default_severity="info",
)

CIDR_OVERLAP_RULE_ID = "ROUTE-002"
register_rule(
    rule_id=CIDR_OVERLAP_RULE_ID,
    version="1.0.0",
    title="CIDR overlap",
    description=(
        "Detects overlapping destination CIDR ranges across a network's own custom "
        "static routes -- a configuration that makes the lower-priority route "
        "partially or fully unreachable for the overlapping portion."
    ),
    default_severity="medium",
)

_OPAQUE_NEXT_HOP_TYPES = {
    "internet_gateway",
    "vpn_tunnel",
    "interconnect_attachment",
    "vpc_peering",
}


def _best_match(routes: list[Route], destination_ip: str) -> Route | None:
    try:
        dest = ipaddress.ip_address(destination_ip)
    except ValueError:
        return None

    best: Route | None = None
    best_prefix_len = -1
    best_priority = 2**32
    for route in routes:
        try:
            network = ipaddress.ip_network(route.dest_range, strict=False)
        except ValueError:
            continue
        if dest not in network:
            continue
        if network.prefixlen > best_prefix_len or (
            network.prefixlen == best_prefix_len and route.priority < best_priority
        ):
            best = route
            best_prefix_len = network.prefixlen
            best_priority = route.priority
    return best


def evaluate_route(
    *, network_self_link: str, routes: list[Route], destination_ip: str, freshness: str
) -> tuple[str, Finding]:
    """Return ``(route_verdict, Finding)`` for one network -> destination
    IP evaluation. ``route_verdict`` is one of ``"routable"``,
    ``"blocked"``, or ``"indeterminate"``."""
    network_routes = [r for r in routes if r.network_self_link == network_self_link]
    if not network_routes:
        return (
            "indeterminate",
            Finding(
                rule_id=ROUTE_RESOLUTION_RULE_ID,
                rule_version="1.0.0",
                severity="info",
                confidence="indeterminate",
                summary=f"No routes were found for network {network_self_link}.",
                affected_resources=[network_self_link],
                freshness=freshness,
                limitations=["The route snapshot for this network returned no entries."],
            ),
        )

    match = _best_match(network_routes, destination_ip)
    reasoning = [
        ReasoningStep(
            step=1,
            description=(
                f"Searched {len(network_routes)} route(s) on {network_self_link} for the "
                f"longest prefix match containing {destination_ip}."
            ),
        )
    ]

    if match is None:
        return (
            "blocked",
            Finding(
                rule_id=ROUTE_RESOLUTION_RULE_ID,
                rule_version="1.0.0",
                severity="medium",
                confidence="high",
                summary=(
                    f"No route on {network_self_link} covers destination {destination_ip}; "
                    "traffic to it has no path."
                ),
                affected_resources=[network_self_link],
                evidence=[
                    Evidence(
                        source=f"routes:{network_self_link}",
                        detail=f"No route matches destination {destination_ip}.",
                    )
                ],
                reasoning=reasoning,
                freshness=freshness,
            ),
        )

    evidence = [
        Evidence(
            source=f"route:{match.name}",
            detail=(
                f"dest_range={match.dest_range}, priority={match.priority}, "
                f"next_hop_type={match.next_hop_type}"
            ),
        )
    ]
    reasoning.append(
        ReasoningStep(
            step=2,
            description=f"Matched route {match.name} (dest_range={match.dest_range}).",
            evidence_indices=[0],
        )
    )

    verdict = "indeterminate" if match.next_hop_type in _OPAQUE_NEXT_HOP_TYPES else "routable"
    confidence = "medium" if verdict == "indeterminate" else "high"
    limitations = (
        [
            f"next_hop_type={match.next_hop_type} leaves the analyzed scope (the internet, a "
            "VPN tunnel, an Interconnect attachment, or a peered network) -- this rule cannot "
            "trace the path further without visibility into that target."
        ]
        if verdict == "indeterminate"
        else []
    )
    return (
        verdict,
        Finding(
            rule_id=ROUTE_RESOLUTION_RULE_ID,
            rule_version="1.0.0",
            severity="info",
            confidence=confidence,
            summary=(
                f"Route {match.name} on {network_self_link} directs traffic to "
                f"{destination_ip} via next_hop_type={match.next_hop_type}."
            ),
            affected_resources=[network_self_link],
            evidence=evidence,
            reasoning=reasoning,
            limitations=limitations,
            freshness=freshness,
        ),
    )


def find_cidr_overlaps(
    *, network_self_link: str, routes: list[Route], freshness: str
) -> list[Finding]:
    """Custom static/dynamic routes on the same network whose
    ``dest_range`` overlaps -- the lower-priority route (or, at equal
    priority, an arbitrary but deterministic loser) never gets used for
    the overlapping portion. A route's overlap against the network's own
    catch-all default route (0.0.0.0/0) is never flagged -- every normal
    network has one, and it always yields to any more specific route by
    design, so flagging that pairing would be pure noise; two distinct
    0.0.0.0/0 routes overlapping each other is still flagged."""
    candidates = [r for r in routes if r.network_self_link == network_self_link]
    findings: list[Finding] = []
    for i, route_a in enumerate(candidates):
        try:
            net_a = ipaddress.ip_network(route_a.dest_range, strict=False)
        except ValueError:
            continue
        for route_b in candidates[i + 1 :]:
            try:
                net_b = ipaddress.ip_network(route_b.dest_range, strict=False)
            except ValueError:
                continue
            if not net_a.overlaps(net_b):
                continue
            if (net_a.prefixlen == 0) != (net_b.prefixlen == 0):
                continue  # one side is the ordinary default route -- not a real overlap
            loser = route_a if route_a.priority >= route_b.priority else route_b
            winner = route_b if loser is route_a else route_a
            findings.append(
                Finding(
                    rule_id=CIDR_OVERLAP_RULE_ID,
                    rule_version="1.0.0",
                    severity="medium",
                    confidence="high",
                    summary=(
                        f"Routes {route_a.name} ({route_a.dest_range}) and {route_b.name} "
                        f"({route_b.dest_range}) overlap on {network_self_link}; "
                        f"{winner.name} (priority={winner.priority}) wins the overlapping "
                        f"range over {loser.name} (priority={loser.priority})."
                    ),
                    affected_resources=[network_self_link, route_a.name, route_b.name],
                    evidence=[
                        Evidence(
                            source=f"route:{route_a.name}",
                            detail=f"dest_range={route_a.dest_range}, priority={route_a.priority}",
                        ),
                        Evidence(
                            source=f"route:{route_b.name}",
                            detail=f"dest_range={route_b.dest_range}, priority={route_b.priority}",
                        ),
                    ],
                    reasoning=[
                        ReasoningStep(
                            step=1,
                            description=(
                                f"{route_a.dest_range} and {route_b.dest_range} overlap; "
                                "the lower-priority-number route wins ties, GCP's own rule."
                            ),
                            evidence_indices=[0, 1],
                        )
                    ],
                    freshness=freshness,
                    remediation=(
                        f"If both routes are intentional, confirm {loser.name}'s remaining "
                        "non-overlapping range still serves its purpose; otherwise narrow or "
                        "remove one of the two routes."
                    ),
                )
            )
    return findings


__all__ = [
    "CIDR_OVERLAP_RULE_ID",
    "ROUTE_RESOLUTION_RULE_ID",
    "evaluate_route",
    "find_cidr_overlaps",
]
