"""EXPOSE-001: public internet exposure via a forwarding rule with an
external (non-internal) load balancing scheme, cross-referenced against
firewall rules to determine whether the exposed IP is actually reachable
from the internet or only appears exposed."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.firewall import evaluate_firewall
from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.firewall import FirewallRule
from gcp_network_mcp.models.load_balancing import ForwardingRuleSummary

RULE_ID = "EXPOSE-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Public forwarding rule exposure",
    description=(
        "Flags an externally-scoped forwarding rule and cross-references firewall rules "
        "to determine whether the exposed IP is actually reachable from the internet."
    ),
    default_severity="medium",
)

_EXTERNAL_SCHEMES = {"EXTERNAL", "EXTERNAL_MANAGED"}


def evaluate_exposure(
    *, rule: ForwardingRuleSummary, firewall_rules: list[FirewallRule], freshness: str
) -> Finding | None:
    if rule.load_balancing_scheme not in _EXTERNAL_SCHEMES:
        return None
    if not rule.network_self_link:
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="medium",
            confidence="indeterminate",
            summary=(
                f"Forwarding rule {rule.name} has an external load balancing scheme "
                f"({rule.load_balancing_scheme}) but no associated network could be resolved "
                "to check firewall reachability."
            ),
            affected_resources=[rule.name],
            freshness=freshness,
            limitations=["No network_self_link was available on this forwarding rule."],
        )

    port = None
    if rule.ports:
        try:
            port = int(rule.ports[0])
        except ValueError:
            port = None
    elif rule.port_range:
        try:
            port = int(rule.port_range.split("-")[0])
        except ValueError:
            port = None

    verdict, firewall_finding = evaluate_firewall(
        network_self_link=rule.network_self_link,
        firewall_rules=firewall_rules,
        direction="INGRESS",
        protocol=(rule.ip_protocol or "tcp").lower(),
        port=port,
        peer_ip="0.0.0.0",  # the internet at large -- the worst case for a public IP
        freshness=freshness,
    )

    evidence = [
        Evidence(
            source=f"forwarding_rule:{rule.name}",
            detail=(
                f"load_balancing_scheme={rule.load_balancing_scheme}, ip_address={rule.ip_address}"
            ),
        )
    ]

    if verdict == "ALLOW":
        return Finding(
            rule_id=RULE_ID,
            rule_version="1.0.0",
            severity="high",
            confidence=firewall_finding.confidence,
            summary=(
                f"Forwarding rule {rule.name} ({rule.ip_address}) is externally scoped and "
                f"ingress traffic to it from any source is ALLOWed by the network's firewall rules."
            ),
            affected_resources=[rule.name, rule.network_self_link],
            evidence=evidence,
            reasoning=[
                ReasoningStep(
                    step=1,
                    description=(
                        "External forwarding rule with no restrictive firewall rule "
                        "blocking internet-wide ingress."
                    ),
                    evidence_indices=[0],
                )
            ],
            freshness=freshness,
            remediation=(
                "If public exposure is unintended, restrict the network's ingress "
                "firewall rules for this port/protocol."
            ),
        )

    return Finding(
        rule_id=RULE_ID,
        rule_version="1.0.0",
        severity="low",
        confidence=firewall_finding.confidence,
        summary=(
            f"Forwarding rule {rule.name} ({rule.ip_address}) is externally scoped, but ingress "
            f"from an arbitrary internet source is {verdict} by the network's firewall rules."
        ),
        affected_resources=[rule.name, rule.network_self_link],
        evidence=evidence,
        freshness=freshness,
        limitations=(
            ["Firewall evaluation for this exposure check returned an indeterminate verdict."]
            if verdict == "indeterminate"
            else []
        ),
    )


__all__ = ["RULE_ID", "evaluate_exposure"]
