from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from google.cloud import networkconnectivity_v1 as ncc
from tests.conftest import PROJECT_ID, FakePager

from gcp_network_mcp.gcp.connectivity_center import (
    get_hub_status,
    list_groups,
    list_hubs,
    list_ncc_routes,
    list_route_tables,
    list_spokes,
    normalize_group,
    normalize_hub,
    normalize_ncc_route,
    normalize_route_table,
    normalize_spoke,
)

_HUB_NAME = "projects/test-project-1/locations/global/hubs/hub-1"
_ROUTE_TABLE_NAME = f"{_HUB_NAME}/routeTables/rt-1"
_SPOKE_NAME = f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-1"


def _unreachable_pager(
    items: list[Any], *, items_field: str, unreachable: list[str] | None = None
) -> FakePager:
    """Build a fake pager matching ``paginate_with_unreachable``'s expected
    page shape: a single page exposing the items under ``items_field`` and
    any unreachable locations under ``unreachable``.

    ``tests.conftest.make_unreachable_pager`` always exposes its items
    under a fixed ``.items`` attribute, but every NCC list call here reads
    a different, call-specific field (``hubs``, ``spokes``, ``groups``,
    ``route_tables``, ``routes``, ``hub_status_entries``), so a
    locally-parameterized page is used instead.
    """
    page = SimpleNamespace(**{items_field: items}, unreachable=unreachable or [])
    return FakePager([page])


def _hub(**overrides: object) -> ncc.Hub:
    fields: dict[str, object] = {
        "name": _HUB_NAME,
        "unique_id": "1234",
        "description": "primary hub",
        "state": ncc.State.ACTIVE,
        "policy_mode": ncc.PolicyMode.PRESET,
        "preset_topology": ncc.PresetTopology.MESH,
        "export_psc": True,
        "route_tables": [f"{_HUB_NAME}/routeTables/rt-1"],
        "labels": {"env": "prod"},
    }
    fields.update(overrides)
    return ncc.Hub(**fields)


def test_normalize_hub_full_fields() -> None:
    normalized = normalize_hub(_hub(), project_id=PROJECT_ID)

    assert normalized.name == _HUB_NAME
    assert normalized.unique_id == "1234"
    assert normalized.project_id == PROJECT_ID
    assert normalized.description == "primary hub"
    assert normalized.state == "ACTIVE"
    assert normalized.policy_mode == "PRESET"
    assert normalized.preset_topology == "MESH"
    assert normalized.export_psc is True
    assert normalized.route_table_names == [f"{_HUB_NAME}/routeTables/rt-1"]
    assert normalized.labels == {"env": "prod"}
    assert normalized.observed_at


def test_normalize_hub_sums_spoke_state_counts_across_multiple_states() -> None:
    """Regression test: ``Hub.spoke_summary.spoke_state_counts`` is a list
    of ``{state, count}`` entries, one per distinct spoke state -- the
    total spoke count must be the *sum* across every entry, not just the
    first one."""
    spoke_summary = ncc.types.hub.SpokeSummary(
        spoke_state_counts=[
            ncc.types.hub.SpokeSummary.SpokeStateCount(state=ncc.State.ACTIVE, count=3),
            ncc.types.hub.SpokeSummary.SpokeStateCount(state=ncc.State.INACTIVE, count=2),
            ncc.types.hub.SpokeSummary.SpokeStateCount(state=ncc.State.CREATING, count=1),
        ]
    )
    hub = _hub(spoke_summary=spoke_summary)

    normalized = normalize_hub(hub, project_id=PROJECT_ID)

    assert normalized.spoke_count == 6


def test_normalize_hub_without_spoke_summary_has_none_spoke_count() -> None:
    hub = _hub()
    assert "spoke_summary" not in hub

    normalized = normalize_hub(hub, project_id=PROJECT_ID)

    assert normalized.spoke_count is None


def test_list_hubs_empty(client_factory) -> None:
    client_factory.ncc_hub_service().list_hubs.return_value = _unreachable_pager(
        [], items_field="hubs"
    )

    result = list_hubs(client_factory, project_id=PROJECT_ID)

    assert result.data == []
    assert result.warnings == []


