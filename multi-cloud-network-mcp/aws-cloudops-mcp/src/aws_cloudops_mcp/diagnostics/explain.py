"""Orchestrates route resolution + security group/NACL evaluation into
one combined path explanation -- the logic behind ``aws_explain_network_path``.

Each sub-evaluation only runs when it has the concrete information it
needs (a resolvable source ENI for security groups; a source AND
destination IP plus a port for the stateless four-leg NACL walk). When a
sub-evaluation is skipped, that is recorded as an explicit limitation on
the combined result rather than silently treating "not evaluated" as
"passed."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aws_cloudops_mcp.diagnostics.models import Finding
from aws_cloudops_mcp.diagnostics.routing import PathHop, PathVerdict, resolve_path
from aws_cloudops_mcp.diagnostics.security import evaluate_network_acls, evaluate_security_groups
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot

OverallVerdict = Literal["allowed", "blocked", "partially_evaluated", "indeterminate"]


class PathExplanation(BaseModel):
    """The combined result of ``aws_explain_network_path``."""

    overall_verdict: OverallVerdict
    route_verdict: PathVerdict
    hops: list[PathHop] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


def _resolve_eni_by_ip(snapshot: NetworkSnapshot, ip: str | None) -> str | None:
    if ip is None:
        return None
    eni = next(
        (e for e in snapshot.network_interfaces if e.private_ip_address == ip or e.public_ip == ip),
        None,
    )
    return eni.network_interface_id if eni else None


def explain_network_path(
    snapshot: NetworkSnapshot,
    *,
    destination: str,
    source_subnet_id: str | None = None,
    source_eni_id: str | None = None,
    source_ip: str | None = None,
    vpc_id: str | None = None,
    destination_eni_id: str | None = None,
    destination_ip: str | None = None,
    protocol: str = "tcp",
    port: int | None = None,
) -> PathExplanation:
    route_result = resolve_path(
        snapshot,
        destination=destination,
        source_subnet_id=source_subnet_id,
        source_eni_id=source_eni_id,
        source_ip=source_ip,
        vpc_id=vpc_id,
    )
    findings = [route_result.finding]

    if route_result.verdict != "routable":
        return PathExplanation(
            overall_verdict="blocked"
            if route_result.verdict == "blocked_at_routing"
            else "indeterminate",
            route_verdict=route_result.verdict,
            hops=route_result.hops,
            findings=findings,
        )

    resolved_source_eni_id = source_eni_id or _resolve_eni_by_ip(snapshot, source_ip)
    resolved_dest_eni_id = destination_eni_id or _resolve_eni_by_ip(snapshot, destination_ip)

    sg_finding: Finding | None = None
    if resolved_source_eni_id:
        sg_finding = evaluate_security_groups(
            snapshot,
            source_eni_id=resolved_source_eni_id,
            destination_eni_id=resolved_dest_eni_id,
            destination_ip=destination_ip
            or (destination if resolved_dest_eni_id is None else None),
            protocol=protocol,
            port=port,
        )
        findings.append(sg_finding)

    nacl_finding: Finding | None = None
    last_hop = route_result.hops[-1] if route_result.hops else None
    can_evaluate_nacl = (
        last_hop is not None
        and last_hop.target_type == "local"
        and source_ip is not None
        and destination_ip is not None
        and port is not None
    )
    if (
        can_evaluate_nacl
        and last_hop is not None
        and source_ip
        and destination_ip
        and port is not None
    ):
        # A "local" hop only proves the destination is somewhere in the VPC; resolve
        # which specific subnet it actually lives in before evaluating NACLs against it.
        resolved_dest_subnet = snapshot.subnet_containing_ip(last_hop.vpc_id, destination_ip)
        if resolved_dest_subnet:
            nacl_finding = evaluate_network_acls(
                snapshot,
                source_subnet_id=last_hop.location_id,
                source_ip=source_ip,
                destination_subnet_id=resolved_dest_subnet,
                destination_ip=destination_ip,
                protocol=protocol,
                port=port,
            )
            findings.append(nacl_finding)
        else:
            can_evaluate_nacl = False

    limitations: list[str] = []
    if resolved_source_eni_id is None:
        limitations.append(
            "security group evaluation skipped: no source ENI could be resolved "
            "(pass source_eni_id, or a source_ip matching a known ENI)"
        )
    if not can_evaluate_nacl:
        limitations.append(
            "network ACL evaluation skipped: requires a same-VPC path with concrete "
            "source_ip, destination_ip, and port"
        )

    decisions = []
    for f in (sg_finding, nacl_finding):
        if f is None:
            continue
        if "deny" in f.summary.lower():
            decisions.append("deny")
        elif f.confidence == "indeterminate":
            decisions.append("indeterminate")
        else:
            decisions.append("allow")

    if "deny" in decisions:
        overall: OverallVerdict = "blocked"
    elif "indeterminate" in decisions or limitations:
        overall = "partially_evaluated"
    else:
        overall = "allowed"

    if limitations:
        route_result.finding.limitations.extend(limitations)

    return PathExplanation(
        overall_verdict=overall,
        route_verdict=route_result.verdict,
        hops=route_result.hops,
        findings=findings,
    )


__all__ = ["OverallVerdict", "PathExplanation", "explain_network_path"]
