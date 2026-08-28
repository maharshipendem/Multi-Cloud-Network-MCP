"""NAT-001: Cloud NAT egress issues -- a NAT config with static (manual)
IP allocation and zero IPs assigned (all egress blocked), and a low
``min_ports_per_vm`` combined with dynamic port allocation disabled,
which risks port exhaustion under load. This rule reasons over the NAT
config alone; it cannot see actual connection counts (no code path in
this server reaches live traffic metrics for this rule), so port
exhaustion is flagged as a *risk*, at reduced confidence, not a
confirmed outage.
"""

from __future__ import annotations

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.nat import RouterNatSummary

RULE_ID = "NAT-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Cloud NAT egress",
    description=(
        "Flags a Cloud NAT with manual IP allocation and zero assigned IPs (egress "
        "fully blocked), and a low per-VM port allocation that risks exhaustion under load."
    ),
    default_severity="medium",
)

_LOW_MIN_PORTS_THRESHOLD = 64


def evaluate_nat(*, router_name: str, nat: RouterNatSummary, freshness: str) -> Finding | None:
    evidence = [
        Evidence(
            source=f"cloud_nat:{nat.name}",
            detail=(
                f"nat_ip_allocate_option={nat.nat_ip_allocate_option}, nat_ips={nat.nat_ips}, "
                f"min_ports_per_vm={nat.min_ports_per_vm}, "
                f"enable_endpoint_independent_mapping={nat.enable_endpoint_independent_mapping}"
            ),
        )
    ]

    if nat.nat_ip_allocate_option == "MANUAL_ONLY" and not nat.nat_ips:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="critical",
            confidence="high",
            summary=(
                f"Cloud NAT {nat.name} on router {router_name} uses MANUAL_ONLY IP "
                "allocation with zero assigned NAT IPs -- all NAT egress traffic is blocked."
            ),
            affected_resources=[router_name, nat.name],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description="nat_ip_allocate_option=MANUAL_ONLY and nat_ips is empty",
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            remediation=(
                "Assign at least one static IP to this NAT config, or switch to "
                "AUTO_ONLY allocation."
            ),
        )

    if nat.min_ports_per_vm is not None and nat.min_ports_per_vm < _LOW_MIN_PORTS_THRESHOLD:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="low",
            confidence="medium",
            summary=(
                f"Cloud NAT {nat.name} on router {router_name} has min_ports_per_vm="
                f"{nat.min_ports_per_vm}, below the {_LOW_MIN_PORTS_THRESHOLD}-port threshold "
                "this rule flags as a port-exhaustion risk under concurrent-connection load."
            ),
            affected_resources=[router_name, nat.name],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description=(
                        f"min_ports_per_vm={nat.min_ports_per_vm} < {_LOW_MIN_PORTS_THRESHOLD}"
                    ),
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            limitations=[
                "This is a configuration-only risk assessment -- actual port exhaustion "
                "depends on live connection counts this server has no visibility into."
            ],
            remediation=(
                "Raise min_ports_per_vm, or enable dynamic port allocation, if VMs "
                "behind this NAT make many concurrent outbound connections."
            ),
        )

    return None


__all__ = ["RULE_ID", "evaluate_nat"]
