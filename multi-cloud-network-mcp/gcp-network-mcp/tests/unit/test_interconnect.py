from __future__ import annotations

import inspect
import typing

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.gcp.interconnect import (
    get_interconnect_diagnostics,
    list_interconnect_attachments,
    list_interconnect_locations,
    list_interconnects,
    normalize_interconnect,
    normalize_interconnect_attachment,
    normalize_interconnect_location,
)
from gcp_network_mcp.models.interconnect import InterconnectAttachment

_INTERCONNECT_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/"
    "interconnects/interconnect-1"
)
_ATTACHMENT_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
    "us-central1/interconnectAttachments/attachment-1"
)


def _interconnect() -> compute_v1.Interconnect:
    return compute_v1.Interconnect(
        name="interconnect-1",
        self_link=_INTERCONNECT_SELF_LINK,
        interconnect_type="DEDICATED",
        link_type="LINK_TYPE_ETHERNET_10G_LR",
        location=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/"
            "interconnectLocations/loc-1"
        ),
        customer_name="Acme Corp",
        admin_enabled=True,
        operational_status="OS_ACTIVE",
        state="ACTIVE",
        provisioned_link_count=1,
        requested_link_count=1,
        google_ip_address="8.8.8.8",
        peer_ip_address="8.8.4.4",
        circuit_infos=[
            compute_v1.InterconnectCircuitInfo(
                google_circuit_id="circuit-1",
                google_demarc_id="demarc-1",
                customer_demarc_id="cust-demarc-1",
            )
        ],
        interconnect_attachments=[_ATTACHMENT_SELF_LINK],
    )


def _attachment(**overrides: object) -> compute_v1.InterconnectAttachment:
    fields = {
        "name": "attachment-1",
        "self_link": _ATTACHMENT_SELF_LINK,
        "interconnect": _INTERCONNECT_SELF_LINK,
        "router": (
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/routers/router-1"
        ),
        "type_": "DEDICATED",
        "edge_availability_domain": "AVAILABILITY_DOMAIN_1",
        "bandwidth": "BPS_1G",
        "vlan_tag8021q": 100,
        "mtu": 1500,
        "state": "ACTIVE",
        "operational_status": "OS_ACTIVE",
        "cloud_router_ip_address": "169.254.0.1",
        "customer_router_ip_address": "169.254.0.2",
        "encryption": "NONE",
        "stack_type": "IPV4_ONLY",
    }
    fields.update(overrides)
    return compute_v1.InterconnectAttachment(**fields)


def _interconnect_location() -> compute_v1.InterconnectLocation:
    return compute_v1.InterconnectLocation(
        name="loc-1",
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/"
            "interconnectLocations/loc-1"
        ),
        description="Example colocation facility",
        address="123 Main St",
        city="Council Bluffs",
        continent="NORTH_AMERICA",
        facility_provider="Equinix",
        status="AVAILABLE",
        available_link_types=["LINK_TYPE_ETHERNET_10G_LR"],
    )


def test_normalize_interconnect_happy_path() -> None:
    normalized = normalize_interconnect(_interconnect(), project_id=PROJECT_ID)
    assert normalized.name == "interconnect-1"
    assert normalized.interconnect_type == "DEDICATED"
    assert normalized.link_type == "LINK_TYPE_ETHERNET_10G_LR"
    assert normalized.customer_name == "Acme Corp"
    assert normalized.admin_enabled is True
    assert normalized.operational_status == "OS_ACTIVE"
    assert normalized.state == "ACTIVE"
    assert normalized.provisioned_link_count == 1
    assert normalized.requested_link_count == 1
    assert normalized.google_ip_address == "8.8.8.8"
    assert normalized.peer_ip_address == "8.8.4.4"
    assert len(normalized.circuit_infos) == 1
    assert normalized.circuit_infos[0].google_circuit_id == "circuit-1"
    assert normalized.interconnect_attachment_self_links == [_ATTACHMENT_SELF_LINK]
    # Interconnect is a global resource -- no region/zone.
    assert normalized.region is None
    assert normalized.zone is None


def test_list_interconnects_uses_plain_list(client_factory) -> None:
    client_factory.interconnects().list.return_value = make_pager([_interconnect()])
    result = list_interconnects(client_factory, project_id=PROJECT_ID)
    assert len(result) == 1
    assert result[0].name == "interconnect-1"


