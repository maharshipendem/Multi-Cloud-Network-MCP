"""``azure_get_network_health``'s report assembly: degraded resources,
unhealthy connections, and (opt-in, bounded) Azure Monitor metrics for the
resource group's gateways and circuits."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from azure_network_mcp.diagnostics.consistency import find_blackhole_routes, find_degraded_resources
from azure_network_mcp.diagnostics.models import Finding
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.common import CollectionWarning
from azure_network_mcp.models.monitor import MetricQueryResult

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory

# Bounded fan-out for opt-in metrics: at most this many resources get a
# metrics query per health-check call, mirroring this project's AWS
# sibling's bounded CloudWatch integration in aws_get_network_health.
MAX_METRIC_RESOURCES = 5


class NetworkHealthReport(BaseModel):
    resource_group: str
    subscription_id: str
    observed_at: str
    total_resources_checked: int
    degraded_resource_count: int
    unhealthy_connection_count: int
    findings: list[Finding] = Field(default_factory=list)
    metrics: list[MetricQueryResult] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)


def get_network_health(
    snapshot: HybridNetworkSnapshot,
    *,
    client_factory: ClientFactory | None = None,
    include_metrics: bool = False,
) -> NetworkHealthReport:
    """Assemble a health report from an already-collected snapshot.
    ``include_metrics`` opts into bounded Azure Monitor metric queries
    (requires ``client_factory``) for up to ``MAX_METRIC_RESOURCES`` of
    the snapshot's gateways/circuits -- resources beyond the cap are
    skipped with a recorded warning, never silently omitted.
    """
    findings = find_degraded_resources(snapshot) + find_blackhole_routes(snapshot)

    degraded_count = sum(
        1
        for state in (
            [v.provisioning_state for v in snapshot.virtual_networks]
            + [n.provisioning_state for n in snapshot.network_security_groups]
            + [r.provisioning_state for r in snapshot.route_tables]
            + [g.provisioning_state for g in snapshot.vpn_gateways]
            + [g.provisioning_state for g in snapshot.virtual_network_gateways]
            + [c.provisioning_state for c in snapshot.express_route_circuits]
            + [g.provisioning_state for g in snapshot.express_route_gateways]
        )
        if state and state != "Succeeded"
    )
    unhealthy_connection_count = sum(
        1
        for status in (
            [c.connection_status for c in snapshot.vpn_connections]
            + [c.connection_status for c in snapshot.virtual_network_gateway_connections]
        )
        if status in {"Disconnected", "NotConnected", "Degraded", "Unknown"}
    )

    total_checked = (
        len(snapshot.virtual_networks)
        + len(snapshot.network_security_groups)
        + len(snapshot.route_tables)
        + len(snapshot.vpn_gateways)
        + len(snapshot.vpn_connections)
        + len(snapshot.virtual_network_gateways)
        + len(snapshot.virtual_network_gateway_connections)
        + len(snapshot.express_route_circuits)
        + len(snapshot.express_route_gateways)
    )

    metrics: list[MetricQueryResult] = []
    warnings: list[CollectionWarning] = list(snapshot.warnings)

    if include_metrics:
        if client_factory is None:
            warnings.append(
                CollectionWarning(
                    resource_type="metric",
                    code="METRICS_UNAVAILABLE",
                    message="include_metrics was requested but no client_factory was provided.",
                )
            )
        else:
            from azure_network_mcp.arm.monitor import get_metrics

            candidates = [
                r.resource_id
                for r in (
                    snapshot.virtual_network_gateways
                    + snapshot.vpn_gateways
                    + snapshot.express_route_circuits
                )
            ]
            for resource_id in candidates[:MAX_METRIC_RESOURCES]:
                try:
                    metrics.append(
                        get_metrics(
                            client_factory,
                            subscription_id=snapshot.subscription_id,
                            resource_id=resource_id,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 -- best-effort per resource
                    warnings.append(
                        CollectionWarning(
                            resource_type="metric",
                            code="COLLECTION_FAILED",
                            message=f"Could not collect metrics for {resource_id}: {exc}",
                        )
                    )
            if len(candidates) > MAX_METRIC_RESOURCES:
                warnings.append(
                    CollectionWarning(
                        resource_type="metric",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"{len(candidates)} gateway/circuit resources found; metrics "
                            f"were queried for only the first {MAX_METRIC_RESOURCES}."
                        ),
                    )
                )

    return NetworkHealthReport(
        resource_group=snapshot.resource_group,
        subscription_id=snapshot.subscription_id,
        observed_at=snapshot.observed_at,
        total_resources_checked=total_checked,
        degraded_resource_count=degraded_count,
        unhealthy_connection_count=unhealthy_connection_count,
        findings=findings,
        metrics=metrics,
        warnings=warnings,
    )


__all__ = ["MAX_METRIC_RESOURCES", "NetworkHealthReport", "get_network_health"]