def test_list_hubs_surfaces_unreachable_locations_without_crashing(client_factory) -> None:
    client_factory.ncc_hub_service().list_hubs.return_value = _unreachable_pager(
        [_hub()], items_field="hubs", unreachable=["global"]
    )

    result = list_hubs(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    assert result.data[0].name == _HUB_NAME
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "UNREACHABLE"
    assert result.warnings[0].scope == "global"


def _spoke(**overrides: object) -> ncc.Spoke:
    fields: dict[str, object] = {
        "name": _SPOKE_NAME,
        "unique_id": "5678",
        "hub": _HUB_NAME,
        "group": f"{_HUB_NAME}/groups/g-1",
        "description": "a spoke",
        "state": ncc.State.ACTIVE,
        "spoke_type": ncc.SpokeType.VPC_NETWORK,
        "linked_vpc_network": ncc.LinkedVpcNetwork(uri="projects/p/global/networks/vpc-a"),
        "labels": {},
    }
    fields.update(overrides)
    return ncc.Spoke(**fields)


def test_normalize_spoke_vpc_network_extracts_linked_uri() -> None:
    spoke = _spoke(
        reasons=[
            ncc.Spoke.StateReason(
                code=ncc.Spoke.StateReason.Code.PENDING_REVIEW, message="awaiting review"
            )
        ]
    )

    normalized = normalize_spoke(spoke, project_id=PROJECT_ID, region="us-central1")

    assert normalized.name == spoke.name
    assert normalized.region == "us-central1"
    assert normalized.hub == _HUB_NAME
    assert normalized.group == f"{_HUB_NAME}/groups/g-1"
    assert normalized.state == "ACTIVE"
    assert normalized.spoke_type == "VPC_NETWORK"
    assert normalized.linked_resource_uris == ["projects/p/global/networks/vpc-a"]
    assert len(normalized.reasons) == 1
    assert normalized.reasons[0].code == "PENDING_REVIEW"
    assert normalized.reasons[0].message == "awaiting review"


def test_normalize_spoke_vpn_tunnel_extracts_multiple_linked_uris() -> None:
    spoke = _spoke(
        spoke_type=ncc.SpokeType.VPN_TUNNEL,
        linked_vpc_network=None,
        linked_vpn_tunnels=ncc.LinkedVpnTunnels(uris=["uri-a", "uri-b"]),
    )

    normalized = normalize_spoke(spoke, project_id=PROJECT_ID)

    assert normalized.spoke_type == "VPN_TUNNEL"
    assert normalized.linked_resource_uris == ["uri-a", "uri-b"]
    assert normalized.region is None


def test_normalize_spoke_unspecified_type_has_no_linked_uris() -> None:
    spoke = _spoke(spoke_type=ncc.SpokeType.SPOKE_TYPE_UNSPECIFIED, linked_vpc_network=None)

    normalized = normalize_spoke(spoke, project_id=PROJECT_ID)

    assert normalized.spoke_type == "SPOKE_TYPE_UNSPECIFIED"
    assert normalized.linked_resource_uris == []


def test_list_spokes_empty(client_factory) -> None:
    client_factory.ncc_hub_service().list_spokes.return_value = _unreachable_pager(
        [], items_field="spokes"
    )

    result = list_spokes(client_factory, project_id=PROJECT_ID)

    assert result.data == []
    assert result.warnings == []


def test_list_spokes_surfaces_unreachable_locations_without_crashing(client_factory) -> None:
    client_factory.ncc_hub_service().list_spokes.return_value = _unreachable_pager(
        [_spoke()], items_field="spokes", unreachable=["us-central1"]
    )

    result = list_spokes(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "UNREACHABLE"
    assert result.warnings[0].scope == "us-central1"


def _group(**overrides: object) -> ncc.Group:
    fields: dict[str, object] = {
        "name": f"{_HUB_NAME}/groups/g-1",
        "uid": "group-uid",
        "description": "default group",
        "state": ncc.State.ACTIVE,
        "route_table": _ROUTE_TABLE_NAME,
        "labels": {},
    }
    fields.update(overrides)
    return ncc.Group(**fields)


def test_normalize_group_auto_accept_reflects_nonempty_project_list() -> None:
    """Regression test: ``Group.auto_accept`` is an ``AutoAccept``
    sub-message wrapping ``auto_accept_projects`` (a list of project
    ids), not a plain bool -- the normalizer must derive the bool from
    the list's actual contents, not merely from the sub-message's
    presence (a prior bug stored ``"auto_accept" in group`` itself,
    which is ``True`` even when the list is empty)."""
    group = _group(auto_accept=ncc.AutoAccept(auto_accept_projects=["project-a"]))

    normalized = normalize_group(group, project_id=PROJECT_ID)

    assert normalized.auto_accept is True


def test_normalize_group_auto_accept_false_when_project_list_empty() -> None:
    """Same sub-message present but with an empty project list must
    normalize to ``False``, not ``True`` -- proving the field's actual
    content decides the bool, not just whether the sub-message was set."""
    group = _group(auto_accept=ncc.AutoAccept(auto_accept_projects=[]))
    assert "auto_accept" in group  # the sub-message itself is present

    normalized = normalize_group(group, project_id=PROJECT_ID)

    assert normalized.auto_accept is False


def test_normalize_group_auto_accept_none_when_unset() -> None:
    group = _group()
    assert "auto_accept" not in group

    normalized = normalize_group(group, project_id=PROJECT_ID)

    assert normalized.auto_accept is None


def test_normalize_group_derives_hub_from_resource_name() -> None:
    normalized = normalize_group(_group(), project_id=PROJECT_ID)

    assert normalized.hub == _HUB_NAME
    assert normalized.route_table == _ROUTE_TABLE_NAME
    assert normalized.uid == "group-uid"
    assert normalized.state == "ACTIVE"


def test_list_groups_empty(client_factory) -> None:
    client_factory.ncc_hub_service().list_groups.return_value = _unreachable_pager(
        [], items_field="groups"
    )

    groups = list_groups(client_factory, hub_name=_HUB_NAME, project_id=PROJECT_ID)

    assert groups == []


def test_list_groups_does_not_crash_on_unreachable_location(client_factory) -> None:
    client_factory.ncc_hub_service().list_groups.return_value = _unreachable_pager(
        [_group()], items_field="groups", unreachable=["global"]
    )

    groups = list_groups(client_factory, hub_name=_HUB_NAME, project_id=PROJECT_ID)

    assert len(groups) == 1
    assert groups[0].name == f"{_HUB_NAME}/groups/g-1"


def _route_table(**overrides: object) -> ncc.RouteTable:
    fields: dict[str, object] = {
        "name": _ROUTE_TABLE_NAME,
        "uid": "rt-uid",
        "description": "default route table",
        "state": ncc.State.ACTIVE,
        "labels": {},
    }
    fields.update(overrides)
    return ncc.RouteTable(**fields)


def test_normalize_route_table_derives_hub_from_resource_name() -> None:
    normalized = normalize_route_table(_route_table(), project_id=PROJECT_ID)

    assert normalized.name == _ROUTE_TABLE_NAME
    assert normalized.hub == _HUB_NAME
    assert normalized.uid == "rt-uid"
    assert normalized.state == "ACTIVE"


def test_list_route_tables_empty(client_factory) -> None:
    client_factory.ncc_hub_service().list_route_tables.return_value = _unreachable_pager(
        [], items_field="route_tables"
    )

    route_tables = list_route_tables(client_factory, hub_name=_HUB_NAME, project_id=PROJECT_ID)

    assert route_tables == []


def test_list_route_tables_does_not_crash_on_unreachable_location(client_factory) -> None:
    client_factory.ncc_hub_service().list_route_tables.return_value = _unreachable_pager(
        [_route_table()], items_field="route_tables", unreachable=["global"]
    )

    route_tables = list_route_tables(client_factory, hub_name=_HUB_NAME, project_id=PROJECT_ID)

    assert len(route_tables) == 1
    assert route_tables[0].name == _ROUTE_TABLE_NAME


def _ncc_route(**overrides: object) -> ncc.Route:
    fields: dict[str, object] = {
        "name": f"{_ROUTE_TABLE_NAME}/routes/route-1",
        "uid": "route-uid",
        "ip_cidr_range": "10.0.0.0/24",
        "type_": ncc.RouteType.VPC_PRIMARY_SUBNET,
        "state": ncc.State.ACTIVE,
        "priority": 100,
        "labels": {},
    }
    fields.update(overrides)
    return ncc.Route(**fields)


def test_normalize_ncc_route_extracts_next_hop_uri_from_submessage() -> None:
    """Regression test: each ``next_hop_*`` field on an NCC ``Route`` is a
    sub-message wrapping a ``uri`` attribute (unlike ``compute_v1.Route``,
    whose next-hop fields are flat strings) -- the normalizer must read
    ``.uri`` off the sub-message, not treat the field itself as the
    target string."""
    route = _ncc_route(
        next_hop_vpc_network=ncc.NextHopVpcNetwork(uri="projects/p/global/networks/vpc-a")
    )

    normalized = normalize_ncc_route(route, route_table_name=_ROUTE_TABLE_NAME)

    assert normalized.route_table == _ROUTE_TABLE_NAME
    assert normalized.ip_cidr_range == "10.0.0.0/24"
    assert normalized.route_type == "VPC_PRIMARY_SUBNET"
    assert normalized.state == "ACTIVE"
    assert normalized.priority == 100
    assert normalized.next_hop_type == "vpc_network"
    assert normalized.next_hop_target == "projects/p/global/networks/vpc-a"


def test_normalize_ncc_route_no_next_hop_set_does_not_crash() -> None:
    route = _ncc_route()

    normalized = normalize_ncc_route(route, route_table_name=_ROUTE_TABLE_NAME)

    assert normalized.next_hop_type == "unknown"
    assert normalized.next_hop_target is None


def test_list_ncc_routes_empty(client_factory) -> None:
    client_factory.ncc_hub_service().list_routes.return_value = _unreachable_pager(
        [], items_field="routes"
    )

    routes = list_ncc_routes(
        client_factory, route_table_name=_ROUTE_TABLE_NAME, project_id=PROJECT_ID
    )

    assert routes == []


def test_list_ncc_routes_does_not_crash_on_unreachable_location(client_factory) -> None:
    client_factory.ncc_hub_service().list_routes.return_value = _unreachable_pager(
        [_ncc_route()], items_field="routes", unreachable=["global"]
    )

    routes = list_ncc_routes(
        client_factory, route_table_name=_ROUTE_TABLE_NAME, project_id=PROJECT_ID
    )

    assert len(routes) == 1
    assert routes[0].name == f"{_ROUTE_TABLE_NAME}/routes/route-1"


def test_get_hub_status_reads_falsy_but_named_enum_via_name_attribute(client_factory) -> None:
    """Regression test: ``PscPropagationStatus.code`` is a proto-plus enum
    whose unset/zero value (``CODE_UNSPECIFIED``) is a real, named member
    -- but is Python-falsy (``int(CODE_UNSPECIFIED) == 0``). The
    normalizer must read ``.name`` unconditionally; a naive
    ``x.name if x else None`` guard would wrongly collapse this real,
    named value to ``None``."""
    entry = ncc.HubStatusEntry(
        count=1,
        group_by="",
        psc_propagation_status=ncc.PscPropagationStatus(
            code=ncc.PscPropagationStatus.Code.CODE_UNSPECIFIED
        ),
    )
    client_factory.ncc_hub_service().query_hub_status.return_value = _unreachable_pager(
        [entry], items_field="hub_status_entries"
    )

    status = get_hub_status(client_factory, hub_name=_HUB_NAME)

    assert status.hub == _HUB_NAME
    assert len(status.entries) == 1
    assert status.entries[0].psc_propagation_status.code == "CODE_UNSPECIFIED"


def test_get_hub_status_one_row_per_status_with_single_propagation_status(client_factory) -> None:
    entry = ncc.HubStatusEntry(
        count=4,
        group_by="code",
        psc_propagation_status=ncc.PscPropagationStatus(
            source_spoke=_SPOKE_NAME,
            source_group=f"{_HUB_NAME}/groups/g-1",
            target_spoke=f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-2",
            code=ncc.PscPropagationStatus.Code.READY,
            message="",
        ),
    )
    client_factory.ncc_hub_service().query_hub_status.return_value = _unreachable_pager(
        [entry], items_field="hub_status_entries"
    )

    status = get_hub_status(client_factory, hub_name=_HUB_NAME)

    assert len(status.entries) == 1
    row = status.entries[0]
    assert row.count == 4
    assert row.group_by == "code"
    assert row.psc_propagation_status.code == "READY"
    assert row.psc_propagation_status.source_spoke == _SPOKE_NAME
    assert row.psc_propagation_status.message is None


def test_get_hub_status_empty(client_factory) -> None:
    client_factory.ncc_hub_service().query_hub_status.return_value = _unreachable_pager(
        [], items_field="hub_status_entries"
    )

    status = get_hub_status(client_factory, hub_name=_HUB_NAME)

    assert status.hub == _HUB_NAME
    assert status.entries == []


def test_get_hub_status_does_not_crash_on_unreachable_location(client_factory) -> None:
    entry = ncc.HubStatusEntry(
        count=1,
        psc_propagation_status=ncc.PscPropagationStatus(
            code=ncc.PscPropagationStatus.Code.PROPAGATING
        ),
    )
    client_factory.ncc_hub_service().query_hub_status.return_value = _unreachable_pager(
        [entry], items_field="hub_status_entries", unreachable=["global"]
    )

    status = get_hub_status(client_factory, hub_name=_HUB_NAME)

    assert len(status.entries) == 1
    assert status.entries[0].psc_propagation_status.code == "PROPAGATING"