def test_list_interconnects_empty(client_factory) -> None:
    client_factory.interconnects().list.return_value = make_pager([])
    result = list_interconnects(client_factory, project_id=PROJECT_ID)
    assert result == []


def test_get_interconnect_diagnostics_extracts_optical_power(client_factory) -> None:
    """Regression test: `receiving_optical_power`/`transmitting_optical_power`
    on each link status are sub-messages (`InterconnectDiagnosticsLinkOpticalPower`)
    wrapping a numeric `.value`, not flat floats. The normalizer must read
    `.value` off the sub-message, not crash or silently drop it."""
    raw_response = compute_v1.InterconnectsGetDiagnosticsResponse(
        result=compute_v1.InterconnectDiagnostics(
            mac_address="00:1a:2b:3c:4d:5e",
            bundle_operational_status="OS_ACTIVE",
            bundle_aggregation_type="LACP_ACTIVE",
            links=[
                compute_v1.InterconnectDiagnosticsLinkStatus(
                    circuit_id="circuit-1",
                    operational_status="OS_ACTIVE",
                    google_demarc="demarc-1",
                    receiving_optical_power=compute_v1.InterconnectDiagnosticsLinkOpticalPower(
                        value=-3.5, state="OK"
                    ),
                    transmitting_optical_power=compute_v1.InterconnectDiagnosticsLinkOpticalPower(
                        value=-2.5, state="OK"
                    ),
                )
            ],
        )
    )
    client_factory.interconnects().get_diagnostics.return_value = raw_response

    diagnostics = get_interconnect_diagnostics(
        client_factory, project_id=PROJECT_ID, interconnect_name="interconnect-1"
    )

    assert diagnostics.interconnect_self_link == _INTERCONNECT_SELF_LINK
    assert diagnostics.mac_address == "00:1a:2b:3c:4d:5e"
    assert diagnostics.bundle_operational_status == "OS_ACTIVE"
    assert len(diagnostics.links) == 1
    link = diagnostics.links[0]
    assert link.circuit_id == "circuit-1"
    assert link.receiving_optical_power_dbm == -3.5
    assert link.transmitting_optical_power_dbm == -2.5


def test_get_interconnect_diagnostics_without_optical_power_is_none(client_factory) -> None:
    raw_response = compute_v1.InterconnectsGetDiagnosticsResponse(
        result=compute_v1.InterconnectDiagnostics(
            links=[
                compute_v1.InterconnectDiagnosticsLinkStatus(
                    circuit_id="circuit-2",
                    operational_status="OS_ACTIVE",
                )
            ]
        )
    )
    client_factory.interconnects().get_diagnostics.return_value = raw_response

    diagnostics = get_interconnect_diagnostics(
        client_factory, project_id=PROJECT_ID, interconnect_name="interconnect-1"
    )
    link = diagnostics.links[0]
    assert link.receiving_optical_power_dbm is None
    assert link.transmitting_optical_power_dbm is None


def test_normalize_interconnect_attachment_happy_path() -> None:
    normalized = normalize_interconnect_attachment(_attachment(), project_id=PROJECT_ID)
    assert normalized.name == "attachment-1"
    assert normalized.region == "us-central1"
    assert normalized.interconnect_self_link == _INTERCONNECT_SELF_LINK
    assert normalized.router_self_link.endswith("/routers/router-1")
    assert normalized.attachment_type == "DEDICATED"
    assert normalized.edge_availability_domain == "AVAILABILITY_DOMAIN_1"
    assert normalized.bandwidth == "BPS_1G"
    assert normalized.vlan_tag8021q == 100
    assert normalized.mtu == 1500
    assert normalized.state == "ACTIVE"
    assert normalized.operational_status == "OS_ACTIVE"
    assert normalized.cloud_router_ip_address == "169.254.0.1"
    assert normalized.customer_router_ip_address == "169.254.0.2"
    assert normalized.encryption == "NONE"
    assert normalized.stack_type == "IPV4_ONLY"
    assert normalized.partner_metadata is None
    assert normalized.redacted is True


