"""Internet exposure analysis for ENIs and load balancers.

Every finding here distinguishes **potential exposure** (a security group
or NACL rule that *would* permit internet traffic) from **proven
reachability** (that permissive rule combined with an actual public IP and
a route to an internet gateway) -- the milestone's own guardrail ("do not
claim traffic reachability from topology alone" / "distinguish potential
exposure from proven reachability") is the reason this module never
collapses those two into one verdict.
"""

from __future__ import annotations

import ipaddress

from aws_cloudops_mcp.diagnostics.models import (
    Confidence,
    Evidence,
    Finding,
    ReasoningStep,
    RuleMetadata,
    Severity,
    register_rule,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot

RULE_ENI_EXPOSURE = register_rule(
    rule_id="EXPOSE-001",
    version="1.0.0",
    title="ENI internet exposure",
    description=(
        "Combines public IP presence, a route to an internet gateway, "
        "security group ingress, and NACL inbound rules to distinguish a "
        "permissive-but-unreachable configuration from one that is "
        "actually reachable from the public internet today."
    ),
    default_severity="medium",
)

RULE_LOAD_BALANCER_EXPOSURE = register_rule(
    rule_id="EXPOSE-002",
    version="1.0.0",
    title="Load balancer internet exposure",
    description=(
        "Flags an internet-facing load balancer listener whose security "
        "groups permit ingress from 0.0.0.0/0 or ::/0."
    ),
    default_severity="medium",
)

_ANY_IPV4 = ipaddress.ip_network("0.0.0.0/0")
_ANY_IPV6 = ipaddress.ip_network("::/0")
_SENSITIVE_PORTS = {
    22: "SSH",
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
}


def _is_open_to_internet(cidr: str) -> bool:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False
    return net in (_ANY_IPV4, _ANY_IPV6)


def _open_sg_ingress_ports(
    snapshot: NetworkSnapshot, group_ids: list[str]
) -> list[tuple[str, int | None, int | None]]:
    """(protocol, from_port, to_port) for every ingress rule open to
    0.0.0.0/0 or ::/0 across the given groups."""
    opened: list[tuple[str, int | None, int | None]] = []
    for group_id in group_ids:
        sg = snapshot.security_group_by_id(group_id)
        if sg is None:
            continue
        for rule in sg.rules:
            if rule.is_egress:
                continue
            if rule.peer.type in ("ipv4", "ipv6") and _is_open_to_internet(rule.peer.value):
                opened.append((rule.ip_protocol, rule.from_port, rule.to_port))
    return opened


def _has_public_route(snapshot: NetworkSnapshot, vpc_id: str, subnet_id: str) -> bool:
    route_table = snapshot.route_table_for_subnet(subnet_id, vpc_id)
    if route_table is None:
        return False
    for route in route_table.routes:
        if route.target_type != "gateway" or route.state != "active":
            continue
        cidr = route.destination_cidr_block or route.destination_ipv6_cidr_block
        if cidr and _is_open_to_internet(cidr):
            return True
    return False


def _nacl_allows_inbound_from_internet(snapshot: NetworkSnapshot, subnet_id: str) -> bool | None:
    nacl = snapshot.network_acl_for_subnet(subnet_id)
    if nacl is None:
        return None
    for entry in sorted((e for e in nacl.entries if not e.egress), key=lambda e: e.rule_number):
        cidr = entry.cidr_block or entry.ipv6_cidr_block
        if cidr and _is_open_to_internet(cidr):
            return entry.rule_action == "allow"
    return False


def _severity_for_ports(ports: list[tuple[str, int | None, int | None]]) -> Severity:
    for protocol, from_port, to_port in ports:
        if protocol == "-1":
            return "critical"
        if from_port is None or to_port is None:
            continue
        for sensitive_port in _SENSITIVE_PORTS:
            if from_port <= sensitive_port <= to_port:
                return "critical"
    return "high"


def evaluate_eni_exposure(snapshot: NetworkSnapshot, network_interface_id: str) -> Finding:
    """Evaluate one ENI's internet exposure."""
    eni = snapshot.eni_by_id(network_interface_id)
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []
    limitations: list[str] = []

    if eni is None or not eni.subnet_id or not eni.vpc_id:
        return _finding(
            RULE_ENI_EXPOSURE,
            "info",
            "indeterminate",
            f"ENI {network_interface_id} was not found (or lacks subnet/VPC data) in this "
            "snapshot.",
            [network_interface_id],
            evidence,
            reasoning,
            [f"ENI {network_interface_id} not resolvable from this snapshot"],
            snapshot.collected_at,
        )

    has_public_ip = eni.public_ip is not None
    evidence.append(
        Evidence(
            source=f"network_interface:{eni.network_interface_id}",
            detail=f"PublicIp={eni.public_ip}",
        )
    )

    has_public_route = _has_public_route(snapshot, eni.vpc_id, eni.subnet_id)
    evidence.append(
        Evidence(
            source=f"subnet:{eni.subnet_id}",
            detail=f"has active route to an internet gateway: {has_public_route}",
        )
    )

    open_ports = _open_sg_ingress_ports(snapshot, eni.security_group_ids)
    for protocol, from_port, to_port in open_ports:
        evidence.append(
            Evidence(
                source=f"network_interface:{eni.network_interface_id}",
                detail=(
                    "security group ingress open to 0.0.0.0/0 or ::/0: "
                    f"{protocol}:{from_port}-{to_port}"
                ),
            )
        )

    nacl_allows = _nacl_allows_inbound_from_internet(snapshot, eni.subnet_id)
    if nacl_allows is None:
        limitations.append(f"no network ACL found for subnet {eni.subnet_id}")
    else:
        evidence.append(
            Evidence(
                source=f"subnet:{eni.subnet_id}",
                detail=f"NACL permits inbound from 0.0.0.0/0 or ::/0: {nacl_allows}",
            )
        )

    reasoning.append(
        ReasoningStep(
            step=1,
            description=(
                f"has_public_ip={has_public_ip}, has_public_route={has_public_route}, "
                f"open_sg_ingress_rules={len(open_ports)}, nacl_allows_inbound={nacl_allows}."
            ),
            evidence_indices=list(range(len(evidence))),
        )
    )

    if not open_ports:
        return _finding(
            RULE_ENI_EXPOSURE,
            "info",
            "high",
            f"{network_interface_id} has no security group ingress rule open to the internet.",
            [network_interface_id],
            evidence,
            reasoning,
            limitations,
            snapshot.collected_at,
        )

    reachable = has_public_ip and has_public_route and (nacl_allows is True)
    if reachable:
        severity = _severity_for_ports(open_ports)
        confidence: Confidence = "high"
        summary = (
            f"{network_interface_id} is reachable from the public internet: it has a public IP, "
            "a route to an internet gateway, and a security group/NACL that permit inbound "
            f"traffic on {', '.join(f'{p}:{f}-{t}' for p, f, t in open_ports)}."
        )
        remediation = (
            "Restrict the security group ingress rule to a specific known CIDR, or remove the "
            "public IP/route if this resource is not meant to be internet-facing."
        )
    else:
        severity = "low"
        confidence = "high" if nacl_allows is not None else "medium"
        summary = (
            f"{network_interface_id}'s security group permits ingress from the internet on "
            f"{', '.join(f'{p}:{f}-{t}' for p, f, t in open_ports)}, but it is not currently "
            f"reachable (public_ip={has_public_ip}, public_route={has_public_route}, "
            f"nacl_allows_inbound={nacl_allows}). This is a latent exposure: any future change "
            "that adds a public IP/route would make it reachable immediately."
        )
        remediation = (
            "Tighten the security group ingress rule now, even though it isn't reachable today -- "
            "it becomes a live exposure the moment a public IP or public route is added."
        )

    return _finding(
        RULE_ENI_EXPOSURE,
        severity,
        confidence,
        summary,
        [network_interface_id],
        evidence,
        reasoning,
        limitations,
        snapshot.collected_at,
        remediation=remediation,
    )


def evaluate_load_balancer_exposure(snapshot: NetworkSnapshot, load_balancer_arn: str) -> Finding:
    lb = next(
        (lb for lb in snapshot.load_balancers if lb.load_balancer_arn == load_balancer_arn), None
    )
    evidence: list[Evidence] = []
    reasoning: list[ReasoningStep] = []

    if lb is None:
        return _finding(
            RULE_LOAD_BALANCER_EXPOSURE,
            "info",
            "indeterminate",
            f"Load balancer {load_balancer_arn} was not found in this snapshot.",
            [load_balancer_arn],
            evidence,
            reasoning,
            [f"load balancer {load_balancer_arn} not resolvable from this snapshot"],
            snapshot.collected_at,
        )

    is_internet_facing = lb.scheme == "internet-facing"
    evidence.append(
        Evidence(source=f"load_balancer:{lb.load_balancer_arn}", detail=f"scheme={lb.scheme}")
    )
    open_ports = _open_sg_ingress_ports(snapshot, lb.security_group_ids)
    for protocol, from_port, to_port in open_ports:
        evidence.append(
            Evidence(
                source=f"load_balancer:{lb.load_balancer_arn}",
                detail=(
                    "security group ingress open to 0.0.0.0/0 or ::/0: "
                    f"{protocol}:{from_port}-{to_port}"
                ),
            )
        )
    reasoning.append(
        ReasoningStep(
            step=1,
            description=f"scheme={lb.scheme}, open_sg_ingress_rules={len(open_ports)}.",
            evidence_indices=list(range(len(evidence))),
        )
    )

    if is_internet_facing and open_ports:
        listener_ports = [f"{listener.protocol}:{listener.port}" for listener in lb.listeners]
        summary = (
            f"{lb.load_balancer_name} is internet-facing with security groups open to "
            f"0.0.0.0/0 or ::/0 on {', '.join(f'{p}:{f}-{t}' for p, f, t in open_ports)}. "
            f"Configured listeners: {', '.join(listener_ports) or 'none'}."
        )
        return _finding(
            RULE_LOAD_BALANCER_EXPOSURE,
            "medium",
            "high",
            summary,
            [load_balancer_arn],
            evidence,
            reasoning,
            [],
            snapshot.collected_at,
            remediation=(
                "This is expected for a public load balancer; confirm the listeners and target "
                "groups behind it are intended to be publicly reachable."
            ),
        )

    return _finding(
        RULE_LOAD_BALANCER_EXPOSURE,
        "info",
        "high",
        f"{lb.load_balancer_name} is not both internet-facing and open to 0.0.0.0/0 or ::/0.",
        [load_balancer_arn],
        evidence,
        reasoning,
        [],
        snapshot.collected_at,
    )


def _finding(
    rule: RuleMetadata,
    severity: Severity,
    confidence: Confidence,
    summary: str,
    affected: list[str],
    evidence: list[Evidence],
    reasoning: list[ReasoningStep],
    limitations: list[str],
    freshness: str,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        severity=severity,
        confidence=confidence,
        summary=summary,
        affected_resources=affected,
        evidence=evidence,
        reasoning=reasoning,
        assumptions=[],
        limitations=limitations,
        freshness=freshness,
        remediation=remediation,
    )


__all__ = ["evaluate_eni_exposure", "evaluate_load_balancer_exposure"]
