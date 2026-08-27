"""AWS service layer: assembles ``aws_get_network_health``'s combined
report -- degraded-resource findings (pure, from ``diagnostics.consistency``),
Flow Log configuration coverage, opt-in bounded CloudWatch metrics, opt-in
existing Reachability Analyzer results, and opt-in recent CloudTrail
network-configuration events.

This module never enables Flow Logs, never creates a Reachability
Analyzer path/analysis, and never changes any alarm/log configuration --
every signal here is a read of state that already exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.cloudtrail import lookup_network_config_events
from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.flowlogs import list_flow_logs
from aws_cloudops_mcp.aws.network_insights import list_network_insights_analyses
from aws_cloudops_mcp.aws.network_metrics import get_known_metrics_for_resource
from aws_cloudops_mcp.aws.snapshot import collect_network_snapshot
from aws_cloudops_mcp.diagnostics.consistency import check_degraded_resource_states
from aws_cloudops_mcp.models.network_health import NetworkHealthReport

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def get_network_health(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_ids: list[str] | None = None,
    include_metrics: bool = False,
    include_reachability_analyses: bool = False,
    include_recent_changes: bool = False,
) -> NetworkHealthReport:
    snapshot = collect_network_snapshot(
        client_factory, region=region, vpc_ids=vpc_ids, include_vpn=True
    )
    degraded = check_degraded_resource_states(snapshot)

    flow_logs = list_flow_logs(client_factory, region=region)
    logged_resource_ids = {fl.resource_id for fl in flow_logs}
    vpcs_without_flow_logs = [
        v.vpc_id for v in snapshot.vpcs if v.vpc_id not in logged_resource_ids
    ]

    limitations: list[str] = []

    metrics = []
    if include_metrics:
        settings = client_factory.settings
        fanout_budget = settings.max_fanout_calls
        for nat in snapshot.nat_gateways:
            if fanout_budget <= 0:
                limitations.append(
                    f"skipped metrics for {nat.nat_gateway_id}: max_fanout_calls "
                    f"({settings.max_fanout_calls}) reached"
                )
                continue
            metrics.extend(
                get_known_metrics_for_resource(
                    client_factory,
                    region=region,
                    resource_type="nat_gateway",
                    resource_id=nat.nat_gateway_id,
                )
            )
            fanout_budget -= 1

    unhealthy_analyses = []
    if include_reachability_analyses:
        analyses = list_network_insights_analyses(client_factory, region=region)
        unhealthy_analyses = [
            a for a in analyses if a.network_path_found is False or a.status == "failed"
        ]

    recent_changes = []
    if include_recent_changes:
        recent_changes = lookup_network_config_events(client_factory, region=region)

    return NetworkHealthReport(
        region=region,
        collected_at=now_iso(),
        degraded_resources=degraded,
        flow_log_configs=flow_logs,
        vpcs_without_flow_logs=vpcs_without_flow_logs,
        metrics=metrics,
        unhealthy_reachability_analyses=unhealthy_analyses,
        recent_config_changes=recent_changes,
        limitations=limitations,
    )


__all__ = ["get_network_health"]
