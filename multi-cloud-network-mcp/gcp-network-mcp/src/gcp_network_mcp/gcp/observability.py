"""Service-layer functions for the explicit-opt-in, narrowly-bounded
Cloud Logging/Monitoring read tools.

Neither ``list_log_entries`` nor ``list_time_series`` is ever called
without an explicit, caller-supplied filter and a bounded time window --
every query is additionally capped at ``Settings.max_log_entries``/
``max_time_series_points`` and ``Settings.max_log_query_window_hours``/
``max_metric_query_window_hours`` regardless of what the caller requests,
so a single tool call can never return an unbounded amount of log/metric
data. This is the read path for troubleshooting, never a general-purpose
log/metric browser.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from google.cloud import monitoring_v3
from google.cloud.logging_v2.types import ListLogEntriesRequest, LogEntry
from google.logging.type import log_severity_pb2

from gcp_network_mcp.config import Settings
from gcp_network_mcp.exceptions import InvalidConfigurationError
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import now_iso
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.models.observability import (
    LogEntrySummary,
    LogQueryResult,
    MetricQueryResult,
    TimeSeriesPoint,
    TimeSeriesSummary,
)

_MAX_PAYLOAD_CHARS = 2000


def _render_payload(entry: LogEntry) -> str | None:
    if "text_payload" in entry:
        return entry.text_payload[:_MAX_PAYLOAD_CHARS]
    if "json_payload" in entry:
        return json.dumps(dict(entry.json_payload), default=str)[:_MAX_PAYLOAD_CHARS]
    if "proto_payload" in entry:
        return f"<proto_payload type_url={entry.proto_payload.type_url}>"
    return None


def _normalize_log_entry(entry: LogEntry) -> LogEntrySummary:
    return LogEntrySummary(
        timestamp=entry.timestamp.rfc3339() if "timestamp" in entry else None,
        severity=log_severity_pb2.LogSeverity.Name(entry.severity),
        log_name=entry.log_name or None,
        resource_type=entry.resource.type or None,
        insert_id=entry.insert_id or None,
        payload=_render_payload(entry),
    )


def query_logs(
    client_factory: ClientFactory,
    settings: Settings,
    *,
    project_id: str,
    filter_expr: str,
    hours: float | None = None,
) -> LogQueryResult:
    """Bounded, explicit-opt-in log query. ``filter_expr`` is required --
    this tool never returns "every log" for a project. ``hours`` (the
    lookback window) is capped at ``Settings.max_log_query_window_hours``."""
    window_hours = min(
        hours or settings.max_log_query_window_hours, settings.max_log_query_window_hours
    )
    if window_hours <= 0:
        raise InvalidConfigurationError("hours must be a positive number.")
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    bounded_filter = f'{filter_expr} AND timestamp>="{since.isoformat()}"'

    max_entries = settings.max_log_entries
    # list_log_entries rejects mixing `request=` with flattened kwargs, so
    # page_size (only settable via the request object) means every field
    # for this call goes through one ListLogEntriesRequest.
    request = ListLogEntriesRequest(
        resource_names=[f"projects/{project_id}"],
        filter=bounded_filter,
        order_by="timestamp desc",
        page_size=min(max_entries, 1000),
    )
    entries = paginate(
        client_factory.logs(),
        "list_log_entries",
        resource_type="log_entry",
        project_id=project_id,
        max_items=max_entries,
        items_field="entries",
        request=request,
    )
    return LogQueryResult(
        project_id=project_id,
        filter_expr=bounded_filter,
        entries=[_normalize_log_entry(e) for e in entries],
        truncated=len(entries) >= max_entries,
        observed_at=now_iso(),
    )


def _normalize_time_series(
    series: monitoring_v3.TimeSeries, *, max_points: int
) -> TimeSeriesSummary:
    return TimeSeriesSummary(
        metric_type=series.metric.type,
        resource_type=series.resource.type or None,
        resource_labels=dict(series.resource.labels),
        metric_labels=dict(series.metric.labels),
        points=[
            TimeSeriesPoint(
                start_time=p.interval.start_time.rfc3339() if "start_time" in p.interval else None,
                end_time=p.interval.end_time.rfc3339() if "end_time" in p.interval else None,
                value=_typed_value(p.value),
            )
            for p in list(series.points)[:max_points]
        ],
    )


def _typed_value(value: monitoring_v3.TypedValue) -> float | None:
    if "double_value" in value:
        return value.double_value
    if "int64_value" in value:
        return float(value.int64_value)
    if "bool_value" in value:
        return float(value.bool_value)
    return None


def query_metrics(
    client_factory: ClientFactory,
    settings: Settings,
    *,
    project_id: str,
    filter_expr: str,
    hours: float | None = None,
) -> MetricQueryResult:
    """Bounded, explicit-opt-in metric query. ``filter_expr`` is required
    (e.g. ``metric.type="compute.googleapis.com/instance/network/received_bytes_count"``);
    ``hours`` (the lookback window) is capped at
    ``Settings.max_metric_query_window_hours``, and total returned points
    across all time series at ``Settings.max_time_series_points``."""
    window_hours = min(
        hours or settings.max_metric_query_window_hours, settings.max_metric_query_window_hours
    )
    if window_hours <= 0:
        raise InvalidConfigurationError("hours must be a positive number.")
    now = datetime.now(UTC)
    interval = monitoring_v3.TimeInterval(
        start_time=now - timedelta(hours=window_hours), end_time=now
    )

    max_points = settings.max_time_series_points
    raw_series = paginate(
        client_factory.metrics(),
        "list_time_series",
        resource_type="time_series",
        project_id=project_id,
        max_items=max_points,  # one item here is one TimeSeries, a conservative proxy cap
        items_field="time_series",
        name=f"projects/{project_id}",
        filter=filter_expr,
        interval=interval,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )

    series_list: list[TimeSeriesSummary] = []
    total_points = 0
    truncated = False
    for series in raw_series:
        remaining = max_points - total_points
        if remaining <= 0:
            truncated = True
            break
        summary = _normalize_time_series(series, max_points=remaining)
        total_points += len(summary.points)
        series_list.append(summary)

    return MetricQueryResult(
        project_id=project_id,
        filter_expr=filter_expr,
        time_series=series_list,
        truncated=truncated,
        observed_at=now_iso(),
    )


__all__ = ["query_logs", "query_metrics"]
