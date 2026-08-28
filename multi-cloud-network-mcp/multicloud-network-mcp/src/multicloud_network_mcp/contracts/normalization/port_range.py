"""Port range normalization.

- **AWS** (``SecurityGroupRule.from_port``/``to_port``): two separate
  nullable integers. A single port has ``from_port == to_port``; "all
  ports" is represented by both being ``None`` (present on the rule at
  all only when the protocol is port-based).
- **Azure** (``SecurityRule.destination_port_range``/
  ``destination_port_ranges``): a string, either a single port
  (``"80"``), a range (``"80-443"``), or ``"*"`` for all ports; a list
  variant when more than one discontiguous range/port applies.
- **GCP** (``Firewall.allowed[].ports``): a list of strings, each either
  a single port (``"80"``) or a range (``"8080-8090"``); an empty/absent
  list means "all ports for this protocol."

This contract's canonical form is a single string: ``"80"`` for one
port, ``"80-443"`` for a range, or ``None`` for "all ports" -- matching
what a human would type into any of the three consoles. A rule with
*multiple discontiguous* port ranges (Azure's plural field, GCP's list
with more than one entry) normalizes to a **list** of these canonical
strings via ``normalize_port_ranges`` (plural) -- the singular
``normalize_port_range`` handles exactly one range/port.
"""

from __future__ import annotations


def normalize_port_range(
    *, start: int | None = None, end: int | None = None, raw: str | None = None
) -> str | None:
    """Normalize one port or range. Pass either ``raw`` (an Azure/GCP-
    style string, including ``"*"``/``""``/``None`` for "all ports") or
    ``start``/``end`` (AWS-style paired integers, both ``None`` for "all
    ports"). Raises ``ValueError`` if both or neither input style is
    given, and if a numeric value is out of the valid 0-65535 port
    range -- never silently clamps or drops an out-of-range value."""
    if raw is not None and (start is not None or end is not None):
        raise ValueError("Pass either raw= or start=/end=, not both")

    if raw is not None:
        stripped = raw.strip()
        if stripped in ("", "*"):
            return None
        if "-" in stripped:
            lo, hi = stripped.split("-", 1)
            return normalize_port_range(start=int(lo), end=int(hi))
        return normalize_port_range(start=int(stripped), end=int(stripped))

    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ValueError(f"start/end must both be set or both be None, got {start=} {end=}")
    for value in (start, end):
        if not (0 <= value <= 65535):
            raise ValueError(f"port {value} out of valid range 0-65535")
    if start > end:
        raise ValueError(f"start ({start}) must be <= end ({end})")
    return str(start) if start == end else f"{start}-{end}"


def normalize_port_ranges(raw_list: list[str]) -> list[str]:
    """Normalize a provider's list-of-ranges field (Azure's plural
    ``destination_port_ranges``, GCP's ``ports``) into a list of
    canonical single-range strings. An empty input list means "all
    ports" and normalizes to an empty output list, matching this
    contract's convention that an empty ``port_ranges`` list on a
    ``FirewallRule`` means unrestricted, same as a ``None`` singular
    ``port_range``."""
    normalized = []
    for entry in raw_list:
        value = normalize_port_range(raw=entry)
        if value is not None:
            normalized.append(value)
    return normalized


__all__ = ["normalize_port_range", "normalize_port_ranges"]
