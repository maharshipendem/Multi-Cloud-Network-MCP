"""Path/finding evidence references: a ``TopologyEdge`` must always
carry at least one specific, already-observed fact -- never an
edge asserted with zero evidence -- and a ``Finding``'s evidence/
reasoning split (fact vs. inference) round-trips with indices intact."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from multicloud_network_mcp.contracts.models import (
    Finding,
    ReasoningStep,
    SourceEvidence,
    TopologyEdge,
)
from multicloud_network_mcp.contracts.urn import build_urn

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _urn(native_id: str) -> str:
    return build_urn(provider="aws", scope={}, resource_type="network", native_id=native_id)


def test_topology_edge_requires_at_least_one_evidence_entry() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        TopologyEdge(
            source_urn=_urn("a"), target_urn=_urn("b"), relationship="routes_to", evidence=[]
        )


def test_topology_edge_evidence_is_a_fact_not_a_string() -> None:
    edge = TopologyEdge(
        source_urn=_urn("a"),
        target_urn=_urn("b"),
        relationship="routes_to",
        evidence=[SourceEvidence(source="route_table:rtb-1", detail="0.0.0.0/0 -> igw-1")],
    )
    assert edge.evidence[0].source == "route_table:rtb-1"
    assert edge.evidence[0].detail == "0.0.0.0/0 -> igw-1"


def test_topology_edge_accepts_multiple_evidence_entries() -> None:
    edge = TopologyEdge(
        source_urn=_urn("a"),
        target_urn=_urn("b"),
        relationship="peers_with",
        evidence=[
            {"source": "peering:pcx-1", "detail": "requester_vpc_id=vpc-a"},
            {"source": "peering:pcx-1", "detail": "accepter_vpc_id=vpc-b"},
        ],
    )
    assert len(edge.evidence) == 2


def test_finding_evidence_indices_reference_reasoning_positions() -> None:
    finding = Finding(
        rule_id="ROUTE-002",
        rule_version="1.0.0",
        provider="aws",
        severity="medium",
        confidence="high",
        summary="overlapping CIDR routes",
        evidence=[
            SourceEvidence(source="route:rtb-1-static-a", detail="10.20.0.0/16 priority=1000"),
            SourceEvidence(source="route:rtb-1-static-b", detail="10.20.4.0/24 priority=900"),
        ],
        reasoning=[
            ReasoningStep(
                step=1,
                description="static-b's range is fully contained in static-a's",
                evidence_indices=[0, 1],
            ),
            ReasoningStep(
                step=2,
                description="static-b has higher priority (lower number wins)",
                evidence_indices=[1],
            ),
        ],
        freshness=FRESHNESS,
    )
    assert finding.reasoning[0].evidence_indices == [0, 1]
    assert all(
        idx < len(finding.evidence) for step in finding.reasoning for idx in step.evidence_indices
    )


def test_finding_indeterminate_confidence_still_carries_summary_and_limitations() -> None:
    # A finding that can't reach a conclusion is still a first-class
    # output, never a silent omission -- it must still explain what
    # couldn't be determined and why.
    finding = Finding(
        rule_id="FW-002",
        rule_version="1.0.0",
        provider="gcp",
        severity="medium",
        confidence="indeterminate",
        summary="Hierarchical policies were not supplied for this scan.",
        limitations=[
            "Hierarchical Firewall Policies require an explicit parent_id -- none was supplied."
        ],
        freshness=FRESHNESS,
    )
    assert finding.confidence == "indeterminate"
    assert finding.summary
    assert finding.limitations


def test_finding_reasoning_is_the_inference_evidence_is_the_fact() -> None:
    # Structural proof of the fact-vs-inference split the diagnostics.py
    # module docstring describes: evidence entries are SourceEvidence
    # (an observed fact), reasoning entries are ReasoningStep (a
    # numbered inference chain) -- two distinct types, not one list.
    finding = Finding(
        rule_id="X",
        rule_version="1.0.0",
        provider="aws",
        severity="low",
        confidence="high",
        summary="s",
        freshness=FRESHNESS,
    )
    assert finding.evidence == []
    assert finding.reasoning == []
    assert type(SourceEvidence(source="a", detail="b")) is not type(
        ReasoningStep(step=1, description="c")
    )
