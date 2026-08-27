"""AWS service layer: bounded, opt-in CloudWatch metric queries for
configured resource health -- the "CloudWatch metric discovery" half of
this milestone's ``aws_get_network_health`` tool (the other half, Flow
Log discovery, is ``aws_list_flow_logs`` from Milestone 3).

``KNOWN_NETWORK_METRICS`` is a small, curated catalog of the specific
CloudWatch metrics each network resource type actually publishes that
are relevant to a health check (not every metric AWS emits for it) --
this is a read *query*, not metric *discovery via ListMetrics*, since a
fixed, documented catalog is more useful for a deterministic health
check than an open-ended metric search.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NamedTuple

from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.models.network_metrics import MetricDatapoint, ResourceMetric

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

MAX_LOOKBACK_HOURS = 24
DEFAULT_LOOKBACK_HOURS = 3
DEFAULT_PERIOD_SECONDS = 300
MAX_DATAPOINTS = 288  # 24h at 5-minute resolution


class _KnownMetric(NamedTuple):
    namespace: str
    metric_name: str
    dimension_name: str


KNOWN_NETWORK_METRICS: dict[str, list[_KnownMetric]] = {
    "nat_gateway": [
        _KnownMetric("AWS/NATGateway", "ErrorPortAllocation", "NatGatewayId"),
        _KnownMetric("AWS/NATGateway", "PacketsDropCount", "NatGatewayId"),
    ],
    "transit_gateway": [
        _KnownMetric("AWS/TransitGateway", "PacketDropCountBlackhole", "TransitGateway"),
        _KnownMetric("AWS/TransitGateway", "PacketDropCountNoRoute", "TransitGateway"),
    ],
    "vpn": [
        _KnownMetric("AWS/VPN", "TunnelState", "VpnId"),
    ],
}


def get_resource_metric(
    client_factory: ClientFactory,
    *,
    region: str,
    namespace: str,
    metric_name: str,
    dimension_name: str,
    dimension_value: str,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    period_seconds: int = DEFAULT_PERIOD_SECONDS,
) -> ResourceMetric:
    """Call cloudwatch:GetMetricStatistics for one metric, bounded to at
    most ``MAX_LOOKBACK_HOURS`` of history and ``MAX_DATAPOINTS`` points."""
    validate_region_format(region)
    client = client_factory.get_client("cloudwatch", region=region)

    capped_lookback = max(1, min(lookback_hours, MAX_LOOKBACK_HOURS))
    capped_period = max(60, period_seconds)
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=capped_lookback)

    response = call_readonly(
        client,
        "get_metric_statistics",
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": dimension_name, "Value": dimension_value}],
        StartTime=start_time,
        EndTime=end_time,
        Period=capped_period,
        Statistics=["Sum", "Average", "Maximum", "Minimum", "SampleCount"],
    )
    datapoints = sorted(response.get("Datapoints", []), key=lambda d: d["Timestamp"])[
        :MAX_DATAPOINTS
    ]

    return ResourceMetric(
        namespace=namespace,
        metric_name=metric_name,
        dimensions={dimension_name: dimension_value},
        datapoints=[
            MetricDatapoint(
                timestamp=str(d["Timestamp"]),
                sum=d.get("Sum"),
                average=d.get("Average"),
                maximum=d.get("Maximum"),
                minimum=d.get("Minimum"),
                sample_count=d.get("SampleCount"),
                unit=d.get("Unit"),
            )
            for d in datapoints
        ],
    )


def get_known_metrics_for_resource(
    client_factory: ClientFactory,
    *,
    region: str,
    resource_type: str,
    resource_id: str,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> list[ResourceMetric]:
    """Query every catalog metric for one resource (e.g. all NAT gateway
    health metrics for one ``nat_gateway_id``). Returns an empty list for
    a ``resource_type`` with no catalog entry, rather than raising."""
    metrics = []
    for known in KNOWN_NETWORK_METRICS.get(resource_type, []):
        metrics.append(
            get_resource_metric(
                client_factory,
                region=region,
                namespace=known.namespace,
                metric_name=known.metric_name,
                dimension_name=known.dimension_name,
                dimension_value=resource_id,
                lookback_hours=lookback_hours,
            )
        )
    return metrics


__all__ = [
    "DEFAULT_LOOKBACK_HOURS",
    "KNOWN_NETWORK_METRICS",
    "MAX_DATAPOINTS",
    "MAX_LOOKBACK_HOURS",
    "get_known_metrics_for_resource",
    "get_resource_metric",
]
