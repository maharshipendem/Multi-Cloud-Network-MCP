"""Normalized models for the explicit-opt-in, narrowly-bounded Cloud
Logging/Monitoring read tools. Never a general-purpose log/metric
browser -- every query is capped on result count and time window
regardless of what a caller requests (see ``config.py``'s
``max_log_entries``/``max_log_query_window_hours``/
``max_time_series_points``/``max_metric_query_window_hours``)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LogEntrySummary(BaseModel):
    """One log entry. ``payload`` is a bounded, truncated string
    rendering of whatever payload type the entry carried (text/JSON/proto)
    -- never returned unbounded, to keep a single tool call's response
    size predictable."""

    timestamp: str | None = None
    severity: str | None = None
    log_name: str | None = None
    resource_type: str | None = None
    insert_id: str | None = None
    payload: str | None = None


class LogQueryResult(BaseModel):
    project_id: str
    filter_expr: str
    entries: list[LogEntrySummary] = Field(default_factory=list)
    truncated: bool = False
    observed_at: str


class TimeSeriesPoint(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    value: float | None = None


class TimeSeriesSummary(BaseModel):
    metric_type: str
    resource_type: str | None = None
    resource_labels: dict[str, str] = Field(default_factory=dict)
    metric_labels: dict[str, str] = Field(default_factory=dict)
    points: list[TimeSeriesPoint] = Field(default_factory=list)


class MetricQueryResult(BaseModel):
    project_id: str
    filter_expr: str
    time_series: list[TimeSeriesSummary] = Field(default_factory=list)
    truncated: bool = False
    observed_at: str


__all__ = [
    "LogEntrySummary",
    "LogQueryResult",
    "MetricQueryResult",
    "TimeSeriesPoint",
    "TimeSeriesSummary",
]
