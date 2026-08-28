"""PEER-001: VPC Network Peering limitations -- non-ACTIVE peering
state, and route-import/export gaps that make a peer's subnets/custom
routes unreachable despite the peering itself being active. GCP peering
is inherently non-transitive (a peer of a peer is not reachable through
this network) -- this rule flags that expectation mismatch when it's
visible from the peering config alone, but cannot see the peer network's
own routes/firewall rules (out of this project's scope), so anything
requiring that visibility is reported at reduced confidence.
"""

from __future__ import annotations

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.peering import NetworkPeering

RULE_ID = "PEER-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="VPC Network Peering limitations",
    description=(
        "Flags a non-ACTIVE peering state, and route-import/export settings that leave "
        "a peer's subnets or custom routes unreachable despite the peering connection "
        "itself being active."
    ),
    default_severity="medium",
)


def evaluate_peering(*, peering: NetworkPeering, freshness: str) -> Finding:
    evidence = [
        Evidence(
            source=f"peering:{peering.name}",
            detail=(
                f"state={peering.state}, exchange_subnet_routes={peering.exchange_subnet_routes}, "
                f"export_custom_routes={peering.export_custom_routes}, "
                f"import_custom_routes={peering.import_custom_routes}"
            ),
        )
    ]

    if peering.state and peering.state != "ACTIVE":
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="high",
            confidence="high",
            summary=(
                f"Peering {peering.name} to {peering.network} is state={peering.state}, "
                "not ACTIVE -- no traffic flows across it."
            ),
            affected_resources=[peering.name, peering.network],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description=f"peering.state={peering.state} != ACTIVE",
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            remediation=(
                "A peering typically needs a matching peering connection configured on "
                f"the other side ({peering.network}) before it reaches ACTIVE."
            ),
        )

    if peering.exchange_subnet_routes is False:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="medium",
            confidence="high",
            summary=(
                f"Peering {peering.name} to {peering.network} has exchange_subnet_routes=false -- "
                "the peer's subnet ranges are not reachable through this peering."
            ),
            affected_resources=[peering.name, peering.network],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description=(
                        "exchange_subnet_routes=false disables subnet-route exchange entirely"
                    ),
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            remediation=(
                "Enable subnet route exchange on the peering if reachability to the "
                "peer's subnets is intended."
            ),
        )

    if not peering.import_custom_routes and not peering.export_custom_routes:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="low",
            confidence="medium",
            summary=(
                f"Peering {peering.name} to {peering.network} does not import or export custom "
                "routes -- only directly connected subnet ranges are reachable, not any custom "
                "static/dynamic routes on either side."
            ),
            affected_resources=[peering.name, peering.network],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description="import_custom_routes=false and export_custom_routes=false",
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            limitations=[
                "Whether this matters depends on the peer network's own route configuration, "
                "which is outside this project's visibility."
            ],
            remediation=(
                "Enable custom route import/export on both sides of the peering if "
                "reachability beyond subnet ranges is intended."
            ),
        )

    return Finding(
        rule_id=RULE_ID,
        rule_version="1.0.0",
        severity="info",
        confidence="high",
        summary=(
            f"Peering {peering.name} to {peering.network} is ACTIVE with subnet and "
            "custom route exchange enabled."
        ),
        affected_resources=[peering.name, peering.network],
        evidence=evidence,
        freshness=freshness,
        limitations=[
            "GCP peering is non-transitive: resources reachable through the peer's own "
            "peerings are not reachable through this one, regardless of these settings."
        ],
    )


__all__ = ["RULE_ID", "evaluate_peering"]
