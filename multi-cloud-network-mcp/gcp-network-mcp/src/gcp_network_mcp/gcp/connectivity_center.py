"""Service-layer functions for Network Connectivity Center (NCC).

Hubs are global resources (parent ``projects/{p}/locations/global``);
spokes are regional but listed across every region in one call via the
``-`` location wildcard (``projects/{p}/locations/-``), the same
convention GCP's REST APIs use elsewhere for "all locations" (e.g.
Compute Engine's zone/region wildcards). Groups, route tables, and
routes are nested under a specific hub/route table and are listed by
that parent's full resource name, not a project ID.

Unlike ``compute_v1`` (whose Discovery-doc-generated client represents
``state``/``type``-shaped fields as plain strings),
``networkconnectivity_v1`` is a newer-style gapic client that represents
every such field as a genuine typed enum (``Hub.state``, ``Spoke.state``,
``Spoke.spoke_type``, ``Route.type_``, ``Hub.policy_mode``, ...) --
verified by introspecting each field's live type. Every normalizer below
therefore reads ``.name`` (never ``field or None``, since an unset enum
is integer ``0``, which is falsy but still a real, named value --
``STATE_UNSPECIFIED``/``SPOKE_TYPE_UNSPECIFIED``/etc. -- not "absent").
"""

from __future__ import annotations

from google.cloud import networkconnectivity_v1 as ncc

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_with_unreachable
from gcp_network_mcp.models.connectivity_center import (
    NccGroup,
    NccHub,
    NccHubStatus,
    NccHubStatusEntry,
    NccPscPropagationStatus,
    NccRoute,
    NccRouteTable,
    NccSpoke,
    NccSpokeReason,
)

_NCC_NEXT_HOP_FIELDS: tuple[str, ...] = (
    "next_hop_vpc_network",
    "next_hop_vpn_tunnel",
    "next_hop_interconnect_attachment",
    "next_hop_router_appliance_instance",
)

# The linked-resource field matching Spoke.spoke_type's enum value, used
# only to extract the linked resource URI(s) -- spoke_type itself always
# comes straight from the SDK's own enum, never inferred.
_SPOKE_TYPE_LINKED_FIELDS: dict[str, str] = {
    "VPC_NETWORK": "linked_vpc_network",
    "VPN_TUNNEL": "linked_vpn_tunnels",
    "INTERCONNECT_ATTACHMENT": "linked_interconnect_attachments",
    "ROUTER_APPLIANCE": "linked_router_appliance_instances",
    "PRODUCER_VPC_NETWORK": "linked_producer_vpc_network",
}


def normalize_hub(hub: ncc.Hub, *, project_id: str) -> NccHub:
    return NccHub(
        name=hub.name,
        unique_id=hub.unique_id or None,
        project_id=project_id,
        description=hub.description or None,
        state=hub.state.name,
        policy_mode=hub.policy_mode.name,
        preset_topology=hub.preset_topology.name,
        export_psc=hub.export_psc,
        route_table_names=list(hub.route_tables),
        spoke_count=(
            sum(c.count for c in hub.spoke_summary.spoke_state_counts)
            if "spoke_summary" in hub
            else None
        ),
        labels=dict(hub.labels),
        observed_at=now_iso(),
    )


def list_hubs(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "list_hubs",
        resource_type="ncc_hub",
        project_id=project_id,
        items_field="hubs",
        parent=f"projects/{project_id}/locations/global",
    )
    return CollectionResult(
        data=[normalize_hub(h, project_id=project_id) for h in raw], warnings=warnings
    )


def _spoke_linked_resource_uris(spoke: ncc.Spoke, *, spoke_type: str) -> list[str]:
    field_name = _SPOKE_TYPE_LINKED_FIELDS.get(spoke_type)
    if field_name is None or field_name not in spoke:
        return []
    value = getattr(spoke, field_name)
    if field_name == "linked_vpc_network":
        return [value.uri] if value.uri else []
    if field_name == "linked_producer_vpc_network":
        return [value.network] if value.network else []
    return list(value.uris)


def normalize_spoke(spoke: ncc.Spoke, *, project_id: str, region: str | None = None) -> NccSpoke:
    spoke_type = spoke.spoke_type.name
    return NccSpoke(
        name=spoke.name,
        unique_id=spoke.unique_id or None,
        project_id=project_id,
        region=region,
        hub=spoke.hub,
        group=spoke.group or None,
        description=spoke.description or None,
        state=spoke.state.name,
        spoke_type=spoke_type,
        linked_resource_uris=_spoke_linked_resource_uris(spoke, spoke_type=spoke_type),
        reasons=[
            NccSpokeReason(code=r.code.name, message=r.message or None) for r in spoke.reasons
        ],
        labels=dict(spoke.labels),
        observed_at=now_iso(),
    )


def list_spokes(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "list_spokes",
        resource_type="ncc_spoke",
        project_id=project_id,
        items_field="spokes",
        parent=f"projects/{project_id}/locations/-",
    )
    return CollectionResult(
        data=[normalize_spoke(s, project_id=project_id) for s in raw], warnings=warnings
    )


