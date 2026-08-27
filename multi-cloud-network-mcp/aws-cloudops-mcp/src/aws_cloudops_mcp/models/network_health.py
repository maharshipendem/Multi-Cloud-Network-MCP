"""Combined output model for ``aws_get_network_health``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.diagnostics.models import Finding
from aws_cloudops_mcp.models.cloudtrail import NetworkConfigEvent
from aws_cloudops_mcp.models.flowlogs import FlowLogConfig
from aws_cloudops_mcp.models.network_insights import NetworkInsightsAnalysis
from aws_cloudops_mcp.models.network_metrics import ResourceMetric


class NetworkHealthReport(BaseModel):
    region: str
    collected_at: str
    degraded_resources: list[Finding] = Field(default_factory=list)
    flow_log_configs: list[FlowLogConfig] = Field(default_factory=list)
    vpcs_without_flow_logs: list[str] = Field(default_factory=list)
    metrics: list[ResourceMetric] = Field(default_factory=list)
    unhealthy_reachability_analyses: list[NetworkInsightsAnalysis] = Field(default_factory=list)
    recent_config_changes: list[NetworkConfigEvent] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


__all__ = ["NetworkHealthReport"]
