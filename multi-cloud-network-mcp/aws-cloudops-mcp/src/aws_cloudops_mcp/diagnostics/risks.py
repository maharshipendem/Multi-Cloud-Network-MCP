"""Aggregates every diagnostic rule that scans a whole snapshot (rather
than answering one source/destination question) into one findings list --
the logic behind ``aws_find_network_risks``.

Every ENI and load balancer in the snapshot is checked, including ones
with nothing wrong (an ``info``-severity finding, not an omission) -- see
``diagnostics.models.Finding`` docstring on why "checked, found nothing"
must never look identical to "not checked." ``min_severity`` lets a
caller filter that noise down for a typical call without the underlying
function ever silently doing so itself.
"""

from __future__ import annotations

from aws_cloudops_mcp.diagnostics.consistency import run_all_consistency_checks
from aws_cloudops_mcp.diagnostics.exposure import (
    evaluate_eni_exposure,
    evaluate_load_balancer_exposure,
)
from aws_cloudops_mcp.diagnostics.models import Finding, Severity
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot

_SEVERITY_ORDER: dict[Severity, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def find_network_risks(
    snapshot: NetworkSnapshot, *, min_severity: Severity | None = None
) -> list[Finding]:
    """Run every whole-snapshot diagnostic rule and return the combined,
    deterministically-ordered findings list.

    ``min_severity`` (e.g. ``"low"``) drops findings less severe than the
    threshold from the returned list; omit it to get everything,
    including informational "checked, nothing found" findings.
    """
    findings: list[Finding] = [
        *run_all_consistency_checks(snapshot),
        *(
            evaluate_eni_exposure(snapshot, eni.network_interface_id)
            for eni in snapshot.network_interfaces
        ),
        *(
            evaluate_load_balancer_exposure(snapshot, lb.load_balancer_arn)
            for lb in snapshot.load_balancers
        ),
    ]

    if min_severity is not None:
        threshold = _SEVERITY_ORDER[min_severity]
        findings = [f for f in findings if _SEVERITY_ORDER[f.severity] <= threshold]

    findings.sort(
        key=lambda f: (
            _SEVERITY_ORDER[f.severity],
            f.rule_id,
            f.affected_resources[0] if f.affected_resources else "",
        )
    )
    return findings


__all__ = ["find_network_risks"]