def normalize_group(group: ncc.Group, *, project_id: str) -> NccGroup:
    return NccGroup(
        name=group.name,
        uid=group.uid or None,
        hub=_hub_name_from_child(group.name),
        description=group.description or None,
        state=group.state.name,
        # ``Group.auto_accept`` is an ``AutoAccept`` sub-message wrapping
        # ``auto_accept_projects`` (a list of project ids/numbers with
        # auto-accept enabled), not a scalar bool -- passing the
        # sub-message straight into ``NccGroup.auto_accept: bool | None``
        # raised a pydantic ValidationError for any group with auto-accept
        # actually configured. Presence of the sub-message alone doesn't
        # mean auto-accept is *on*, either: an explicitly-set-but-empty
        # ``auto_accept_projects`` still has ``"auto_accept" in group``
        # true, so the emptiness of the list -- not just its presence --
        # decides the normalized bool.
        auto_accept=(
            bool(group.auto_accept.auto_accept_projects) if "auto_accept" in group else None
        ),
        route_table=group.route_table or None,
        labels=dict(group.labels),
        observed_at=now_iso(),
    )


def _hub_name_from_child(child_resource_name: str) -> str:
    """A group/route table/route's own resource name embeds its parent
    hub's name (``.../hubs/{hub}/groups/{group}``) -- extracted here
    rather than requiring every caller to separately track which hub a
    listed child came from."""
    parts = child_resource_name.split("/")
    if "hubs" in parts:
        hub_index = parts.index("hubs")
        return "/".join(parts[: hub_index + 2])
    return child_resource_name


def list_groups(client_factory: ClientFactory, *, hub_name: str, project_id: str) -> list[NccGroup]:
    raw, _ = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "list_groups",
        resource_type="ncc_group",
        project_id=project_id,
        items_field="groups",
        parent=hub_name,
    )
    return [normalize_group(g, project_id=project_id) for g in raw]


def normalize_route_table(route_table: ncc.RouteTable, *, project_id: str) -> NccRouteTable:
    return NccRouteTable(
        name=route_table.name,
        uid=route_table.uid or None,
        hub=_hub_name_from_child(route_table.name),
        description=route_table.description or None,
        state=route_table.state.name,
        labels=dict(route_table.labels),
        observed_at=now_iso(),
    )


def list_route_tables(
    client_factory: ClientFactory, *, hub_name: str, project_id: str
) -> list[NccRouteTable]:
    raw, _ = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "list_route_tables",
        resource_type="ncc_route_table",
        project_id=project_id,
        items_field="route_tables",
        parent=hub_name,
    )
    return [normalize_route_table(rt, project_id=project_id) for rt in raw]


def _ncc_next_hop(route: ncc.Route) -> tuple[str, str | None]:
    """Each ``next_hop_*`` field is a sub-message wrapping a ``uri`` (not
    a flat string, unlike ``compute_v1.Route``'s next-hop fields)."""
    for field_name in _NCC_NEXT_HOP_FIELDS:
        if field_name in route:
            next_hop_type = field_name.removeprefix("next_hop_")
            return next_hop_type, getattr(route, field_name).uri or None
    return "unknown", None


def normalize_ncc_route(route: ncc.Route, *, route_table_name: str) -> NccRoute:
    next_hop_type, next_hop_target = _ncc_next_hop(route)
    return NccRoute(
        name=route.name,
        uid=route.uid or None,
        route_table=route_table_name,
        spoke=route.spoke or None,
        ip_cidr_range=route.ip_cidr_range,
        route_type=route.type_.name,
        state=route.state.name,
        priority=route.priority or None,
        next_hop_type=next_hop_type,
        next_hop_target=next_hop_target,
        labels=dict(route.labels),
        observed_at=now_iso(),
    )


def list_ncc_routes(
    client_factory: ClientFactory, *, route_table_name: str, project_id: str
) -> list[NccRoute]:
    raw, _ = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "list_routes",
        resource_type="ncc_route",
        project_id=project_id,
        items_field="routes",
        parent=route_table_name,
    )
    return [normalize_ncc_route(r, route_table_name=route_table_name) for r in raw]


def get_hub_status(client_factory: ClientFactory, *, hub_name: str) -> NccHubStatus:
    raw, _ = paginate_with_unreachable(
        client_factory.ncc_hub_service(),
        "query_hub_status",
        resource_type="ncc_hub_status",
        items_field="hub_status_entries",
        name=hub_name,
    )
    entries = [
        NccHubStatusEntry(
            count=e.count,
            group_by=e.group_by or None,
            psc_propagation_status=NccPscPropagationStatus(
                source_spoke=e.psc_propagation_status.source_spoke or None,
                source_group=e.psc_propagation_status.source_group or None,
                source_forwarding_rule=e.psc_propagation_status.source_forwarding_rule or None,
                target_spoke=e.psc_propagation_status.target_spoke or None,
                target_group=e.psc_propagation_status.target_group or None,
                code=e.psc_propagation_status.code.name,
                message=e.psc_propagation_status.message or None,
            ),
        )
        for e in raw
    ]
    return NccHubStatus(hub=hub_name, entries=entries, observed_at=now_iso())


__all__ = [
    "get_hub_status",
    "list_groups",
    "list_hubs",
    "list_ncc_routes",
    "list_route_tables",
    "list_spokes",
    "normalize_group",
    "normalize_hub",
    "normalize_ncc_route",
    "normalize_route_table",
    "normalize_spoke",
]
