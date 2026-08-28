"""Service-layer functions for Compute Engine instance connectivity
metadata (network interfaces, not full instance inventory)."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_aggregated
from gcp_network_mcp.models.common import parse_self_link
from gcp_network_mcp.models.instances import (
    AccessConfigSummary,
    InstanceSummary,
    NetworkInterfaceSummary,
)


def _normalize_access_config(access_config: compute_v1.AccessConfig) -> AccessConfigSummary:
    return AccessConfigSummary(
        type_=access_config.type_,
        name=access_config.name or None,
        nat_ip=access_config.nat_i_p or None,
        network_tier=access_config.network_tier or None,
        public_ptr_domain_name=access_config.public_ptr_domain_name or None,
    )


def _normalize_network_interface(interface: compute_v1.NetworkInterface) -> NetworkInterfaceSummary:
    return NetworkInterfaceSummary(
        name=interface.name,
        network_self_link=interface.network or None,
        subnetwork_self_link=interface.subnetwork or None,
        network_ip=interface.network_i_p or None,
        stack_type=interface.stack_type or None,
        nic_type=interface.nic_type or None,
        access_configs=[_normalize_access_config(a) for a in interface.access_configs],
        alias_ip_ranges=[r.ip_cidr_range for r in interface.alias_ip_ranges],
    )


def normalize_instance(instance: compute_v1.Instance, *, project_id: str) -> InstanceSummary:
    parsed = parse_self_link(instance.self_link) if instance.self_link else None
    return InstanceSummary(
        self_link=instance.self_link or None,
        id=str(instance.id) if instance.id else None,
        name=instance.name,
        project_id=project_id,
        zone=parsed.zone if parsed else None,
        status=instance.status or None,
        machine_type=instance.machine_type or None,
        can_ip_forward=instance.can_ip_forward,
        tags=list(instance.tags.items),
        service_accounts=[sa.email for sa in instance.service_accounts if sa.email],
        network_interfaces=[_normalize_network_interface(i) for i in instance.network_interfaces],
        observed_at=now_iso(),
        source_api="InstancesClient.aggregated_list",
    )


def list_instances(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    """List every instance's connectivity metadata across every zone in
    one project."""
    raw, warnings = paginate_aggregated(
        client_factory.instances(),
        "aggregated_list",
        items_field="instances",
        resource_type="instance",
        project_id=project_id,
        project=project_id,
    )
    data = [normalize_instance(i, project_id=project_id) for i in raw]
    return CollectionResult(data=data, warnings=warnings)


__all__ = ["list_instances", "normalize_instance"]
