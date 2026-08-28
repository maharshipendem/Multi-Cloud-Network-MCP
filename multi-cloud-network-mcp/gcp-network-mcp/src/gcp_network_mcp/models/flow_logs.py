"""Normalized model for VPC Flow Logs *configuration* only -- never log
records/content. A VPC Flow Logs Config (Network Management API) targets
exactly one of a subnet/VPN tunnel/Interconnect attachment; ``target_type``
is derived from whichever of those three fields is populated."""

from __future__ import annotations

from pydantic import BaseModel


class VpcFlowLogsConfigSummary(BaseModel):
    name: str
    state: str | None = None
    target_type: str
    target_resource: str | None = None
    aggregation_interval: str | None = None
    flow_sampling: float | None = None
    filter_expr: str | None = None
    description: str | None = None
    cross_project_metadata: str | None = None
    observed_at: str
    source_api: str = "VpcFlowLogsServiceClient.list_vpc_flow_logs_configs"


__all__ = ["VpcFlowLogsConfigSummary"]
