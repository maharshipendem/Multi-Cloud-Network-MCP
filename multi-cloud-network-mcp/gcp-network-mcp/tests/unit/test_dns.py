from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core import exceptions as gax
from google.cloud import dns
from tests.conftest import PROJECT_ID, FakeLegacyPager

from gcp_network_mcp.exceptions import ResourceNotFoundError
from gcp_network_mcp.gcp.dns import (
    _normalize_zone,
    _paginate_legacy,
    list_dns_zone_records,
    list_dns_zones,
)


def _managed_zone(
    name: str,
    *,
    dns_name: str = "example.com.",
    description: str | None = None,
    zone_id: str | None = None,
    name_servers: list[str] | None = None,
    name_server_set: str | None = None,
) -> dns.ManagedZone:
    """A real ``google.cloud.dns.ManagedZone`` -- the constructor only
    accepts name/dns_name/client/description, so the remaining
    API-populated fields (id/nameServers/nameServerSet) are set directly
    on ``_properties``, exactly as the real client library would after
    deserializing a server response."""
    zone = dns.ManagedZone(name, dns_name=dns_name, client=None)
    # ManagedZone.__init__ defaults `description` to `dns_name` when not
    # given (a real quirk of this SDK's constructor, unlike from_api_repr()
    # -- the path production actually uses -- which leaves it genuinely
    # unset). Set the property directly to bypass that fallback so this
    # helper accurately simulates an API response with no description.
    zone.description = description
    if zone_id is not None:
        zone._properties["id"] = zone_id
    if name_servers is not None:
        zone._properties["nameServers"] = name_servers
    if name_server_set is not None:
        zone._properties["nameServerSet"] = name_server_set
    return zone


def _record_set(
    name: str,
    record_type: str,
    ttl: int,
    rrdatas: list[str],
    *,
    zone: dns.ManagedZone | None = None,
) -> dns.ResourceRecordSet:
    return dns.ResourceRecordSet(name, record_type, ttl, rrdatas, zone=zone or _managed_zone("z"))


# --- _paginate_legacy --------------------------------------------------------


def test_paginate_legacy_flattens_across_pages_by_iterating_pages_directly() -> None:
    """Proves ``_paginate_legacy`` walks ``.pages`` and then iterates each
    page directly (this is the legacy HTTPIterator shape) rather than via
    a ``page.items`` attribute like every gapic pager in this codebase."""
    pager = FakeLegacyPager([["a", "b"], ["c"]])
    items = _paginate_legacy(pager, max_items=100)
    assert items == ["a", "b", "c"]


def test_paginate_legacy_respects_max_items_cap_mid_page() -> None:
    pager = FakeLegacyPager([["a", "b", "c"], ["d", "e"]])
    items = _paginate_legacy(pager, max_items=2)
    assert items == ["a", "b"]


def test_paginate_legacy_handles_no_pages() -> None:
    pager = FakeLegacyPager([])
    assert _paginate_legacy(pager, max_items=100) == []


# --- _normalize_zone ----------------------------------------------------------


def test_normalize_zone_maps_all_fields() -> None:
    zone = _managed_zone(
        "prod-zone",
        dns_name="prod.example.com.",
        description="prod zone",
        zone_id="998877",
        name_servers=["ns-cloud-a1.googledomains.com.", "ns-cloud-a2.googledomains.com."],
        name_server_set="cloud-set",
    )
    normalized = _normalize_zone(zone, project_id=PROJECT_ID)
    assert normalized.name == "prod-zone"
    assert normalized.project_id == PROJECT_ID
    assert normalized.dns_name == "prod.example.com."
    assert normalized.description == "prod zone"
    assert normalized.zone_id == "998877"
    assert normalized.name_servers == [
        "ns-cloud-a1.googledomains.com.",
        "ns-cloud-a2.googledomains.com.",
    ]
    assert normalized.name_server_set == "cloud-set"
    assert normalized.observed_at
    assert normalized.source_api == "google.cloud.dns.Client.list_zones"


def test_normalize_zone_degrades_unset_optional_fields_to_none() -> None:
    zone = _managed_zone("bare-zone", dns_name="bare.example.com.")
    normalized = _normalize_zone(zone, project_id=PROJECT_ID)
    assert normalized.description is None
    assert normalized.zone_id is None
    assert normalized.name_servers == []
    assert normalized.name_server_set is None


