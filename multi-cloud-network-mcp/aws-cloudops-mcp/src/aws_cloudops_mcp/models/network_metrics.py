"""Normalized model for bounded CloudWatch metric queries used by network
health checks."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricDatapoint(BaseModel):
    timestamp: str
    sum: float | None = None
    average: float | None = None
    maximum: float | None = None
    minimum: float | None = None
    sample_count: float | None = None
    unit: str | None = None


class ResourceMetric(BaseModel):
    namespace: str
    metric_name: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    datapoints: list[MetricDatapoint] = Field(default_factory=list)


__all__ = ["MetricDatapoint", "ResourceMetric"]
