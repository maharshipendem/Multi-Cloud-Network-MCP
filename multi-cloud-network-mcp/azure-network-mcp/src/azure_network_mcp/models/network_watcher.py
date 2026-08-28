"""Normalized models for Network Watcher: topology, existing connection
monitors, and flow log configuration (VNet and NSG flow logs share one
unified API in the current Azure SDK, keyed by the target resource ID).

This module never creates, starts, or stops a Network Watcher, connection
monitor, troubleshooter, or packet capture -- only ``get``/``list`` calls
against resources that already exist. See docs/security.md#guardrails.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource


class NetworkWatcher(AzureResource):
    """Normalized entry from NetworkWatchersOperations.list/list_all/get."""


class TopologyAssociation(BaseModel):
    name: str | None = None
    associated_resource_id: str | None = None
    association_type: str | None = None


class TopologyResource(BaseModel):
    name: str | None = None
    resource_id: str | None = None
    location: str | None = None
    associations: list[TopologyAssociation] = Field(default_factory=list)


class AzureNetworkTopology(BaseModel):
    """Azure's own resource-association graph for one resource group, from
    NetworkWatchersOperations.get_topology -- a different, coarser view
    than this server's own ``azure_get_vnet_topology`` (which is
    self-computed and single-VNet-scoped with typed nodes/edges/evidence).
    This is Azure's native topology, surfaced as-is."""

    resource_group: str
    created_at: str | None = None
    last_modified_at: str | None = None
    resources: list[TopologyResource] = Field(default_factory=list)


class ConnectionMonitorEndpointSummary(BaseModel):
    name: str | None = None
    resource_id: str | None = None
    address: str | None = None


class ConnectionMonitor(AzureResource):
    """Normalized entry from ConnectionMonitorsOperations.list/get -- the
    configuration and last-known monitoring status of an *existing*
    connection monitor. This module never creates, starts, or stops one;
    per-check time-series data points require Azure Monitor Logs (Log
    Analytics), out of scope for this milestone -- see
    docs/limitations.md."""

    network_watcher_name: str | None = None
    monitoring_status: str | None = None
    start_time: str | None = None
    auto_start: bool | None = None
    monitoring_interval_in_seconds: int | None = None
    endpoints: list[ConnectionMonitorEndpointSummary] = Field(default_factory=list)


class FlowLogConfig(AzureResource):
    """Normalized entry from FlowLogsOperations.list/get -- configuration
    for a VNet or NSG flow log (the current API unifies both under one
    resource type, keyed by ``target_resource_id``). Configuration and
    delivery metadata only -- never log record contents; see
    docs/security.md#redaction."""

    network_watcher_name: str | None = None
    target_resource_id: str | None = None
    enabled: bool | None = None
    storage_account_id: str | None = None
    retention_days: int | None = None
    format_type: str | None = None
    format_version: int | None = None
    traffic_analytics_enabled: bool | None = None


__all__ = [
    "AzureNetworkTopology",
    "ConnectionMonitor",
    "ConnectionMonitorEndpointSummary",
    "FlowLogConfig",
    "NetworkWatcher",
    "TopologyAssociation",
    "TopologyResource",
]
