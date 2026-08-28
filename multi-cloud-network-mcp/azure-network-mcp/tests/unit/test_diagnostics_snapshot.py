from __future__ import annotations

from unittest.mock import MagicMock

from azure.core.exceptions import HttpResponseError
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.diagnostics.snapshot import collect_hybrid_snapshot

# Every resource family collect_hybrid_snapshot fetches, and the exact
# operation-group method name it calls when a resource_group is given --
# some collectors use "list" for a resource-group-scoped call, others
# "list_by_resource_group" (a non-paginated *List wrapper for two of
# them). Kept centralized here so a mismatch is caught in one place
# rather than four near-duplicate test bodies.
_PAGED_METHODS = {
    "virtual_networks": "list",
    "network_security_groups": "list",
    "route_tables": "list",
    "network_interfaces": "list",
    "public_ip_addresses": "list",
    "private_endpoints": "list",
    "virtual_hubs": "list_by_resource_group",
    "vpn_gateways": "list_by_resource_group",
    "virtual_network_gateways": "list",
    "virtual_network_gateway_connections": "list",
    "express_route_circuits": "list",
}
_WRAPPER_METHODS = {
    "express_route_gateways": "list_by_resource_group",
}


def _stub_all_empty(network_client: MagicMock) -> None:
    for attr, method in _PAGED_METHODS.items():
        getattr(getattr(network_client, attr), method).return_value = make_pageable([])
    for attr, method in _WRAPPER_METHODS.items():
        getattr(getattr(network_client, attr), method).return_value = MagicMock(value=[])


def test_collect_hybrid_snapshot_degrades_gracefully_on_partial_rbac(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    """Partial RBAC scenario: one resource family (403 Forbidden) must not
    fail the whole snapshot -- it degrades to an empty list plus a warning."""
    _stub_all_empty(network_client)
    forbidden = HttpResponseError("Forbidden")
    forbidden.status_code = 403
    network_client.network_security_groups.list.side_effect = forbidden

    snapshot = collect_hybrid_snapshot(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    assert snapshot.network_security_groups == []
    assert any(w.resource_type == "network_security_group" for w in snapshot.warnings)
    assert any(w.code == "COLLECTION_FAILED" for w in snapshot.warnings)


def test_collect_hybrid_snapshot_degrades_gracefully_on_unsupported_region(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    """Unsupported region/API version scenario: a resource type not
    available in this region/subscription must not fail the whole
    snapshot."""
    _stub_all_empty(network_client)
    not_found = HttpResponseError("Not Found")
    not_found.status_code = 404
    network_client.virtual_hubs.list_by_resource_group.side_effect = not_found

    snapshot = collect_hybrid_snapshot(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    assert snapshot.virtual_hubs == []
    assert any(w.resource_type == "virtual_hub" for w in snapshot.warnings)


def test_collect_hybrid_snapshot_degrades_gracefully_on_throttling(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    """Throttling scenario: a 429 from one resource family must not fail
    the whole snapshot."""
    _stub_all_empty(network_client)
    throttled = HttpResponseError("Too Many Requests")
    throttled.status_code = 429
    network_client.route_tables.list.side_effect = throttled

    snapshot = collect_hybrid_snapshot(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    assert snapshot.route_tables == []
    assert any(w.resource_type == "route_table" for w in snapshot.warnings)


def test_collect_hybrid_snapshot_succeeds_fully_when_everything_is_available(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _stub_all_empty(network_client)

    snapshot = collect_hybrid_snapshot(
        client_factory, subscription_id=SUBSCRIPTION_ID, resource_group=RESOURCE_GROUP
    )

    assert snapshot.warnings == []