# --- list_dns_zones ------------------------------------------------------------


def test_list_dns_zones_flattens_two_pages(client_factory, dns_client: MagicMock) -> None:
    zone1 = _managed_zone("zone-1", zone_id="1")
    zone2 = _managed_zone("zone-2", zone_id="2")
    zone3 = _managed_zone("zone-3", zone_id="3")
    dns_client.list_zones.return_value = FakeLegacyPager([[zone1, zone2], [zone3]])

    zones = list_dns_zones(client_factory, project_id=PROJECT_ID)

    assert [z.name for z in zones] == ["zone-1", "zone-2", "zone-3"]
    assert all(z.project_id == PROJECT_ID for z in zones)


def test_list_dns_zones_empty(client_factory, dns_client: MagicMock) -> None:
    dns_client.list_zones.return_value = FakeLegacyPager([])
    assert list_dns_zones(client_factory, project_id=PROJECT_ID) == []


def test_list_dns_zones_respects_max_items(client_factory, dns_client: MagicMock) -> None:
    zones = [_managed_zone(f"zone-{i}") for i in range(5)]
    dns_client.list_zones.return_value = FakeLegacyPager([zones])

    result = list_dns_zones(client_factory, project_id=PROJECT_ID, max_items=2)

    assert [z.name for z in result] == ["zone-0", "zone-1"]


def test_list_dns_zones_translates_error(client_factory, dns_client: MagicMock) -> None:
    dns_client.list_zones.side_effect = gax.NotFound("no such thing")
    with pytest.raises(ResourceNotFoundError):
        list_dns_zones(client_factory, project_id=PROJECT_ID)


# --- list_dns_zone_records ------------------------------------------------------


def test_list_dns_zone_records_looks_up_zone_and_flattens_records(
    client_factory, dns_client: MagicMock
) -> None:
    zone_mock = MagicMock(name="zone_mock")
    record1 = _record_set("www.example.com.", "A", 300, ["1.2.3.4"])
    record2 = _record_set("example.com.", "MX", 3600, ["10 mail.example.com."])
    zone_mock.list_resource_record_sets.return_value = FakeLegacyPager([[record1], [record2]])
    dns_client.zone.return_value = zone_mock

    records = list_dns_zone_records(client_factory, project_id=PROJECT_ID, zone_name="prod-zone")

    dns_client.zone.assert_called_once_with("prod-zone")
    assert [r.name for r in records] == ["www.example.com.", "example.com."]
    assert records[0].record_type == "A"
    assert records[0].ttl == 300
    assert records[0].rrdatas == ["1.2.3.4"]
    assert records[1].record_type == "MX"


def test_list_dns_zone_records_respects_max_records(client_factory, dns_client: MagicMock) -> None:
    zone_mock = MagicMock(name="zone_mock")
    records = [_record_set(f"r{i}.example.com.", "A", 60, [f"10.0.0.{i}"]) for i in range(4)]
    zone_mock.list_resource_record_sets.return_value = FakeLegacyPager([records])
    dns_client.zone.return_value = zone_mock

    result = list_dns_zone_records(
        client_factory, project_id=PROJECT_ID, zone_name="z", max_records=2
    )
    assert len(result) == 2


def test_list_dns_zone_records_empty(client_factory, dns_client: MagicMock) -> None:
    zone_mock = MagicMock(name="zone_mock")
    zone_mock.list_resource_record_sets.return_value = FakeLegacyPager([])
    dns_client.zone.return_value = zone_mock

    result = list_dns_zone_records(client_factory, project_id=PROJECT_ID, zone_name="z")
    assert result == []


def test_list_dns_zone_records_translates_error(client_factory, dns_client: MagicMock) -> None:
    zone_mock = MagicMock(name="zone_mock")
    zone_mock.list_resource_record_sets.side_effect = gax.Forbidden("nope")
    dns_client.zone.return_value = zone_mock

    from gcp_network_mcp.exceptions import AuthorizationError

    with pytest.raises(AuthorizationError):
        list_dns_zone_records(client_factory, project_id=PROJECT_ID, zone_name="z")
