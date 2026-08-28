"""Normalized models for Network Connectivity Center (NCC): hubs,
spokes, groups, route tables, routes, and propagation status."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NccHub(BaseModel):
    """Normalized entry from ``HubServiceClient.list_hubs``/``get_hub``.
    Hubs are global (project-scoped, no region/zone)."""

    name: str
    unique_id: str | None = None
    project_id: str
    description: str | None = None
    state: str | None = None
    policy_mode: str | None = None
    preset_topology: str | None = None
    export_psc: bool | None = None
    route_table_names: list[str] = Field(default_factory=list)
    # Summed across Hub.spoke_summary.spoke_state_counts.
    spoke_count: int | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: str
    source_api: str = "HubServiceClient.list_hubs"


class NccSpokeReason(BaseModel):
    code: str | None = None
    message: str | None = None


class NccSpoke(BaseModel):
    """Normalized entry from ``HubServiceClient.list_spokes``/``get_spoke``.
    Spokes are regional; ``spoke_type`` reflects which single linked-resource
    field (VPC network, VPN tunnels, Interconnect attachments, router
    appliance instances, producer VPC) is actually populated."""

    name: str
    unique_id: str | None = None
    project_id: str
    region: str | None = None
    hub: str
    group: str | None = None
    description: str | None = None
    state: str | None = None
    spoke_type: str
    linked_resource_uris: list[str] = Field(default_factory=list)
    reasons: list[NccSpokeReason] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: str
    source_api: str = "HubServiceClient.list_spokes"


class NccGroup(BaseModel):
    """Normalized entry from ``HubServiceClient.list_groups``/``get_group``."""

    name: str
    uid: str | None = None
    hub: str
    description: str | None = None
    state: str | None = None
    auto_accept: bool | None = None
    route_table: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: str
    source_api: str = "HubServiceClient.list_groups"


class NccRouteTable(BaseModel):
    """Normalized entry from ``HubServiceClient.list_route_tables``/``get_route_table``."""

    name: str
    uid: str | None = None
    hub: str
    description: str | None = None
    state: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: str
    source_api: str = "HubServiceClient.list_route_tables"


class NccRoute(BaseModel):
    """Normalized entry from ``HubServiceClient.list_routes``/``get_route``.

    ``next_hop_type``/``next_hop_target`` are derived the same way as
    ``models.routes.Route`` -- from whichever ``next_hop_*`` field NCC
    populated (VPC network, VPN tunnel, Interconnect attachment, router
    appliance instance).
    """

    name: str
    uid: str | None = None
    route_table: str
    spoke: str | None = None
    ip_cidr_range: str
    route_type: str | None = None
    state: str | None = None
    priority: int | None = None
    next_hop_type: str
    next_hop_target: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: str
    source_api: str = "HubServiceClient.list_routes"


class NccPscPropagationStatus(BaseModel):
    """One row of a Hub's PSC propagation status, from ``query_hub_status``."""

    source_spoke: str | None = None
    source_group: str | None = None
    source_forwarding_rule: str | None = None
    target_spoke: str | None = None
    target_group: str | None = None
    code: str | None = None
    message: str | None = None


class NccHubStatusEntry(BaseModel):
    """One row of a Hub's PSC propagation status, from ``query_hub_status``.
    ``count`` is the number of propagated PSC connections sharing this
    exact status (1 when the query wasn't grouped)."""

    count: int
    group_by: str | None = None
    psc_propagation_status: NccPscPropagationStatus


class NccHubStatus(BaseModel):
    """Full ``query_hub_status`` result for one hub -- the read-only
    computed propagation/status view, distinct from the hub's own static
    configuration fields on ``NccHub``."""

    hub: str
    entries: list[NccHubStatusEntry] = Field(default_factory=list)
    observed_at: str
    source_api: str = "HubServiceClient.query_hub_status"


__all__ = [
    "NccGroup",
    "NccHub",
    "NccHubStatus",
    "NccHubStatusEntry",
    "NccPscPropagationStatus",
    "NccRoute",
    "NccRouteTable",
    "NccSpoke",
    "NccSpokeReason",
]
