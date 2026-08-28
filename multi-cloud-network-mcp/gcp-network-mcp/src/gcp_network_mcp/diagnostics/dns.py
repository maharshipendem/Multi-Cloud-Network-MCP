"""DNS-001: DNS forwarding chain issues.

``google-cloud-dns`` (the only Google-published Python client library
for Cloud DNS -- see ``models/dns.py``) exposes no visibility/forwarding-
config/peering-config/Policy/Response-Policy data at all, so this rule
cannot evaluate an actual forwarding chain (private zone -> forwarding
target -> upstream resolver). It runs at ``confidence="indeterminate"``
for every zone, explicitly naming the missing evidence, rather than
either fabricating a forwarding-chain analysis or silently omitting the
rule -- per this milestone's explicit guardrail against claiming
certainty with incomplete data. The one fact this rule *can* check
(zone has no assigned name servers) is reported at full confidence.
"""

from __future__ import annotations

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.dns import DnsZone

RULE_ID = "DNS-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="DNS forwarding chain",
    description=(
        "Reports on a managed zone's forwarding-chain health. Confidence is always "
        "indeterminate for forwarding/peering/policy evaluation -- no available Google "
        "client library exposes that configuration -- except the one fact this rule can "
        "check directly (whether the zone has assigned name servers)."
    ),
    default_severity="info",
)


def evaluate_zone(*, zone: DnsZone, freshness: str) -> Finding:
    evidence = [
        Evidence(
            source=f"dns_zone:{zone.name}",
            detail=f"dns_name={zone.dns_name}, name_servers={zone.name_servers}",
        )
    ]

    if not zone.name_servers:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="medium",
            confidence="high",
            summary=f"Managed zone {zone.name} ({zone.dns_name}) has no name servers assigned.",
            affected_resources=[zone.name],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1, description="zone.name_servers is empty", evidence_indices=[0]
                )
            ],
            freshness=freshness,
            limitations=[
                "Forwarding/peering/Policy/Response-Policy configuration for this zone could "
                "not be evaluated -- no available Google-published Python client library "
                "exposes it (see docs/limitations.md#cloud-dns)."
            ],
        )

    return Finding(
        rule_id=RULE_ID,
        rule_version="1.0.0",
        severity="info",
        confidence="indeterminate",
        summary=(
            f"Managed zone {zone.name} ({zone.dns_name}) has {len(zone.name_servers)} name "
            "server(s) assigned; its forwarding chain (private-zone forwarding target, DNS "
            "peering, Policy, Response Policy) could not be evaluated."
        ),
        affected_resources=[zone.name],
        evidence=evidence,
        freshness=freshness,
        limitations=[
            "Forwarding/peering/Policy/Response-Policy configuration for this zone could not "
            "be evaluated -- no available Google-published Python client library exposes it "
            "(see docs/limitations.md#cloud-dns)."
        ],
    )


__all__ = ["RULE_ID", "evaluate_zone"]
