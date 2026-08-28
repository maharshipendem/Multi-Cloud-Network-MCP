"""Severity normalization.

Unlike every other table in this package, all three cloud repos' own
diagnostics engines already use the *exact same* five-value
``Severity`` vocabulary (``critical``/``high``/``medium``/``low``/
``info``) and four-value ``Confidence`` vocabulary
(``high``/``medium``/``low``/``indeterminate``) today -- there is no
provider-specific raw string to map from. This module exists anyway,
for two reasons: (1) forward compatibility -- a future, non-Python, or
differently-designed adapter (or a fourth cloud provider) may not use
these exact string literals, and having a normalization entry point
means that adapter has one obvious place to plug in a real mapping
without this contract's core models needing to change; (2) so
``Severity``/``Confidence`` participate in the same
"has a documented, testable normalization function" pattern as every
other normalization-target vocabulary in this package, rather than
being a silent exception.
"""

from __future__ import annotations

from multicloud_network_mcp.contracts.models.enums import Confidence, Severity

_SEVERITY_TABLE: dict[str, Severity] = {s.value: s for s in Severity}
_CONFIDENCE_TABLE: dict[str, Confidence] = {c.value: c for c in Confidence}


def normalize_severity(raw: str) -> str:
    """Normalize a raw severity string (case-insensitive) onto
    ``Severity``'s vocabulary. An unrecognized value normalizes to
    ``"info"`` (the least alarming value -- a normalization function
    must never silently invent urgency an adapter didn't actually
    observe) rather than raising, since severity is advisory metadata,
    not structural data whose malformation should abort a mapping."""
    return _SEVERITY_TABLE.get(raw.strip().lower(), Severity.INFO).value


def normalize_confidence(raw: str) -> str:
    """Normalize a raw confidence string (case-insensitive) onto
    ``Confidence``'s vocabulary. An unrecognized value normalizes to
    ``"indeterminate"`` -- the correct default for "we don't actually
    know how confident to be in this," never silently upgraded to a
    higher-confidence value."""
    return _CONFIDENCE_TABLE.get(raw.strip().lower(), Confidence.INDETERMINATE).value


__all__ = ["normalize_confidence", "normalize_severity"]
