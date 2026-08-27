"""Core diagnostic output contracts: Finding, Evidence, ReasoningStep, and
the rule catalog every diagnostic module registers into.

``Confidence`` carries an explicit ``"indeterminate"`` value rather than
treating "could not determine" as a missing/omitted finding. A rule that
cannot reach a conclusion because required evidence is missing (a security
group it could not fetch, a peered VPC outside the analyzed snapshot) must
say so, with ``limitations`` explaining what was missing -- silently
omitting the finding would look identical to "checked, found no issue,"
which is the one thing this milestone's guardrails explicitly forbid
("claim certainty with incomplete data").
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low", "indeterminate"]


class Evidence(BaseModel):
    """One specific, already-collected fact a finding's reasoning relies on.

    ``source`` identifies exactly which snapshot record the fact came from
    (e.g. ``"route_table:rtb-0123456789abcdef0"``,
    ``"security_group_rule:sgr-0123456789abcdef0"``) so a reader can trace
    a conclusion back to a specific AWS API response field, never an
    inference dressed up as an observation.
    """

    source: str
    detail: str


class ReasoningStep(BaseModel):
    """One step in a deterministic chain from evidence to conclusion.

    ``step`` is the step's 1-indexed position; steps are always emitted in
    the order they were actually evaluated, so replaying them reproduces
    the same reasoning a human would need to follow to reach the same
    conclusion by hand.
    """

    step: int
    description: str
    evidence_indices: list[int] = Field(default_factory=list)


class Finding(BaseModel):
    """One deterministic diagnostic conclusion.

    Every field the milestone's spec requires is present unconditionally
    (not optional-and-usually-omitted): ``severity``, ``confidence``,
    ``summary``, ``affected_resources``, ``evidence``, ``reasoning``,
    ``assumptions``, ``limitations``, ``freshness``, and ``remediation``.
    A finding with ``confidence="indeterminate"`` still carries a
    ``summary`` (stating what could not be determined and why) and
    ``limitations`` (what evidence was missing) -- it is a first-class
    output, not an error or an omission.

    ``remediation`` is always advisory text for a human to act on; nothing
    in this package (or anywhere in this repository) executes it. There is
    no "apply this fix" code path anywhere this field's value can reach.
    """

    rule_id: str
    rule_version: str
    severity: Severity
    confidence: Confidence
    summary: str
    affected_resources: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    reasoning: list[ReasoningStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    freshness: str
    remediation: str | None = None


class RuleMetadata(BaseModel):
    """Catalog entry for one diagnostic rule.

    ``rule_id`` is a stable, versioned identifier (e.g. ``"ROUTE-001"``);
    ``version`` follows semantic versioning for the rule's *logic* (a
    change to what the rule detects or how it reasons bumps the version,
    a wording-only summary/remediation-text change does not). Domain
    prefixes: ``ROUTE-*`` (route resolution), ``SEC-*`` (security
    group/NACL evaluation), ``EXPOSE-*`` (internet exposure),
    ``CONSIST-*`` (route-table/attachment consistency), ``HEALTH-*``
    (resource state checks).
    """

    rule_id: str
    version: str
    title: str
    description: str
    default_severity: Severity


_RULE_CATALOG: dict[str, RuleMetadata] = {}


def register_rule(
    rule_id: str, version: str, title: str, description: str, default_severity: Severity
) -> RuleMetadata:
    """Register a rule in the catalog. Raises on a duplicate ``rule_id``
    (a rule ID must be registered exactly once, at import time, by the
    module that implements it) so the catalog can never silently drift
    from what actually runs."""
    if rule_id in _RULE_CATALOG:
        raise ValueError(f"Rule '{rule_id}' is already registered.")
    metadata = RuleMetadata(
        rule_id=rule_id,
        version=version,
        title=title,
        description=description,
        default_severity=default_severity,
    )
    _RULE_CATALOG[rule_id] = metadata
    return metadata


def rule_catalog() -> dict[str, RuleMetadata]:
    """Return a copy of the full rule catalog (rule_id -> metadata)."""
    return dict(_RULE_CATALOG)


def get_rule(rule_id: str) -> RuleMetadata:
    return _RULE_CATALOG[rule_id]


__all__ = [
    "Confidence",
    "Evidence",
    "Finding",
    "ReasoningStep",
    "RuleMetadata",
    "Severity",
    "get_rule",
    "register_rule",
    "rule_catalog",
]
