"""NCC-001: Network Connectivity Center propagation issues -- an
inactive spoke (with its GCP-reported state reasons), and PSC
propagation errors from a hub's ``query_hub_status`` computed view."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.models import Evidence, Finding, ReasoningStep, register_rule
from gcp_network_mcp.models.connectivity_center import NccHubStatus, NccSpoke

RULE_ID = "NCC-001"
register_rule(
    rule_id=RULE_ID,
    version="1.0.0",
    title="Network Connectivity Center propagation",
    description=(
        "Flags an inactive NCC spoke (with GCP's own reported reasons) and PSC "
        "propagation errors reported by a hub's own status computation."
    ),
    default_severity="medium",
)

_ACTIVE_STATES = {"ACTIVE"}
_HEALTHY_PSC_CODES = {"READY", "PROPAGATING"}


def evaluate_spoke(*, spoke: NccSpoke, freshness: str) -> Finding | None:
    """Returns ``None`` when the spoke is active -- no finding needed for
    the healthy case, matching this engine's "findings are for issues"
    convention (used by ``risks.py``; ``health.py`` and ``explain.py``
    still surface the underlying facts regardless)."""
    if not spoke.state or spoke.state in _ACTIVE_STATES:
        return None

    reasons = (
        "; ".join(f"{r.code}: {r.message}" for r in spoke.reasons if r.code) or "no reason reported"
    )
    return Finding(
        rule_id=RULE_ID,
        rule_version="1.0.0",
        severity="high",
        confidence="high",
        summary=(
            f"NCC spoke {spoke.name} (hub={spoke.hub}) is state={spoke.state}, not "
            f"ACTIVE. Reasons: {reasons}"
        ),
        affected_resources=[spoke.name, spoke.hub],
        evidence=[
            Evidence(
                source=f"ncc_spoke:{spoke.name}", detail=f"state={spoke.state}, reasons={reasons}"
            )
        ],
        reasoning=[
            ReasoningStep(
                step=1, description=f"spoke.state={spoke.state} is not ACTIVE", evidence_indices=[0]
            )
        ],
        freshness=freshness,
        remediation=(
            "Review the spoke's reported reasons -- a common cause is the hub owner "
            "not yet accepting the spoke (see accept_hub_spoke on the hub owner's side)."
        ),
    )


def evaluate_hub_status(*, hub_status: NccHubStatus, freshness: str) -> list[Finding]:
    findings: list[Finding] = []
    for entry in hub_status.entries:
        status = entry.psc_propagation_status
        if not status.code or status.code in _HEALTHY_PSC_CODES:
            continue
        findings.append(
            Finding(
                rule_id=RULE_ID,
                rule_version="1.0.0",
                severity="high",
                confidence="high",
                summary=(
                    f"Hub {hub_status.hub} reports {entry.count} PSC connection(s) with "
                    f"propagation status {status.code}"
                    + (f": {status.message}" if status.message else "")
                ),
                affected_resources=[
                    hub_status.hub,
                    status.source_spoke or "",
                    status.target_spoke or "",
                ],
                evidence=[
                    Evidence(
                        source=f"ncc_hub_status:{hub_status.hub}",
                        detail=(
                            f"code={status.code}, source_spoke={status.source_spoke}, "
                            f"target_spoke={status.target_spoke}"
                        ),
                    )
                ],
                reasoning=[
                    ReasoningStep(
                        step=1,
                        description=(
                            f"psc_propagation_status.code={status.code} is not READY/PROPAGATING"
                        ),
                        evidence_indices=[0],
                    )
                ],
                freshness=freshness,
                remediation=(
                    "Consult the specific error code against GCP's PSC propagation "
                    "status reference for the exact quota or configuration issue."
                ),
            )
        )
    return findings


__all__ = ["RULE_ID", "evaluate_hub_status", "evaluate_spoke"]
