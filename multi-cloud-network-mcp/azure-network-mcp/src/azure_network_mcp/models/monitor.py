"""Normalized models for bounded Azure Monitor metric queries.

Only a small, fixed catalog of known network-relevant metrics is ever
queried (``arm/monitor.py::KNOWN_NETWORK_METRICS``), never open-ended
metric discovery, and every query is bounded on both timespan and
datapoint count -- see ``arm/monitor.py`` for the caps. This mirrors the
bounded-metrics pattern this project's AWS sibling established for
CloudWatch (``aws_cloudops_mcp.aws.network_metrics``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricDataPoint(BaseModel):
    timestamp: str
    average: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    total: float | None = None
    count: float | None = None


class MetricSeries(BaseModel):
    metric_name: str
    unit: str | None = None
    data_points: list[MetricDataPoint] = Field(default_factory=list)


class MetricQueryResult(BaseModel):
    resource_id: str
    timespan: str
    interval: str | None = None
    series: list[MetricSeries] = Field(default_factory=list)
    stale: bool = False


__all__ = ["MetricDataPoint", "MetricQueryResult", "MetricSeries"]
