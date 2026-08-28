"""Diagnostic finding and path explanation, with fact vs. inference,
confidence, assumptions, limitations, freshness, and remediation advice.

Nearly a verbatim unification of what AWS/Azure/GCP's own diagnostics
engines already independently converged on -- all three define an
essentially identical ``Finding`` shape today. The one structural change
here: ``affected_resources``/``evidence[].source`` reference this
contract's ``urn`` scheme instead of a raw provider-native ID string, so
a finding is unambiguous even when reasoning across resources from more
than one provider's scope.

**Fact vs. inference**: ``evidence`` entries are facts -- each one names
the exact already-collected record a claim rests on, never an inference
dressed up as an observation. ``reasoning`` entries are the inference
chain -- the deterministic steps from those facts to the finding's
conclusion, always emitted in evaluation order so a human can replay the
same reasoning by hand. A finding's ``summary``/``severity`` are
conclusions (inference); its ``evidence`` list is what those conclusions
are answerable to.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from multicloud_network_mcp.contracts.models.common import SourceEvidence
from multicloud_network_mcp.contracts.models.enums import PathVerdict


class ReasoningStep(BaseModel):
    """One step in a deterministic inference chain from evidence to
    conclusion. ``step`` is 1-indexed and steps are always emitted in
    the order they were actually evaluated. ``evidence_indices``
    references positions into the owning ``Finding.evidence`` list."""

    step: int
    description: str
    evidence_indices: list[int] = Field(default_factory=list)


class Finding(BaseModel):
    """One deterministic diagnostic conclusion.

    Every field is present unconditionally -- not optional-and-usually-
    omitted. A finding with ``confidence`` ``"indeterminate"`` still
    carries a ``summary`` (what could not be determined, and why) and
    ``limitations`` (what evidence was missing); it is a first-class
    output, never an error or a silent omission -- a rule that cannot
    reach a conclusion because required evidence is missing must say so
    explicitly, not look identical to "checked, found no issue."

    ``rule_id``/``rule_version`` identify which versioned rule produced
    this finding (see ``docs/normalization.md`` for how each provider's
    own rule catalog maps its rule IDs into this contract -- rule IDs
    themselves are NOT unified across providers, since the underlying
    checks genuinely differ per cloud; a consumer correlates findings by
    ``affected_resources``/``severity``/``confidence``, not by expecting
    the same ``rule_id`` string to mean the same thing across providers).

    ``remediation`` is always advisory text for a human to act on --
    nothing in this contract (or any conformant adapter) executes it.
    """

    rule_id: str
    rule_version: str
    provider: str
    severity: str
    confidence: str
    summary: str
    affected_resources: list[str] = Field(default_factory=list)
    """URNs of the resources this finding concerns."""
    evidence: list[SourceEvidence] = Field(default_factory=list)
    """Facts -- always specific, already-observed values."""
    reasoning: list[ReasoningStep] = Field(default_factory=list)
    """Inference -- the deterministic chain from evidence to conclusion."""
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    freshness: str
    remediation: str | None = None


class PathExplanation(BaseModel):
    """One deterministic evaluation of whether traffic from a source to
    a destination would be allowed, blocked, or only partially
    evaluated -- the unification of every cloud repo's own
    "explain a network path" tool.

    ``overall_verdict`` is ``ALLOWED`` only when every underlying
    ``findings`` entry independently concluded so; ``BLOCKED`` if any
    did; ``PARTIALLY_EVALUATED`` if any finding's evidence was
    incomplete -- never silently upgraded to ``ALLOWED``. ``findings``
    holds the full per-layer reasoning (route resolution, firewall/NSG/
    security-group evaluation, and any hierarchical/organization-level
    policy layer a provider exposes) rather than this contract
    re-modeling each provider's distinct layer set -- see
    ``docs/normalization.md`` for how each provider's specific layers
    map onto this one ``findings`` list.
    """

    provider: str
    source: str
    """A URN if the source is a known resource, otherwise an IP/CIDR."""
    destination: str
    """A URN if the destination is a known resource, otherwise an IP/CIDR."""
    protocol: str | None = None
    port: int | None = None
    overall_verdict: PathVerdict
    findings: list[Finding] = Field(default_factory=list)
    freshness: str


__all__ = ["Finding", "PathExplanation", "ReasoningStep"]
