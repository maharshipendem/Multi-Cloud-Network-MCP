"""Normalized model for Packet Mirroring *configuration* only.

Never carries mirrored packet content -- Packet Mirroring's own API has
no method that would return captured packet data in the first place (it
streams to a collector ILB the caller configured); this server exposes
only the mirroring policy's configuration, per this milestone's explicit
guardrail.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class PacketMirroringFilterSummary(BaseModel):
    ip_protocols: list[str] = Field(default_factory=list)
    cidr_ranges: list[str] = Field(default_factory=list)
    direction: str | None = None


class PacketMirroringPolicy(GcpResource):
    """Normalized entry from ``PacketMirroringsClient.list``/``aggregated_list``/``get``."""

    network_self_link: str
    collector_ilb_forwarding_rule: str | None = None
    enable: str | None = None
    priority: int | None = None
    mirrored_instance_self_links: list[str] = Field(default_factory=list)
    mirrored_subnetwork_self_links: list[str] = Field(default_factory=list)
    mirrored_tags: list[str] = Field(default_factory=list)
    filter: PacketMirroringFilterSummary | None = None


__all__ = ["PacketMirroringFilterSummary", "PacketMirroringPolicy"]
