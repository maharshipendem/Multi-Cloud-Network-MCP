"""Deterministic route resolution: longest-prefix-match walk from a source
subnet/ENI/IP toward a destination IP/CIDR, across local/NAT/IGW/EIGW/
peering/TGW/endpoint/blackhole targets.

This mirrors exactly what AWS's route selection algorithm does -- longest
prefix match, static routes preferred over propagated routes on a tie --
and nothing more: it does not evaluate security groups or NACLs (that is
``diagnostics.security``'s job) and it does not claim reachability by
itself (``aws_explain_network_path`` combines this module's verdict with
the security evaluation before saying anything about whether traffic
actually gets through).
"""

from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import BaseModel, Field

from aws_cloudops_mcp.diagnostics.models import (
    Confidence,
    Evidence,
    Finding,
    ReasoningStep,
    Severity,
    register_rule,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Route, RouteTable
from aws_cloudops_mcp.models.transit_gateway import TransitGatewayRoute

RULE_ROUTE_RESOLUTION = register_rule(
    rule_id="ROUTE-001",
    version="1.0.0",
    title="Route resolution",
    description=(
        "Resolves the route table entry a packet from a given source would "
        "match for a given destination, via longest-prefix match with "
        "AWS's static-over-propagated tie-break, walking through NAT/"
        "peering/TGW hops until the path terminates or leaves the "
        "analyzed snapshot's scope."
    ),
    default_severity="info",
)

# Route target types this engine treats as a hop it can continue resolving
# through (NAT re-enters the loop from the NAT's own subnet; peering/TGW
# re-enter from the peer VPC's own route tables, if that VPC is in scope).
_CONTINUABLE_TARGET_TYPES = {"nat_gateway", "vpc_peering_connection", "transit_gateway"}

# Terminal target types this engine can resolve completely by itself --
# the path structurally ends here (egress to the internet, an AWS service
# via a gateway endpoint, an appliance ENI, IPv6 egress-only).
_TERMINAL_TARGET_TYPES = {
    "gateway",
    "egress_only_internet_gateway",
    "vpc_endpoint",
    "network_interface",
}

PathVerdict = Literal[
    "routable",
    "blocked_at_routing",
    "left_analyzed_scope",
    "unresolved_target",
    "indeterminate",
]

_MAX_HOPS = 12


class PathHop(BaseModel):
    """One resolved step of a route-resolution walk."""

    hop_number: int
    vpc_id: str
    location_id: str
    route_table_id: str | None = None
    matched_route: Route | None = None
    target_type: str | None = None
    description: str


class RouteResolutionResult(BaseModel):
    verdict: PathVerdict
    hops: list[PathHop] = Field(default_factory=list)
    finding: Finding


class _Candidate(BaseModel):
    route: Route
    prefix_length: int
    is_propagated: bool


def _contains(
    outer: ipaddress.IPv4Network | ipaddress.IPv6Network,
    inner: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> bool:
    """Whether ``inner`` is ``outer`` or a subnet of it. IPv4/IPv6 never
    contain one another -- ``subnet_of`` raises on a version mismatch
    rather than returning False, so that case is handled explicitly."""
    if outer.version != inner.version:
        return False
    return inner == outer or inner.subnet_of(outer)  # type: ignore[arg-type]


def _network_of(cidr: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return None


def _destination_network(
    destination: str,
) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(destination, strict=False)
    except ValueError:
        try:
            addr = ipaddress.ip_address(destination)
            return ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}")
        except ValueError:
            return None


def _route_destination_network(
    route: Route,
) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    cidr = route.destination_cidr_block or route.destination_ipv6_cidr_block
    if not cidr:
        return None
    return _network_of(cidr)


def _prefix_list_networks(
    snapshot: NetworkSnapshot, prefix_list_id: str
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None:
    """Return the CIDRs a managed prefix list expands to, or ``None`` if
    the prefix list (or its entries) isn't in the snapshot -- distinct
    from an empty list, which means "present, and genuinely has zero
    entries.\""""
    pl = next(
        (p for p in snapshot.managed_prefix_lists if p.prefix_list_id == prefix_list_id), None
    )
    if pl is None or pl.entries is None:
        return None
    return [n for n in (_network_of(e.cidr) for e in pl.entries) if n is not None]


def _best_matching_route(
    route_table: RouteTable,
    destination: ipaddress.IPv4Network | ipaddress.IPv6Network,
    snapshot: NetworkSnapshot,
) -> tuple[Route | None, list[str]]:
    """Longest-prefix match across a route table's entries.

    Static routes win a tie over propagated routes at the same prefix
    length, matching AWS's documented precedence. Returns the winning
    route (or ``None`` if nothing matches) plus a list of human-readable
    notes about anything that could not be conclusively evaluated (an
    unresolved prefix-list route) -- the caller decides how that affects
    confidence.
    """
    candidates: list[_Candidate] = []
    unresolved_notes: list[str] = []

    for route in route_table.routes:
        if route.target == "local":
            net = _network_of(route.destination_cidr_block or "")
            if net and _contains(net, destination):
                candidates.append(
                    _Candidate(route=route, prefix_length=net.prefixlen, is_propagated=False)
                )
            continue

        if route.destination_prefix_list_id:
            networks = _prefix_list_networks(snapshot, route.destination_prefix_list_id)
            if networks is None:
                unresolved_notes.append(
                    f"route to prefix list {route.destination_prefix_list_id} "
                    f"(target {route.target_type}:{route.target}) could not be evaluated -- "
                    "prefix list entries were not included in this snapshot"
                )
                continue
            best_pl_prefix = -1
            for net in networks:
                if _contains(net, destination):
                    best_pl_prefix = max(best_pl_prefix, net.prefixlen)
            if best_pl_prefix >= 0:
                candidates.append(
                    _Candidate(
                        route=route, prefix_length=best_pl_prefix, is_propagated=route.is_propagated
                    )
                )
            continue

        net = _route_destination_network(route)
        if net is None:
            continue
        if _contains(net, destination):
            candidates.append(
                _Candidate(
                    route=route, prefix_length=net.prefixlen, is_propagated=route.is_propagated
                )
            )

    if not candidates:
        return None, unresolved_notes

    candidates.sort(key=lambda c: (c.prefix_length, not c.is_propagated), reverse=True)
    best_prefix = candidates[0].prefix_length
    tied = [c for c in candidates if c.prefix_length == best_prefix]
    static_tied = [c for c in tied if not c.is_propagated]
    winner = static_tied[0] if static_tied else tied[0]
    return winner.route, unresolved_notes


def _best_matching_tgw_route(
    snapshot: NetworkSnapshot, destination: ipaddress.IPv4Network | ipaddress.IPv6Network
) -> TransitGatewayRoute | None:
    """Longest-prefix match across the Transit Gateway routes included in
    this snapshot."""
    best_route: TransitGatewayRoute | None = None
    best_prefix = -1
    for tgw_route in snapshot.transit_gateway_routes:
        if not tgw_route.destination_cidr_block:
            continue
        net = _network_of(tgw_route.destination_cidr_block)
        if net is None:
            continue
        if _contains(net, destination) and net.prefixlen > best_prefix:
            best_prefix = net.prefixlen
            best_route = tgw_route
    return best_route


def _subnet_containing_ip(
    snapshot: NetworkSnapshot, vpc_id: str, ip: ipaddress.IPv4Network | ipaddress.IPv6Network
) -> str | None:
    for subnet in snapshot.subnets:
        if subnet.vpc_id != vpc_id:
            continue
        net = _network_of(subnet.cidr_block)
        if net and _contains(net, ip):
            return subnet.subnet_id
    return None


def _resolve_source(
    snapshot: NetworkSnapshot,
    *,
    source_subnet_id: str | None,
    source_eni_id: str | None,
    source_ip: str | None,
    vpc_id: str | None,
) -> tuple[str, str, list[Evidence]] | None:
    """Resolve a source specification down to (vpc_id, subnet_id). Returns
    ``None`` if it cannot be resolved from the snapshot at all."""
    evidence: list[Evidence] = []
    if source_eni_id:
        eni = snapshot.eni_by_id(source_eni_id)
        if eni is None or not eni.subnet_id or not eni.vpc_id:
            return None
        evidence.append(
            Evidence(
                source=f"network_interface:{source_eni_id}",
                detail=f"SubnetId={eni.subnet_id} VpcId={eni.vpc_id}",
            )
        )
        return eni.vpc_id, eni.subnet_id, evidence

    if source_subnet_id:
        subnet = snapshot.subnet_by_id(source_subnet_id)
        if subnet is None:
            return None
        evidence.append(
            Evidence(
                source=f"subnet:{source_subnet_id}",
                detail=f"VpcId={subnet.vpc_id} CidrBlock={subnet.cidr_block}",
            )
        )
        return subnet.vpc_id, source_subnet_id, evidence

    if source_ip and vpc_id:
        net = _destination_network(source_ip)
        if net is None:
            return None
        subnet_id = _subnet_containing_ip(snapshot, vpc_id, net)
        if subnet_id is None:
            return None
        evidence.append(
            Evidence(
                source=f"subnet:{subnet_id}",
                detail=f"CIDR contains source IP {source_ip}",
            )
        )
        return vpc_id, subnet_id, evidence

    return None


def _next_hop_location(
    snapshot: NetworkSnapshot,
    route: Route,
    current_vpc_id: str,
    dest_net: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> tuple[str, str] | None:
    """Where a continuable route (NAT/peering/TGW) leads next, as
    (vpc_id, subnet_id) -- or ``None`` if that location isn't resolvable
    from the snapshot (the peer VPC/attachment target isn't included in
    this snapshot, or the destination doesn't fall in any of its
    subnets)."""
    if route.target_type == "nat_gateway":
        nat = next((n for n in snapshot.nat_gateways if n.nat_gateway_id == route.target), None)
        if nat is None or not nat.subnet_id:
            return None
        return current_vpc_id, nat.subnet_id

    if route.target_type == "vpc_peering_connection":
        pcx = next(
            (
                p
                for p in snapshot.vpc_peering_connections
                if p.vpc_peering_connection_id == route.target
            ),
            None,
        )
        if pcx is None:
            return None
        peer_vpc_id = (
            pcx.accepter.vpc_id if pcx.requester.vpc_id == current_vpc_id else pcx.requester.vpc_id
        )
        if not peer_vpc_id or snapshot.vpc_by_id(peer_vpc_id) is None:
            return None
        peer_subnet_id = _subnet_containing_ip(snapshot, peer_vpc_id, dest_net)
        if peer_subnet_id is None:
            return None
        return peer_vpc_id, peer_subnet_id

    if route.target_type == "transit_gateway":
        tgw_route = _best_matching_tgw_route(snapshot, dest_net)
        if tgw_route is None:
            return None
        vpc_attachment = next(
            (a for a in tgw_route.attachments if a.resource_type == "vpc" and a.resource_id),
            None,
        )
        if vpc_attachment is None or vpc_attachment.resource_id is None:
            return None
        target_vpc_id = vpc_attachment.resource_id
        if snapshot.vpc_by_id(target_vpc_id) is None:
            return None
        target_subnet_id = _subnet_containing_ip(snapshot, target_vpc_id, dest_net)
        if target_subnet_id is None:
            return None
        return target_vpc_id, target_subnet_id

    return None


def resolve_path(
    snapshot: NetworkSnapshot,
    *,
    destination: str,
    source_subnet_id: str | None = None,
    source_eni_id: str | None = None,
    source_ip: str | None = None,
    vpc_id: str | None = None,
) -> RouteResolutionResult:
    """Resolve the routing path from a source to ``destination``.

    Exactly one of ``source_eni_id``, ``source_subnet_id``, or
    (``source_ip`` + ``vpc_id``) must identify the source; the first one
    provided (in that order) wins if more than one is given.
    """
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []
    limitations: list[str] = []
    hops: list[PathHop] = []
    freshness = snapshot.collected_at

    def finalize(
        verdict: PathVerdict,
        confidence: Confidence,
        summary: str,
        *,
        affected: list[str],
        remediation: str | None,
    ) -> RouteResolutionResult:
        severity: Severity = "medium" if verdict == "blocked_at_routing" else "info"
        finding = Finding(
            rule_id=RULE_ROUTE_RESOLUTION.rule_id,
            rule_version=RULE_ROUTE_RESOLUTION.version,
            severity=severity,
            confidence=confidence,
            summary=summary,
            affected_resources=affected,
            evidence=list(evidence),
            reasoning=list(reasoning),
            assumptions=[],
            limitations=list(limitations),
            freshness=freshness,
            remediation=remediation,
        )
        return RouteResolutionResult(verdict=verdict, hops=list(hops), finding=finding)

    def indeterminate(summary: str, extra_limitations: list[str]) -> RouteResolutionResult:
        limitations.extend(extra_limitations)
        return finalize("indeterminate", "indeterminate", summary, affected=[], remediation=None)

    dest_net = _destination_network(destination)
    if dest_net is None:
        return indeterminate(
            f"'{destination}' is not a valid IP address or CIDR block.",
            [f"could not parse destination '{destination}'"],
        )

    resolved = _resolve_source(
        snapshot,
        source_subnet_id=source_subnet_id,
        source_eni_id=source_eni_id,
        source_ip=source_ip,
        vpc_id=vpc_id,
    )
    if resolved is None:
        return indeterminate(
            "Could not resolve the source to a subnet within the analyzed snapshot.",
            ["source ENI/subnet/IP was not found in the collected snapshot"],
        )
    current_vpc_id, current_subnet_id, source_evidence = resolved
    evidence.extend(source_evidence)
    reasoning.append(
        ReasoningStep(
            step=1,
            description=f"Resolved source to subnet {current_subnet_id} in VPC {current_vpc_id}.",
            evidence_indices=list(range(len(evidence))),
        )
    )

    visited: set[tuple[str, str]] = set()
    confidence: Confidence = "high"

    for hop_number in range(1, _MAX_HOPS + 1):
        visit_key = (current_vpc_id, current_subnet_id)
        if visit_key in visited:
            return indeterminate(
                f"Route resolution revisited subnet {current_subnet_id} -- a routing "
                "cycle exists between the hops walked so far.",
                ["route table cycle detected; resolution stopped to avoid an infinite loop"],
            )
        visited.add(visit_key)

        route_table = snapshot.route_table_for_subnet(current_subnet_id, current_vpc_id)
        if route_table is None:
            return indeterminate(
                f"Subnet {current_subnet_id} has no associated route table (explicit or "
                "main) in the analyzed snapshot.",
                [f"no route table found for subnet {current_subnet_id}"],
            )

        route, unresolved_notes = _best_matching_route(route_table, dest_net, snapshot)
        if unresolved_notes:
            limitations.extend(unresolved_notes)
            if confidence == "high":
                confidence = "medium"

        if route is None:
            evidence.append(
                Evidence(
                    source=f"route_table:{route_table.route_table_id}",
                    detail=f"no route matches destination {destination}",
                )
            )
            reasoning.append(
                ReasoningStep(
                    step=hop_number + 1,
                    description=(
                        f"No route in {route_table.route_table_id} matches {destination}."
                    ),
                    evidence_indices=[len(evidence) - 1],
                )
            )
            hops.append(
                PathHop(
                    hop_number=hop_number,
                    vpc_id=current_vpc_id,
                    location_id=current_subnet_id,
                    route_table_id=route_table.route_table_id,
                    matched_route=None,
                    target_type=None,
                    description=(
                        "No matching route; destination is unreachable at the routing layer."
                    ),
                )
            )
            return finalize(
                "blocked_at_routing",
                "high" if confidence == "high" else confidence,
                f"No route to {destination} exists in {route_table.route_table_id}.",
                affected=[route_table.route_table_id, current_subnet_id],
                remediation=(
                    f"Add a route for {destination} (or a covering CIDR) to "
                    f"{route_table.route_table_id} if traffic to this destination is expected "
                    "to succeed."
                ),
            )

        dest_desc = route.destination_cidr_block or route.destination_prefix_list_id or "?"
        evidence.append(
            Evidence(
                source=f"route_table:{route_table.route_table_id}",
                detail=(
                    f"{dest_desc} -> {route.target_type}:{route.target} "
                    f"(state={route.state}, origin={route.origin})"
                ),
            )
        )
        reasoning.append(
            ReasoningStep(
                step=hop_number + 1,
                description=(
                    f"Longest-prefix match in {route_table.route_table_id}: {dest_desc} -> "
                    f"{route.target_type}:{route.target}."
                ),
                evidence_indices=[len(evidence) - 1],
            )
        )
        hops.append(
            PathHop(
                hop_number=hop_number,
                vpc_id=current_vpc_id,
                location_id=current_subnet_id,
                route_table_id=route_table.route_table_id,
                matched_route=route,
                target_type=route.target_type,
                description=f"Matched route to {route.target_type}:{route.target}.",
            )
        )

        if route.state == "blackhole":
            return finalize(
                "blocked_at_routing",
                "high",
                f"Route to {destination} in {route_table.route_table_id} is a blackhole "
                f"(target {route.target_type}:{route.target} no longer exists).",
                affected=[route_table.route_table_id, str(route.target)],
                remediation=(
                    f"The route's target ({route.target}) no longer exists. Remove or "
                    "replace the blackholed route."
                ),
            )

        if route.target == "local":
            dest_subnet_id = _subnet_containing_ip(snapshot, current_vpc_id, dest_net)
            description = (
                f"Destination {destination} is local to VPC {current_vpc_id}"
                + (f" (subnet {dest_subnet_id})" if dest_subnet_id else "")
                + "."
            )
            return finalize(
                "routable",
                confidence,
                description,
                affected=[current_vpc_id],
                remediation=None,
            )

        if route.target_type in _TERMINAL_TARGET_TYPES:
            return finalize(
                "routable",
                confidence,
                f"Path terminates via {route.target_type}:{route.target}.",
                affected=[str(route.target)],
                remediation=None,
            )

        if route.target_type not in _CONTINUABLE_TARGET_TYPES:
            limitations.append(
                f"target type '{route.target_type}' for {route.target} is not resolvable "
                "within this diagnostic engine's scope"
            )
            return finalize(
                "unresolved_target",
                "indeterminate",
                f"Route resolves to {route.target_type}:{route.target}, a target type this "
                "engine does not resolve further.",
                affected=[str(route.target)],
                remediation=None,
            )

        # Continuable: nat_gateway, vpc_peering_connection, transit_gateway.
        next_location = _next_hop_location(snapshot, route, current_vpc_id, dest_net)
        if next_location is None:
            limitations.append(
                f"target {route.target_type}:{route.target} leaves the resources included "
                "in this snapshot; resolution cannot continue past this hop"
            )
            return finalize(
                "left_analyzed_scope",
                "indeterminate",
                f"Path exits via {route.target_type}:{route.target}, outside this "
                "snapshot's collected scope.",
                affected=[str(route.target)],
                remediation=None,
            )
        current_vpc_id, current_subnet_id = next_location

    return indeterminate(
        f"Route resolution exceeded {_MAX_HOPS} hops without terminating.",
        [f"stopped after {_MAX_HOPS} hops"],
    )


__all__ = ["PathHop", "PathVerdict", "RouteResolutionResult", "resolve_path"]
