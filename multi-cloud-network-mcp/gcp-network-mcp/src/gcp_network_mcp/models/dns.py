"""Normalized models for Cloud DNS managed zones and record summaries.

``google-cloud-dns`` is the only Google-published Python client library
for Cloud DNS -- there is no gapic-generated version. It is also the one
client in this codebase's dependency set with no ``visibility``/
``privateVisibilityConfig``/``forwardingConfig``/``peeringConfig``
accessor and no Policy/Response Policy support at all (that surface
simply isn't wrapped by this library). ``DnsZone`` therefore only carries
what the library actually exposes; ``policy_support`` fields it cannot
populate are always ``None``, and DNS Policies/Response Policies/
forwarding zones are not represented by any model in this milestone --
see docs/limitations.md#cloud-dns.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DnsZone(BaseModel):
    name: str
    project_id: str
    dns_name: str
    description: str | None = None
    zone_id: str | None = None
    name_servers: list[str] = Field(default_factory=list)
    name_server_set: str | None = None
    observed_at: str
    source_api: str = "google.cloud.dns.Client.list_zones"


class DnsRecordSetSummary(BaseModel):
    """One resource record set within a zone. ``rrdatas`` is bounded by
    the caller's ``max_records`` -- see gcp/dns.py."""

    name: str
    record_type: str
    ttl: int | None = None
    rrdatas: list[str] = Field(default_factory=list)


__all__ = ["DnsRecordSetSummary", "DnsZone"]
