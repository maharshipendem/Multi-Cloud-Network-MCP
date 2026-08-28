"""EXPOSE-001: internet exposure analysis across a whole resource group's
snapshot.

Evaluates each NIC's *configured* NSG rules (custom + default, as
collected in the snapshot -- not a per-NIC effective-NSG API call, which
would be an unbounded fan-out across every NIC in the resource group) for
a network interface that also has a public IP attached. This is
"potential exposure" (a permissive rule exists), not a proven-reachable
claim -- see docs/security.md#no-reachability-claims.
"""

from __future__ import annotations

from azure_network_mcp.diagnostics.models import Evidence, Finding, register_rule
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.common import normalize_resource_id

RULE_ID = "EXPOSE-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Network interface internet exposure",
    description=(
        "Flags a network interface that has a public IP attached and is protected "
        "by an NSG with a broad (0.0.0.0/0 or '*') inbound Allow rule."
    ),
    default_severity="medium",
)

_ANY_ADDRESS_TOKENS = {"*", "0.0.0.0/0", "internet", "any"}
_SENSITIVE_PORTS = {"22", "3389", "3306", "1433", "5432", "6379", "27017"}


def _is_wildcard(prefixes: list[str], prefix: str | None) -> bool:
    values = prefixes or ([prefix] if prefix else [])
    return any(v.strip().lower() in _ANY_ADDRESS_TOKENS for v in values)


def _touches_sensitive_port(ranges: list[str], single: str | None) -> bool:
    values = ranges or ([single] if single else [])
    for v in values:
        token = v.strip()
        if token == "*":
            return True
        if token in _SENSITIVE_PORTS:
            return True
        if "-" in token:
            try:
                low, high = (int(p) for p in token.split("-", 1))
                if any(low <= int(p) <= high for p in _SENSITIVE_PORTS):
                    return True
            except ValueError:
                continue
    return False


def find_exposed_network_interfaces(snapshot: HybridNetworkSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    nics_with_public_ip = {}
    for pip in snapshot.public_ip_addresses:
        if pip.associated_resource_id:
            # associated_resource_id is a NIC ip_configuration id, e.g.
            # .../networkInterfaces/nic-1/ipConfigurations/ipconfig1
            nic_id = pip.associated_resource_id.split("/ipConfigurations/")[0]
            nics_with_public_ip[normalize_resource_id(nic_id)] = pip

    nsgs_by_id = {normalize_resource_id(n.resource_id): n for n in snapshot.network_security_groups}
    subnets_by_id = {normalize_resource_id(s.resource_id): s for s in snapshot.subnets}

    for nic in snapshot.network_interfaces:
        matched_pip = nics_with_public_ip.get(normalize_resource_id(nic.resource_id))
        if matched_pip is None:
            continue

        nsg = None
        if nic.network_security_group_id:
            nsg = nsgs_by_id.get(normalize_resource_id(nic.network_security_group_id))
        if nsg is None:
            for ipc in nic.ip_configurations:
                if not ipc.subnet_id:
                    continue
                subnet = subnets_by_id.get(normalize_resource_id(ipc.subnet_id))
                if subnet and subnet.network_security_group_id:
                    nsg = nsgs_by_id.get(normalize_resource_id(subnet.network_security_group_id))
                if nsg:
                    break

        if nsg is None:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    rule_version="1.0.0",
                    severity="medium",
                    confidence="indeterminate",
                    summary=(
                        f"NIC {nic.name} has a public IP ({matched_pip.ip_address}) but no NSG "
                        "association was found in this snapshot -- exposure could not be "
                        "evaluated."
                    ),
                    affected_resources=[nic.resource_id, matched_pip.resource_id],
                    freshness=snapshot.observed_at,
                    limitations=[
                        "No NIC- or subnet-level NSG association was found for this "
                        "network interface in the collected snapshot."
                    ],
                )
            )
            continue

        matched_rules = [
            r
            for r in nsg.security_rules
            if r.direction == "Inbound"
            and r.access == "Allow"
            and _is_wildcard(r.source_address_prefixes, r.source_address_prefix)
        ]
        if not matched_rules:
            continue

        sensitive = any(
            _touches_sensitive_port(r.destination_port_ranges, r.destination_port_range)
            for r in matched_rules
        )
        rule_names = ", ".join(r.name or "" for r in matched_rules)
        findings.append(
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="high" if sensitive else "medium",
                confidence="medium",
                summary=(
                    f"NIC {nic.name} has public IP {matched_pip.ip_address} and NSG {nsg.name} "
                    f"allows inbound traffic from any source via rule(s): {rule_names}."
                ),
                affected_resources=[nic.resource_id, matched_pip.resource_id, nsg.resource_id],
                evidence=[
                    Evidence(
                        source=f"nsg_rule:{r.name}@{nsg.name}",
                        detail=(
                            f"priority={r.priority}, protocol={r.protocol}, "
                            "destination_ports="
                            f"{r.destination_port_ranges or r.destination_port_range}"
                        ),
                    )
                    for r in matched_rules
                ],
                freshness=snapshot.observed_at,
                assumptions=[
                    "This reflects the NSG's configured rules, not Azure's computed "
                    "effective-rule merge for this specific NIC -- a rule at the subnet "
                    "level could still be overridden by a NIC-level association not "
                    "captured here."
                ],
                remediation=(
                    "If public exposure on this port range is unintended, narrow the "
                    "NSG rule's source address prefix or remove the public IP association."
                ),
            )
        )

    return findings


__all__ = ["RULE_ID", "find_exposed_network_interfaces"]
