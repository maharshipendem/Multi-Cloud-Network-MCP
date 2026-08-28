"""Service-layer function for VPC Flow Logs *configuration* -- never log
records/content. Lists project-level configs
(``projects/{project}/locations/global``); organization-level configs
are out of this milestone's tool surface (project-scoped inventory only,
matching every other tool)."""

from __future__ import annotations

from google.cloud import network_management_v1 as nm

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_with_unreachable
from gcp_network_mcp.models.flow_logs import VpcFlowLogsConfigSummary

_TARGET_FIELDS: tuple[str, ...] = ("subnet", "interconnect_attachment", "vpn_tunnel")


def _target(config: nm.VpcFlowLogsConfig) -> tuple[str, str | None]:
    for field_name in _TARGET_FIELDS:
        if field_name in config:
            return field_name, str(getattr(config, field_name))
    return "unknown", None


def normalize_flow_logs_config(config: nm.VpcFlowLogsConfig) -> VpcFlowLogsConfigSummary:
    target_type, target_resource = _target(config)
    return VpcFlowLogsConfigSummary(
        name=config.name,
        state=config.state.name,
        target_type=target_type,
        target_resource=target_resource,
        aggregation_interval=config.aggregation_interval.name
        if "aggregation_interval" in config
        else None,
        flow_sampling=config.flow_sampling or None,
        filter_expr=config.filter_expr or None,
        description=config.description or None,
        cross_project_metadata=config.cross_project_metadata.name
        if "cross_project_metadata" in config
        else None,
        observed_at=now_iso(),
    )


def list_vpc_flow_logs_configs(
    client_factory: ClientFactory, *, project_id: str
) -> CollectionResult:
    raw, warnings = paginate_with_unreachable(
        client_factory.vpc_flow_logs(),
        "list_vpc_flow_logs_configs",
        resource_type="vpc_flow_logs_config",
        project_id=project_id,
        items_field="vpc_flow_logs_configs",
        parent=f"projects/{project_id}/locations/global",
    )
    return CollectionResult(data=[normalize_flow_logs_config(c) for c in raw], warnings=warnings)


__all__ = ["list_vpc_flow_logs_configs", "normalize_flow_logs_config"]
