"""CIDR/IP normalization -- pure value transforms, no provider SDK
imports, no network calls.

Every provider represents an address/CIDR range as a plain string
already (AWS ``"10.0.0.0/16"``, Azure ``"10.0.0.0/16"``, GCP
``"10.0.0.0/16"``) -- the string *format* rarely needs normalizing.
What genuinely varies is: whether a bare IP (no ``/prefix``) is
returned for a single-host range, leading zeros/non-canonical forms
(rare but not impossible from hand-edited configs), and IPv4 vs. IPv6.
"""

from __future__ import annotations

import ipaddress

from multicloud_network_mcp.contracts.models.enums import IpVersion


def normalize_cidr(value: str) -> str:
    """Return ``value`` in canonical CIDR form (``ip_network`` prefixed
    form, e.g. a bare host address ``"10.0.0.5"`` becomes
    ``"10.0.0.5/32"``). Raises ``ValueError`` on anything that isn't a
    valid IPv4/IPv6 address or network -- never silently coerces
    malformed input into an empty/default value, per this contract's
    "never silently coerce unknown data" guardrail."""
    if "/" in value:
        network = ipaddress.ip_network(value, strict=False)
    else:
        addr = ipaddress.ip_address(value)
        network = ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}")
    return str(network)


def ip_version_of(value: str) -> IpVersion:
    """Determine whether a CIDR/address string is IPv4 or IPv6. Raises
    ``ValueError`` on invalid input -- same "never silently coerce"
    discipline as ``normalize_cidr``."""
    network_or_addr = value.split("/", 1)[0]
    addr = ipaddress.ip_address(network_or_addr)
    return IpVersion.IPV6 if addr.version == 6 else IpVersion.IPV4


def is_valid_cidr(value: str) -> bool:
    """A non-raising check, for callers that want to skip/flag
    malformed input rather than crash -- ``normalize_cidr``/
    ``ip_version_of`` themselves never silently swallow an error, this
    is the one explicit opt-in to "tell me if it's valid, don't raise"."""
    try:
        normalize_cidr(value)
    except ValueError:
        return False
    return True


__all__ = ["ip_version_of", "is_valid_cidr", "normalize_cidr"]
