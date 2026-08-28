"""Service-layer functions for Cloud DNS managed zones and record
summaries.

``google.cloud.dns`` is the legacy, hand-written client library (see
models/dns.py's module docstring) -- its pagination shape
(``google.api_core.page_iterator.HTTPIterator``, whose ``Page`` objects
are directly iterable) differs from every gapic client's ``ListPager``
this codebase otherwise uses, so this module paginates directly rather
than going through ``gcp.pagination``. Every call is still funneled
through ``assert_read_only_operation``/``record_call`` for the same
auditability every other provider library gets.
"""

from __future__ import annotations

from typing import Any

from google.api_core import exceptions as gax

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import now_iso, record_call
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.gcp.pagination import DEFAULT_MAX_ITEMS
from gcp_network_mcp.models.dns import DnsRecordSetSummary, DnsZone
from gcp_network_mcp.security.guardrails import assert_read_only_operation


def _paginate_legacy(pager: Any, *, max_items: int) -> list[Any]:
    items: list[Any] = []
    for page in pager.pages:
        record_call()
        for item in page:
            items.append(item)
            if len(items) >= max_items:
                return items
    return items


def _normalize_zone(zone: Any, *, project_id: str) -> DnsZone:
    return DnsZone(
        name=zone.name,
        project_id=project_id,
        dns_name=zone.dns_name,
        description=zone.description or None,
        zone_id=zone.zone_id or None,
        name_servers=list(zone.name_servers or []),
        name_server_set=zone.name_server_set or None,
        observed_at=now_iso(),
    )


def list_dns_zones(
    client_factory: ClientFactory, *, project_id: str, max_items: int = DEFAULT_MAX_ITEMS
) -> list[DnsZone]:
    assert_read_only_operation("list_zones")
    client = client_factory.dns_client(project_id)
    try:
        raw_zones = _paginate_legacy(client.list_zones(), max_items=max_items)
    except gax.GoogleAPICallError as exc:
        raise translate_gcp_error(exc, resource_type="dns_zone", project_id=project_id) from exc
    return [_normalize_zone(z, project_id=project_id) for z in raw_zones]


def list_dns_zone_records(
    client_factory: ClientFactory,
    *,
    project_id: str,
    zone_name: str,
    max_records: int = 500,
) -> list[DnsRecordSetSummary]:
    assert_read_only_operation("list_resource_record_sets")
    client = client_factory.dns_client(project_id)
    zone = client.zone(zone_name)
    try:
        raw_records = _paginate_legacy(zone.list_resource_record_sets(), max_items=max_records)
    except gax.GoogleAPICallError as exc:
        raise translate_gcp_error(
            exc, resource_type="dns_record_set", project_id=project_id
        ) from exc
    return [
        DnsRecordSetSummary(
            name=r.name, record_type=r.record_type, ttl=r.ttl, rrdatas=list(r.rrdatas)
        )
        for r in raw_records
    ]


__all__ = ["list_dns_zone_records", "list_dns_zones"]
