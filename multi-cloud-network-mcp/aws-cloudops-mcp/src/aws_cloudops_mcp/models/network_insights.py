"""Normalized models for Reachability Analyzer and Network Access Analyzer.

Both are read-only result *retrieval* here -- this milestone explicitly
excludes creating a Reachability Analyzer path/analysis or a Network
Access Analyzer scope/analysis (those are mutating EC2 operations). A
finding's ``finding_components`` is a summary (component ARNs/types only,
not AWS's full nested explanation graph) so a single finding can't blow
up a tool response; the milestone asks for result retrieval, not a full
reproduction of the console's analysis view.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource


class NetworkInsightsPath(AwsResource):
    """Normalized entry from ec2:DescribeNetworkInsightsPaths (Reachability
    Analyzer) -- a path definition, not yet analyzed or already analyzed
    elsewhere."""

    network_insights_path_id: str
    network_insights_path_arn: str | None = None
    source: str | None = None
    destination: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    protocol: str | None = None
    destination_port: int | None = None


class NetworkInsightsAnalysis(AwsResource):
    """Normalized entry from ec2:DescribeNetworkInsightsAnalyses --
    a completed (or in-progress) reachability analysis for one path."""

    network_insights_analysis_id: str
    network_insights_analysis_arn: str | None = None
    network_insights_path_id: str | None = None
    status: str | None = None
    status_message: str | None = None
    warning_message: str | None = None
    network_path_found: bool | None = None
    start_date: str | None = None


class NetworkInsightsAccessScope(AwsResource):
    """Normalized entry from ec2:DescribeNetworkInsightsAccessScopes
    (Network Access Analyzer) -- a scope definition."""

    network_insights_access_scope_id: str
    network_insights_access_scope_arn: str | None = None
    created_date: str | None = None
    updated_date: str | None = None


class NetworkInsightsAccessScopeAnalysis(AwsResource):
    """Normalized entry from ec2:DescribeNetworkInsightsAccessScopeAnalyses."""

    network_insights_access_scope_analysis_id: str
    network_insights_access_scope_analysis_arn: str | None = None
    network_insights_access_scope_id: str | None = None
    status: str | None = None
    status_message: str | None = None
    warning_message: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    findings_found: str | None = None  # "true" | "false" | "unknown"
    analyzed_eni_count: int | None = None


class AccessScopeFindingComponent(BaseModel):
    component_id: str | None = None
    component_arn: str | None = None


class AccessScopeAnalysisFinding(AwsResource):
    """Normalized entry from ec2:GetNetworkInsightsAccessScopeAnalysisFindings.

    ``finding_components`` is a bounded summary (component id/ARN) of
    the finding's path components, not AWS's full per-component
    explanation payload -- see module docstring.
    """

    finding_id: str
    network_insights_access_scope_analysis_id: str
    network_insights_access_scope_id: str | None = None
    finding_components: list[AccessScopeFindingComponent] = Field(default_factory=list)


__all__ = [
    "AccessScopeAnalysisFinding",
    "AccessScopeFindingComponent",
    "NetworkInsightsAccessScope",
    "NetworkInsightsAccessScopeAnalysis",
    "NetworkInsightsAnalysis",
    "NetworkInsightsPath",
]
