"""CIDR/IP normalization: IPv4, IPv6, canonicalization, and rejection
of malformed input rather than silent coercion."""

from __future__ import annotations

import pytest

from multicloud_network_mcp.contracts.models.enums import IpVersion
from multicloud_network_mcp.contracts.normalization.cidr import (
    ip_version_of,
    is_valid_cidr,
    normalize_cidr,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.0.0.0/16", "10.0.0.0/16"),
        ("10.0.0.5", "10.0.0.5/32"),
        ("0.0.0.0/0", "0.0.0.0/0"),
        ("2001:db8::/32", "2001:db8::/32"),
        ("::1", "::1/128"),
    ],
)
def test_normalize_cidr(raw: str, expected: str) -> None:
    assert normalize_cidr(raw) == expected


def test_normalize_cidr_non_strict_host_bits_set() -> None:
    # A network with host bits set (e.g. 10.0.0.5/24) is a common
    # real-world sloppy input -- normalize_cidr must not raise, it
    # should behave like ip_network(..., strict=False).
    assert normalize_cidr("10.0.0.5/24") == "10.0.0.0/24"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.0.0.0/16", IpVersion.IPV4),
        ("10.0.0.5", IpVersion.IPV4),
        ("2001:db8::/32", IpVersion.IPV6),
        ("::1", IpVersion.IPV6),
    ],
)
def test_ip_version_of(raw: str, expected: IpVersion) -> None:
    assert ip_version_of(raw) == expected


@pytest.mark.parametrize("garbage", ["not-a-cidr", "999.999.999.999", "", "10.0.0.0/99"])
def test_normalize_cidr_raises_on_malformed_input(garbage: str) -> None:
    with pytest.raises(ValueError):
        normalize_cidr(garbage)


@pytest.mark.parametrize("garbage", ["not-a-cidr", "999.999.999.999"])
def test_ip_version_of_raises_on_malformed_input(garbage: str) -> None:
    with pytest.raises(ValueError):
        ip_version_of(garbage)


def test_is_valid_cidr_never_raises() -> None:
    assert is_valid_cidr("10.0.0.0/16") is True
    assert is_valid_cidr("garbage") is False
