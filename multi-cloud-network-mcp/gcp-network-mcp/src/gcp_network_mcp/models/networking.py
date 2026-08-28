"""Normalized models for VPC Networks and Subnetworks."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class Network(GcpResource):
    """Normalized entry from ``NetworksClient.list``/``get``.

    ``mode`` is derived, not a raw GCP field: ``"auto"`` when
    ``auto_create_subnetworks`` is true, ``"custom"`` otherwise -- GCP's
    own API only exposes the boolean, but "auto vs custom mode" is the
    vocabulary operators actually use.
    """

    mode: str
    mtu: int | None = None
    subnetwork_self_links: list[str] = Field(default_factory=list)
    peering_names: list[str] = Field(default_factory=list)
    firewall_policy_self_link: str | None = None
    network_firewall_policy_enforcement_order: str | None = None
    routing_mode: str | None = None
    internal_ipv6_range: str | None = None


class SecondaryRange(BaseModel):
    """One secondary IP range on a Subnetwork (e.g. for GKE pod/service CIDRs)."""

    range_name: str
    ip_cidr_range: str


class Subnetwork(GcpResource):
    """Normalized entry from ``SubnetworksClient.list``/``aggregated_list``/``get``."""

    network_self_link: str
    ip_cidr_range: str
    gateway_address: str | None = None
    purpose: str | None = None
    role: str | None = None
    stack_type: str | None = None
    ipv6_cidr_range: str | None = None
    private_ip_google_access: bool | None = None
    private_ipv6_google_access: str | None = None
    enable_flow_logs: bool | None = None
    state: str | None = None
    secondary_ip_ranges: list[SecondaryRange] = Field(default_factory=list)


__all__ = ["Network", "SecondaryRange", "Subnetwork"]
