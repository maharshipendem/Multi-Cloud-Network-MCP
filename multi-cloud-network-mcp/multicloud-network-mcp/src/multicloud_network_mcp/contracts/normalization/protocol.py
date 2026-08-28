"""Protocol normalization table.

Each provider represents a firewall/route protocol differently:

- **AWS** (``SecurityGroupRule.ip_protocol`` /
  ``NetworkAclEntry.protocol``): a lowercase keyword (``"tcp"``,
  ``"udp"``, ``"icmp"``) for the common cases, ``"-1"`` for "all
  protocols," or a raw IANA protocol number as a string for anything
  else.
- **Azure** (``SecurityRule.protocol``): a capitalized keyword
  (``"Tcp"``, ``"Udp"``, ``"Icmp"``, ``"Esp"``, ``"Ah"``), or ``"*"``
  for "all protocols."
- **GCP** (``Firewall.allowed[].I_p_protocol``/``denied[].I_p_protocol``):
  a lowercase keyword (``"tcp"``, ``"udp"``, ``"icmp"``, ``"esp"``,
  ``"ah"``, ``"sctp"``), or a raw IANA protocol number as a string.

``normalize_protocol()`` maps any of these onto this contract's
``Protocol`` vocabulary (see ``models/enums.py``) plus the underlying
IANA protocol number where known. A raw numeric protocol with no
keyword in this table's closed set is **not** silently forced into
``OTHER`` and discarded -- ``NormalizedProtocol.iana_number`` still
carries the original number, and a caller populating a canonical
``FirewallRule.protocol`` field should additionally put the untouched
raw string in ``extensions[provider]["protocol"]`` when the mapping
lands on ``OTHER``, per this contract's "never silently coerce unknown
data" guardrail.
"""

from __future__ import annotations

from pydantic import BaseModel

from multicloud_network_mcp.contracts.models.enums import Protocol

# keyword (lowercased) -> (Protocol, IANA number)
_KEYWORD_TABLE: dict[str, tuple[Protocol, int | None]] = {
    "tcp": (Protocol.TCP, 6),
    "udp": (Protocol.UDP, 17),
    "icmp": (Protocol.ICMP, 1),
    "icmpv6": (Protocol.ICMPV6, 58),
    "esp": (Protocol.ESP, 50),
    "ah": (Protocol.AH, 51),
    "gre": (Protocol.GRE, 47),
    "-1": (Protocol.ALL, None),
    "*": (Protocol.ALL, None),
    "all": (Protocol.ALL, None),
    "any": (Protocol.ALL, None),
}

# IANA protocol number -> Protocol, for a raw numeric string input.
_IANA_NUMBER_TABLE: dict[int, Protocol] = {
    1: Protocol.ICMP,
    6: Protocol.TCP,
    17: Protocol.UDP,
    47: Protocol.GRE,
    50: Protocol.ESP,
    51: Protocol.AH,
    58: Protocol.ICMPV6,
}


class NormalizedProtocol(BaseModel):
    protocol: str
    """A ``Protocol`` enum value (plain ``str``-typed per this
    contract's normalization-target-enum rule -- see
    ``models/enums.py``)."""
    iana_number: int | None = None
    raw: str
    """The original, untouched provider value -- always preserved."""


def normalize_protocol(raw: str) -> NormalizedProtocol:
    """Normalize one provider's raw protocol string. Never raises --
    an unrecognized value normalizes to ``Protocol.OTHER`` with
    ``iana_number=None`` rather than failing the whole mapping, but the
    original ``raw`` value is always retained on the result so nothing
    is silently lost."""
    lowered = raw.strip().lower()
    if lowered in _KEYWORD_TABLE:
        protocol, iana_number = _KEYWORD_TABLE[lowered]
        return NormalizedProtocol(protocol=protocol.value, iana_number=iana_number, raw=raw)
    if lowered.lstrip("-").isdigit():
        number = int(lowered)
        protocol = _IANA_NUMBER_TABLE.get(number, Protocol.OTHER)
        return NormalizedProtocol(protocol=protocol.value, iana_number=number, raw=raw)
    return NormalizedProtocol(protocol=Protocol.OTHER.value, iana_number=None, raw=raw)


__all__ = ["NormalizedProtocol", "normalize_protocol"]