def test_normalize_interconnect_attachment_with_partner_metadata() -> None:
    raw = _attachment(
        partner_metadata=compute_v1.InterconnectAttachmentPartnerMetadata(
            partner_name="Partner Co",
            interconnect_name="partner-interconnect-1",
            portal_url="https://partner.example.com/portal",
        )
    )
    normalized = normalize_interconnect_attachment(raw, project_id=PROJECT_ID)
    assert normalized.partner_metadata is not None
    assert normalized.partner_metadata.partner_name == "Partner Co"
    assert normalized.partner_metadata.interconnect_name == "partner-interconnect-1"
    assert normalized.partner_metadata.portal_url == "https://partner.example.com/portal"


def test_normalize_interconnect_attachment_never_leaks_pairing_key() -> None:
    """Regression test: InterconnectAttachment's raw SDK type carries
    `pairing_key` (the Partner Interconnect provisioning secret). The
    normalizer must never read it -- prove it by literal string search
    over the full repr of the normalized model."""
    raw = _attachment(pairing_key="secret-pairing-key-123")
    normalized = normalize_interconnect_attachment(raw, project_id=PROJECT_ID)
    assert "secret-pairing-key-123" not in str(normalized)
    assert "pairing_key" not in InterconnectAttachment.model_fields
    assert normalized.redacted is True


def test_interconnect_attachment_model_has_no_network_self_link_field() -> None:
    """Regression test: InterconnectAttachment's normalized model must not
    carry a `network_self_link` field -- the raw SDK type has no direct
    `network` field, only `router` (a network is resolved by following
    Router.network separately). Guards against this being silently
    reintroduced with an incorrect direct mapping."""
    assert "network_self_link" not in InterconnectAttachment.model_fields


def test_list_interconnect_attachments_aggregates_across_regions(client_factory) -> None:
    client_factory.interconnect_attachments().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [_attachment()]}, items_field="interconnect_attachments"
    )
    result = list_interconnect_attachments(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].name == "attachment-1"


def test_list_interconnect_attachments_empty(client_factory) -> None:
    client_factory.interconnect_attachments().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="interconnect_attachments"
    )
    result = list_interconnect_attachments(client_factory, project_id=PROJECT_ID)
    assert result.data == []
    assert result.warnings == []


def test_normalize_interconnect_location_happy_path() -> None:
    normalized = normalize_interconnect_location(_interconnect_location())
    assert normalized.name == "loc-1"
    assert normalized.description == "Example colocation facility"
    assert normalized.address == "123 Main St"
    assert normalized.city == "Council Bluffs"
    assert normalized.continent == "NORTH_AMERICA"
    assert normalized.facility_provider == "Equinix"
    assert normalized.status == "AVAILABLE"
    assert normalized.available_link_types == ["LINK_TYPE_ETHERNET_10G_LR"]


def test_list_interconnect_locations_uses_plain_list(client_factory) -> None:
    client_factory.interconnect_locations().list.return_value = make_pager(
        [_interconnect_location()]
    )
    result = list_interconnect_locations(client_factory, project_id=PROJECT_ID)
    assert len(result) == 1
    assert result[0].name == "loc-1"


def test_list_interconnect_locations_empty(client_factory) -> None:
    client_factory.interconnect_locations().list.return_value = make_pager([])
    result = list_interconnect_locations(client_factory, project_id=PROJECT_ID)
    assert result == []


def test_list_interconnect_locations_requires_real_project_id_and_passes_it_through(
    client_factory,
) -> None:
    """Regression test: interconnect locations are global metadata (every
    project sees the same colocation facilities), but GCP's API still
    requires a real project ID in the request -- there is no project-less
    list call. Confirm the function signature requires `project_id: str`
    (no default, so a caller can't omit it or pass a placeholder like
    "_") and that the value given is passed through to the underlying
    `list` call's kwargs."""
    signature = inspect.signature(list_interconnect_locations)
    project_id_param = signature.parameters["project_id"]
    type_hints = typing.get_type_hints(list_interconnect_locations)
    assert type_hints["project_id"] is str
    assert project_id_param.default is inspect.Parameter.empty

    client_factory.interconnect_locations().list.return_value = make_pager([])
    list_interconnect_locations(client_factory, project_id=PROJECT_ID)
    _, call_kwargs = client_factory.interconnect_locations().list.call_args
    assert call_kwargs["project"] == PROJECT_ID
