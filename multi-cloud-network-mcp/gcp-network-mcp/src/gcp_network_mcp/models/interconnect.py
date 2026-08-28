"""Normalized models for Cloud Interconnect: interconnects,
attachments, locations, and diagnostics.

``InterconnectAttachment``'s underlying SDK type carries a ``pairing_key``
field (the Partner Interconnect provisioning secret a customer's partner
carrier needs to complete provisioning) that no normalizer in
``gcp/interconnect.py`` ever reads -- redaction *by omission*, per this
milestone's explicit guardrail ("never return pairing keys or secrets").
``InterconnectAttachment`` is stamped ``redacted: bool = True``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class InterconnectCircuitInfo(BaseModel):
    google_circuit_id: str | None = None
    google_demarc_id: str | None = None
    customer_demarc_id: str | None = None


class Interconnect(GcpResource):
    """Normalized entry from ``InterconnectsClient.list``/``get``.
    Global resource (not region/zone-scoped). Dedicated Interconnect only
    -- Partner Interconnect is represented on the attachment side
    (``InterconnectAttachment.edge_availability_domain``/``partner_metadata``)."""

    interconnect_type: str | None = None
    link_type: str | None = None
    location: str | None = None
    customer_name: str | None = None
    admin_enabled: bool | None = None
    operational_status: str | None = None
    state: str | None = None
    provisioned_link_count: int | None = None
    requested_link_count: int | None = None
    google_ip_address: str | None = None
    peer_ip_address: str | None = None
    circuit_infos: list[InterconnectCircuitInfo] = Field(default_factory=list)
    interconnect_attachment_self_links: list[str] = Field(default_factory=list)


class InterconnectAttachmentPartnerMetadata(BaseModel):
    """Partner-provided identification for a Partner Interconnect
    attachment -- never a secret; the pairing key itself is never read
    (see module docstring)."""

    partner_name: str | None = None
    interconnect_name: str | None = None
    portal_url: str | None = None


class InterconnectAttachment(GcpResource):
    """Normalized entry from ``InterconnectAttachmentsClient.list``/
    ``aggregated_list``/``get``. Never carries ``pairing_key`` -- see
    module docstring."""

    redacted: bool = True
    interconnect_self_link: str | None = None
    # An attachment has no direct network reference -- it attaches to a
    # Router, whose network you resolve separately (Router.network).
    router_self_link: str | None = None
    attachment_type: str | None = None
    edge_availability_domain: str | None = None
    bandwidth: str | None = None
    vlan_tag8021q: int | None = None
    mtu: int | None = None
    state: str | None = None
    operational_status: str | None = None
    cloud_router_ip_address: str | None = None
    customer_router_ip_address: str | None = None
    partner_asn: int | None = None
    partner_metadata: InterconnectAttachmentPartnerMetadata | None = None
    encryption: str | None = None
    stack_type: str | None = None


class InterconnectLocation(BaseModel):
    """Normalized entry from ``InterconnectLocationsClient.list``/``get``
    -- a colocation facility where a Dedicated Interconnect can be
    provisioned. Global metadata, not project-scoped."""

    self_link: str | None = None
    name: str
    description: str | None = None
    address: str | None = None
    city: str | None = None
    continent: str | None = None
    facility_provider: str | None = None
    status: str | None = None
    available_link_types: list[str] = Field(default_factory=list)
    observed_at: str
    source_api: str = "InterconnectLocationsClient.list"


class InterconnectDiagnosticsLinkStatus(BaseModel):
    circuit_id: str | None = None
    operational_status: str | None = None
    google_demarc: str | None = None
    receiving_optical_power_dbm: float | None = None
    transmitting_optical_power_dbm: float | None = None


class InterconnectDiagnostics(BaseModel):
    """From ``InterconnectsClient.get_diagnostics`` -- the read-only
    computed physical-link health view, distinct from the interconnect's
    own static configuration fields."""

    interconnect_self_link: str
    mac_address: str | None = None
    bundle_operational_status: str | None = None
    bundle_aggregation_type: str | None = None
    links: list[InterconnectDiagnosticsLinkStatus] = Field(default_factory=list)
    observed_at: str
    source_api: str = "InterconnectsClient.get_diagnostics"


__all__ = [
    "Interconnect",
    "InterconnectAttachment",
    "InterconnectAttachmentPartnerMetadata",
    "InterconnectCircuitInfo",
    "InterconnectDiagnostics",
    "InterconnectDiagnosticsLinkStatus",
    "InterconnectLocation",
]
