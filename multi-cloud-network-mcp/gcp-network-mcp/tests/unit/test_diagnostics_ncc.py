from __future__ import annotations

from gcp_network_mcp.diagnostics.ncc import evaluate_hub_status, evaluate_spoke
from gcp_network_mcp.models.connectivity_center import (
    NccHubStatus,
    NccHubStatusEntry,
    NccPscPropagationStatus,
    NccSpoke,
    NccSpokeReason,
)

FRESHNESS = "2026-08-27T00:00:00Z"
HUB = "projects/p/locations/global/hubs/hub-1"


def _spoke(
    *, state: str | None = "ACTIVE", reasons: list[NccSpokeReason] | None = None
) -> NccSpoke:
    return NccSpoke(
        name="spoke-1",
        project_id="p",
        hub=HUB,
        state=state,
        spoke_type="VPC_NETWORK",
        reasons=reasons or [],
        observed_at=FRESHNESS,
    )


# --------------------------------------------------------------------------
# evaluate_spoke (NCC-001)
# --------------------------------------------------------------------------


def test_active_spoke_returns_none() -> None:
    assert evaluate_spoke(spoke=_spoke(state="ACTIVE"), freshness=FRESHNESS) is None


def test_spoke_with_no_state_returns_none() -> None:
    assert evaluate_spoke(spoke=_spoke(state=None), freshness=FRESHNESS) is None


def test_inactive_spoke_produces_finding_referencing_reason() -> None:
    reasons = [NccSpokeReason(code="PENDING_REVIEW", message="awaiting hub owner acceptance")]
    finding = evaluate_spoke(spoke=_spoke(state="INACTIVE", reasons=reasons), freshness=FRESHNESS)
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "PENDING_REVIEW" in finding.summary
    assert "awaiting hub owner acceptance" in finding.summary
    assert finding.evidence
    assert finding.remediation is not None


def test_inactive_spoke_with_no_reasons_reported() -> None:
    finding = evaluate_spoke(spoke=_spoke(state="INACTIVE", reasons=[]), freshness=FRESHNESS)
    assert finding is not None
    assert "no reason reported" in finding.summary


# --------------------------------------------------------------------------
# evaluate_hub_status (NCC-001)
# --------------------------------------------------------------------------


def _hub_status(entries: list[NccHubStatusEntry]) -> NccHubStatus:
    return NccHubStatus(hub=HUB, entries=entries, observed_at=FRESHNESS)


def test_healthy_psc_codes_produce_no_findings() -> None:
    entries = [
        NccHubStatusEntry(count=1, psc_propagation_status=NccPscPropagationStatus(code="READY")),
        NccHubStatusEntry(
            count=2, psc_propagation_status=NccPscPropagationStatus(code="PROPAGATING")
        ),
    ]
    findings = evaluate_hub_status(hub_status=_hub_status(entries), freshness=FRESHNESS)
    assert findings == []


def test_missing_code_is_skipped() -> None:
    entries = [
        NccHubStatusEntry(count=1, psc_propagation_status=NccPscPropagationStatus(code=None))
    ]
    findings = evaluate_hub_status(hub_status=_hub_status(entries), freshness=FRESHNESS)
    assert findings == []


def test_error_code_produces_finding() -> None:
    entries = [
        NccHubStatusEntry(
            count=3,
            psc_propagation_status=NccPscPropagationStatus(
                code="ERROR_PSC_CONNECTION_UNSUPPORTED",
                message="quota exceeded",
                source_spoke="spoke-a",
                target_spoke="spoke-b",
            ),
        )
    ]
    findings = evaluate_hub_status(hub_status=_hub_status(entries), freshness=FRESHNESS)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "quota exceeded" in finding.summary
    assert finding.evidence
    assert "spoke-a" in finding.affected_resources
    assert "spoke-b" in finding.affected_resources


def test_multiple_unhealthy_entries_each_produce_a_finding() -> None:
    entries = [
        NccHubStatusEntry(count=1, psc_propagation_status=NccPscPropagationStatus(code="ERROR_A")),
        NccHubStatusEntry(count=1, psc_propagation_status=NccPscPropagationStatus(code="ERROR_B")),
    ]
    findings = evaluate_hub_status(hub_status=_hub_status(entries), freshness=FRESHNESS)
    assert len(findings) == 2
