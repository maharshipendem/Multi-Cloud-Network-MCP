"""ARM service layer: Network Watcher topology, existing connection
monitors, and flow log configuration.

This module never creates, starts, or stops a Network Watcher, connection
monitor, troubleshooter, or packet capture -- every function here calls
only ``get``/``list`` operations against resources that already exist.
``get_network_topology`` calls ``NetworkWatchersOperations.get_topology``,
which is a POST-shaped read (it takes a request body scoping the query to
one resource group) but performs no mutation -- it passes this codebase's
``get``-prefix guardrail rule without needing an exception.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure.mgmt.network.models import TopologyParameters

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_watcher import (
    AzureNetworkTopology,
    ConnectionMonitor,
    ConnectionMonitorEndpointSummary,
    FlowLogConfig,
    NetworkWatcher,
    TopologyAssociation,
    TopologyResource,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_network_watchers(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[NetworkWatcher]:
    """Call NetworkWatchersOperations.list (one resource group) or
    .list_all (whole subscription)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.network_watchers,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.network_watchers, "list_all", max_items=settings.max_page_results)

    result = []
    for watcher in raw:
        parsed = parse_resource_id(watcher.id)
        result.append(
            NetworkWatcher(
                resource_id=watcher.id,
                name=watcher.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=watcher.location,
                provisioning_state=getattr(watcher, "provisioning_state", None),
                tags=normalize_tags(watcher.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/networkWatchers",
            )
        )
    return result


def get_network_topology(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_watcher_name: str,
    target_resource_group: str,
) -> AzureNetworkTopology:
    """Call NetworkWatchersOperations.get_topology, scoped to
    ``target_resource_group`` -- Azure's own resource-association graph,
    distinct from this server's self-computed ``azure_get_vnet_topology``."""
    client = client_factory.get_network_client(subscription_id)
    result = call_readonly(
        client.network_watchers,
        "get_topology",
        resource_group_name=resource_group,
        network_watcher_name=network_watcher_name,
        parameters=TopologyParameters(target_resource_group_name=target_resource_group),
    )
    return AzureNetworkTopology(
        resource_group=target_resource_group,
        created_at=(
            result.created_date_time.isoformat()
            if getattr(result, "created_date_time", None)
            else None
        ),
        last_modified_at=(
            result.last_modified.isoformat() if getattr(result, "last_modified", None) else None
        ),
        resources=[
            TopologyResource(
                name=r.name,
                resource_id=r.id,
                location=r.location,
                associations=[
                    TopologyAssociation(
                        name=a.name,
                        associated_resource_id=getattr(a, "resource_id", None),
                        association_type=getattr(a, "association_type", None),
                    )
                    for a in (r.associations or [])
                ],
            )
            for r in (result.resources or [])
        ],
    )


def list_connection_monitors(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_watcher_name: str,
) -> list[ConnectionMonitor]:
    """Call ConnectionMonitorsOperations.list -- configuration and
    last-known status of existing connection monitors. Never creates,
    starts, or stops one."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.connection_monitors,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        network_watcher_name=network_watcher_name,
    )
    result = []
    for cm in raw:
        parsed = parse_resource_id(cm.id) if getattr(cm, "id", None) else None
        result.append(
            ConnectionMonitor(
                resource_id=cm.id or "",
                name=cm.name,
                subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
                resource_group=parsed.resource_group if parsed else resource_group,
                location=getattr(cm, "location", None),
                provisioning_state=getattr(cm, "provisioning_state", None),
                tags=normalize_tags(getattr(cm, "tags", None)),
                observed_at=observed_at,
                source_api="Microsoft.Network/networkWatchers/connectionMonitors",
                network_watcher_name=network_watcher_name,
                monitoring_status=getattr(cm, "monitoring_status", None),
                start_time=(cm.start_time.isoformat() if getattr(cm, "start_time", None) else None),
                auto_start=getattr(cm, "auto_start", None),
                monitoring_interval_in_seconds=getattr(cm, "monitoring_interval_in_seconds", None),
                endpoints=[
                    ConnectionMonitorEndpointSummary(
                        name=ep.name,
                        resource_id=getattr(ep, "resource_id", None),
                        address=getattr(ep, "address", None),
                    )
                    for ep in (getattr(cm, "endpoints", None) or [])
                ],
            )
        )
    return result


def list_flow_logs(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_watcher_name: str,
) -> list[FlowLogConfig]:
    """Call FlowLogsOperations.list -- configuration and delivery
    metadata for VNet and NSG flow logs (unified under one resource type
    in the current API), never log record contents."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.flow_logs,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        network_watcher_name=network_watcher_name,
    )
    result = []
    for fl in raw:
        parsed = parse_resource_id(fl.id)
        retention = getattr(fl, "retention_policy", None)
        fmt = getattr(fl, "format", None)
        result.append(
            FlowLogConfig(
                resource_id=fl.id,
                name=fl.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=fl.location,
                provisioning_state=getattr(fl, "provisioning_state", None),
                tags=normalize_tags(fl.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/networkWatchers/flowLogs",
                network_watcher_name=network_watcher_name,
                target_resource_id=getattr(fl, "target_resource_id", None),
                enabled=getattr(fl, "enabled", None),
                storage_account_id=getattr(fl, "storage_id", None),
                retention_days=(getattr(retention, "days", None) if retention else None),
                format_type=(getattr(fmt, "type", None) if fmt else None),
                format_version=(getattr(fmt, "version", None) if fmt else None),
                traffic_analytics_enabled=(
                    getattr(
                        fl.flow_analytics_configuration.network_watcher_flow_analytics_configuration,
                        "enabled",
                        None,
                    )
                    if getattr(fl, "flow_analytics_configuration", None)
                    and getattr(
                        fl.flow_analytics_configuration,
                        "network_watcher_flow_analytics_configuration",
                        None,
                    )
                    else None
                ),
            )
        )
    return result


__all__ = [
    "get_network_topology",
    "list_connection_monitors",
    "list_flow_logs",
    "list_network_watchers",
]
