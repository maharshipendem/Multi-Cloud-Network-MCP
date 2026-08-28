"""ARM service layer: bounded Azure Monitor metric queries for network
health.

Mirrors this project's AWS sibling's ``aws_cloudops_mcp.aws.network_metrics``
pattern: only a small, fixed catalog of known network-relevant metrics is
ever queried (never open-ended metric discovery), and every query is
bounded on both timespan and datapoint count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from azure_network_mcp.arm.readonly import call_readonly
from azure_network_mcp.exceptions import ToolExecutionError
from azure_network_mcp.models.monitor import MetricDataPoint, MetricQueryResult, MetricSeries

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory

MAX_LOOKBACK_HOURS = 24
MAX_DATAPOINTS = 288
DEFAULT_INTERVAL = "PT5M"

# A fixed catalog of network-relevant metrics per ARM resource type --
# never an open-ended "any metric name" query. Keys are the resource
# type's provider/type segment as it appears in an ARM resource ID.
KNOWN_NETWORK_METRICS: dict[str, list[str]] = {
    "microsoft.network/virtualnetworkgateways": [
        "TunnelAverageBandwidth",
        "TunnelEgressBytes",
        "TunnelIngressBytes",
        "TunnelPeerCount",
        "P2SConnectionCount",
    ],
    "microsoft.network/expressroutecircuits": [
        "BitsInPerSecond",
        "BitsOutPerSecond",
        "ArpAvailability",
        "BgpAvailability",
    ],
    "microsoft.network/azurefirewalls": [
        "Throughput",
        "FirewallHealth",
        "SNATPortUtilization",
    ],
    "microsoft.network/loadbalancers": [
        "ByteCount",
        "PacketCount",
        "SnatConnectionCount",
        "DipAvailability",
    ],
    "microsoft.network/applicationgateways": [
        "Throughput",
        "TotalRequests",
        "UnhealthyHostCount",
        "FailedRequests",
    ],
    "microsoft.network/p2svpngateways": ["P2SConnectionCount", "P2SBandwidth"],
    "microsoft.network/vpngateways": ["TunnelAverageBandwidth", "TunnelEgressBytes"],
}


def _resource_type_key(resource_id: str) -> str:
    parts = [p for p in resource_id.lower().split("/") if p]
    idx = parts.index("providers") if "providers" in parts else -1
    if idx == -1 or idx + 2 >= len(parts):
        return ""
    return f"{parts[idx + 1]}/{parts[idx + 2]}"


def get_metrics(
    client_factory: ClientFactory, *, subscription_id: str, resource_id: str
) -> MetricQueryResult:
    """Query the fixed metric catalog for ``resource_id``'s resource
    type, bounded to the last ``MAX_LOOKBACK_HOURS`` hours at
    ``DEFAULT_INTERVAL`` granularity (capped at ``MAX_DATAPOINTS`` points
    per series). Raises ``ToolExecutionError`` if the resource type has
    no known metric catalog entry, rather than falling back to an
    unbounded/undocumented metric discovery call.
    """
    metric_names = KNOWN_NETWORK_METRICS.get(_resource_type_key(resource_id))
    if not metric_names:
        raise ToolExecutionError(
            f"No known network metric catalog entry for resource type of '{resource_id}'.",
            error_type="TOOL_EXECUTION_ERROR",
        )

    client = client_factory.get_monitor_client(subscription_id)
    end = datetime.now(UTC)
    start = end - timedelta(hours=MAX_LOOKBACK_HOURS)
    timespan = f"{start.isoformat()}/{end.isoformat()}"

    response = call_readonly(
        client.metrics,
        "list",
        resource_uri=resource_id,
        timespan=timespan,
        interval=DEFAULT_INTERVAL,
        metricnames=",".join(metric_names),
        aggregation="Average,Total,Maximum,Minimum,Count",
    )

    series: list[MetricSeries] = []
    for metric in response.value or []:
        data_points: list[MetricDataPoint] = []
        for ts in metric.timeseries or []:
            for point in (ts.data or [])[:MAX_DATAPOINTS]:
                data_points.append(
                    MetricDataPoint(
                        timestamp=point.time_stamp.isoformat() if point.time_stamp else "",
                        average=point.average,
                        minimum=point.minimum,
                        maximum=point.maximum,
                        total=point.total,
                        count=point.count,
                    )
                )
        series.append(
            MetricSeries(
                metric_name=(metric.name.value if metric.name else "unknown"),
                unit=str(metric.unit) if metric.unit else None,
                data_points=data_points,
            )
        )

    is_stale = all(not s.data_points for s in series)
    return MetricQueryResult(
        resource_id=resource_id,
        timespan=timespan,
        interval=DEFAULT_INTERVAL,
        series=series,
        stale=is_stale,
    )


__all__ = ["KNOWN_NETWORK_METRICS", "MAX_DATAPOINTS", "MAX_LOOKBACK_HOURS", "get_metrics"]
