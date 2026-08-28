"""Normalized models for Cloud Routers and their embedded Cloud NAT
configurations (GCP has no separate NAT-listing API -- NAT config lives
entirely inside ``Router.nats``)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class RouterNatSummary(BaseModel):
    """One Cloud NAT gateway configured on a Router."""

    name: str
    nat_ip_allocate_option: str | None = None
    source_subnetwork_ip_ranges_to_nat: str | None = None
    nat_ips: list[str] = Field(default_factory=list)
    min_ports_per_vm: int | None = None
    max_ports_per_vm: int | None = None
    enable_endpoint_independent_mapping: bool | None = None


class RouterSummary(GcpResource):
    """Normalized entry from ``RoutersClient.list``/``aggregated_list``/``get``."""

    network_self_link: str
    bgp_asn: int | None = None
    nats: list[RouterNatSummary] = Field(default_factory=list)


__all__ = ["RouterNatSummary", "RouterSummary"]
