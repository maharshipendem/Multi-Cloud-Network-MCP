"""Normalized models for reserved IP Addresses (regional and global)."""

from __future__ import annotations

from pydantic import Field

from gcp_network_mcp.models.common import GcpResource


class AddressSummary(GcpResource):
    """Normalized entry from ``AddressesClient``/``GlobalAddressesClient``
    ``list``/``aggregated_list``/``get``."""

    address: str
    address_type: str | None = None
    status: str | None = None
    purpose: str | None = None
    network_self_link: str | None = None
    subnetwork_self_link: str | None = None
    network_tier: str | None = None
    users: list[str] = Field(default_factory=list)


__all__ = ["AddressSummary"]
