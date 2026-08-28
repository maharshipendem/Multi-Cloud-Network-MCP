"""Service-layer functions for Cloud Interconnect: interconnects,
attachments, locations, and diagnostics."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate, paginate_aggregated
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.common import parse_self_link
from gcp_network_mcp.models.interconnect import (
    Interconnect,
    InterconnectAttachment,
    InterconnectAttachmentPartnerMetadata,
    InterconnectCircuitInfo,
    InterconnectDiagnostics,
    InterconnectDiagnosticsLinkStatus,
    InterconnectLocation,
)


def normalize_interconnect(
    interconnect: compute_v1.Interconnect, *, project_id: str
) -> Interconnect:
    return Interconnect(
        self_link=interconnect.self_link or None,
        id=str(interconnect.id) if interconnect.id else None,
        name=interconnect.name,
        project_id=project_id,
        interconnect_type=interconnect.interconnect_type or None,
        link_type=interconnect.link_type or None,
        location=interconnect.location or None,
        customer_name=interconnect.customer_name or None,
        admin_enabled=interconnect.admin_enabled,
        operational_status=interconnect.operational_status or None,
        state=interconnect.state or None,
        provisioned_link_count=interconnect.provisioned_link_count or None,
        requested_link_count=interconnect.requested_link_count or None,
        google_ip_address=interconnect.google_ip_address or None,
        peer_ip_address=interconnect.peer_ip_address or None,
        circuit_infos=[
            InterconnectCircuitInfo(
                google_circuit_id=c.google_circuit_id or None,
                google_demarc_id=c.google_demarc_id or None,
                customer_demarc_id=c.customer_demarc_id or None,
            )
            for c in interconnect.circuit_infos
        ],
        interconnect_attachment_self_links=list(interconnect.interconnect_attachments),
        observed_at=now_iso(),
        source_api="InterconnectsClient.list",
    )


def list_interconnects(client_factory: ClientFactory, *, project_id: str) -> list[Interconnect]:
    """Interconnects are a global (project-scoped, not region/zone-scoped)
    resource."""
    raw = paginate(
        client_factory.interconnects(),
        "list",
        resource_type="interconnect",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_interconnect(i, project_id=project_id) for i in raw]


def get_interconnect_diagnostics(
    client_factory: ClientFactory, *, project_id: str, interconnect_name: str
) -> InterconnectDiagnostics:
    interconnect_self_link = (
        f"https://www.googleapis.com/compute/v1/projects/{project_id}/global/"
        f"interconnects/{interconnect_name}"
    )
    diagnostics = call_readonly(
        client_factory.interconnects(),
        "get_diagnostics",
        project=project_id,
        interconnect=interconnect_name,
    ).result
    return InterconnectDiagnostics(
        interconnect_self_link=interconnect_self_link,
        mac_address=diagnostics.mac_address or None,
        bundle_operational_status=diagnostics.bundle_operational_status or None,
        bundle_aggregation_type=diagnostics.bundle_aggregation_type or None,
        links=[
            InterconnectDiagnosticsLinkStatus(
                circuit_id=link.circuit_id or None,
                operational_status=link.operational_status or None,
                google_demarc=link.google_demarc or None,
                receiving_optical_power_dbm=(
                    link.receiving_optical_power.value
                    if "receiving_optical_power" in link
                    else None
                ),
                transmitting_optical_power_dbm=(
                    link.transmitting_optical_power.value
                    if "transmitting_optical_power" in link
                    else None
                ),
            )
            for link in diagnostics.links
        ],
        observed_at=now_iso(),
    )


def normalize_interconnect_attachment(
    attachment: compute_v1.InterconnectAttachment, *, project_id: str
) -> InterconnectAttachment:
    parsed = parse_self_link(attachment.self_link) if attachment.self_link else None
    partner_metadata = None
    if "partner_metadata" in attachment:
        partner_metadata = InterconnectAttachmentPartnerMetadata(
            partner_name=attachment.partner_metadata.partner_name or None,
            interconnect_name=attachment.partner_metadata.interconnect_name or None,
            portal_url=attachment.partner_metadata.portal_url or None,
        )
    return InterconnectAttachment(
        self_link=attachment.self_link or None,
        id=str(attachment.id) if attachment.id else None,
        name=attachment.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        interconnect_self_link=attachment.interconnect or None,
        router_self_link=attachment.router or None,
        attachment_type=attachment.type_ or None,
        edge_availability_domain=attachment.edge_availability_domain or None,
        bandwidth=attachment.bandwidth or None,
        vlan_tag8021q=attachment.vlan_tag8021q or None,
        mtu=attachment.mtu or None,
        state=attachment.state or None,
        operational_status=attachment.operational_status or None,
        cloud_router_ip_address=attachment.cloud_router_ip_address or None,
        customer_router_ip_address=attachment.customer_router_ip_address or None,
        partner_asn=attachment.partner_asn or None,
        partner_metadata=partner_metadata,
        encryption=attachment.encryption or None,
        stack_type=attachment.stack_type or None,
        observed_at=now_iso(),
        source_api="InterconnectAttachmentsClient.aggregated_list",
    )


def list_interconnect_attachments(
    client_factory: ClientFactory, *, project_id: str
) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.interconnect_attachments(),
        "aggregated_list",
        items_field="interconnect_attachments",
        resource_type="interconnect_attachment",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_interconnect_attachment(a, project_id=project_id) for a in raw],
        warnings=warnings,
    )


def normalize_interconnect_location(
    location: compute_v1.InterconnectLocation,
) -> InterconnectLocation:
    return InterconnectLocation(
        self_link=location.self_link or None,
        name=location.name,
        description=location.description or None,
        address=location.address or None,
        city=location.city or None,
        continent=location.continent or None,
        facility_provider=location.facility_provider or None,
        status=location.status or None,
        available_link_types=list(location.available_link_types),
        observed_at=now_iso(),
    )


def list_interconnect_locations(
    client_factory: ClientFactory, *, project_id: str
) -> list[InterconnectLocation]:
    """Interconnect locations are global metadata (every project sees the
    same colocation facilities), but GCP's API still requires a project
    ID in the request -- there is no project-less list call."""
    raw = paginate(
        client_factory.interconnect_locations(),
        "list",
        resource_type="interconnect_location",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_interconnect_location(location) for location in raw]


__all__ = [
    "get_interconnect_diagnostics",
    "list_interconnect_attachments",
    "list_interconnect_locations",
    "list_interconnects",
    "normalize_interconnect",
    "normalize_interconnect_attachment",
    "normalize_interconnect_location",
]
