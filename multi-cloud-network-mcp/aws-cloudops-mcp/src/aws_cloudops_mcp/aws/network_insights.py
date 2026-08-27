"""AWS service layer: Reachability Analyzer and Network Access Analyzer,
read-only result retrieval only.

Nothing in this module creates a path, an analysis, a scope, or a scope
analysis (``ec2:CreateNetworkInsightsPath``, ``StartNetworkInsightsAnalysis``,
``CreateNetworkInsightsAccessScope``, ``StartNetworkInsightsAccessScopeAnalysis``
and their delete counterparts are all mutating operations, explicitly out
of this milestone's scope) -- only the corresponding ``Describe*``/``Get*``
calls that read results an operator (or a separate process) already
created.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_insights import (
    AccessScopeAnalysisFinding,
    AccessScopeFindingComponent,
    NetworkInsightsAccessScope,
    NetworkInsightsAccessScopeAnalysis,
    NetworkInsightsAnalysis,
    NetworkInsightsPath,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

DEFAULT_MAX_FINDINGS = 100


def list_network_insights_paths(
    client_factory: ClientFactory,
    *,
    region: str,
    network_insights_path_ids: list[str] | None = None,
) -> list[NetworkInsightsPath]:
    """Call ec2:DescribeNetworkInsightsPaths and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = (
        {"NetworkInsightsPathIds": network_insights_path_ids} if network_insights_path_ids else {}
    )
    raw = paginate(
        client,
        "describe_network_insights_paths",
        "NetworkInsightsPaths",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        NetworkInsightsPath(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeNetworkInsightsPaths",
            network_insights_path_id=p["NetworkInsightsPathId"],
            network_insights_path_arn=p.get("NetworkInsightsPathArn"),
            source=p.get("Source"),
            destination=p.get("Destination"),
            source_ip=p.get("SourceIp"),
            destination_ip=p.get("DestinationIp"),
            protocol=p.get("Protocol"),
            destination_port=p.get("DestinationPort"),
            tags=normalize_tags(p.get("Tags")),
        )
        for p in raw
    ]


def list_network_insights_analyses(
    client_factory: ClientFactory,
    *,
    region: str,
    network_insights_path_id: str | None = None,
    network_insights_analysis_ids: list[str] | None = None,
) -> list[NetworkInsightsAnalysis]:
    """Call ec2:DescribeNetworkInsightsAnalyses and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if network_insights_path_id:
        kwargs["NetworkInsightsPathId"] = network_insights_path_id
    if network_insights_analysis_ids:
        kwargs["NetworkInsightsAnalysisIds"] = network_insights_analysis_ids

    raw = paginate(
        client,
        "describe_network_insights_analyses",
        "NetworkInsightsAnalyses",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        NetworkInsightsAnalysis(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeNetworkInsightsAnalyses",
            network_insights_analysis_id=a["NetworkInsightsAnalysisId"],
            network_insights_analysis_arn=a.get("NetworkInsightsAnalysisArn"),
            network_insights_path_id=a.get("NetworkInsightsPathId"),
            status=a.get("Status"),
            status_message=a.get("StatusMessage"),
            warning_message=a.get("WarningMessage"),
            network_path_found=a.get("NetworkPathFound"),
            start_date=str(a["StartDate"]) if a.get("StartDate") else None,
            tags=normalize_tags(a.get("Tags")),
        )
        for a in raw
    ]


def list_network_insights_access_scopes(
    client_factory: ClientFactory,
    *,
    region: str,
    network_insights_access_scope_ids: list[str] | None = None,
) -> list[NetworkInsightsAccessScope]:
    """Call ec2:DescribeNetworkInsightsAccessScopes and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = (
        {"NetworkInsightsAccessScopeIds": network_insights_access_scope_ids}
        if network_insights_access_scope_ids
        else {}
    )
    raw = paginate(
        client,
        "describe_network_insights_access_scopes",
        "NetworkInsightsAccessScopes",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        NetworkInsightsAccessScope(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeNetworkInsightsAccessScopes",
            network_insights_access_scope_id=s["NetworkInsightsAccessScopeId"],
            network_insights_access_scope_arn=s.get("NetworkInsightsAccessScopeArn"),
            created_date=str(s["CreatedDate"]) if s.get("CreatedDate") else None,
            updated_date=str(s["UpdatedDate"]) if s.get("UpdatedDate") else None,
            tags=normalize_tags(s.get("Tags")),
        )
        for s in raw
    ]


def list_network_insights_access_scope_analyses(
    client_factory: ClientFactory,
    *,
    region: str,
    network_insights_access_scope_id: str | None = None,
) -> list[NetworkInsightsAccessScopeAnalysis]:
    """Call ec2:DescribeNetworkInsightsAccessScopeAnalyses and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = (
        {"NetworkInsightsAccessScopeId": network_insights_access_scope_id}
        if network_insights_access_scope_id
        else {}
    )
    raw = paginate(
        client,
        "describe_network_insights_access_scope_analyses",
        "NetworkInsightsAccessScopeAnalyses",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        NetworkInsightsAccessScopeAnalysis(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeNetworkInsightsAccessScopeAnalyses",
            network_insights_access_scope_analysis_id=a["NetworkInsightsAccessScopeAnalysisId"],
            network_insights_access_scope_analysis_arn=a.get(
                "NetworkInsightsAccessScopeAnalysisArn"
            ),
            network_insights_access_scope_id=a.get("NetworkInsightsAccessScopeId"),
            status=a.get("Status"),
            status_message=a.get("StatusMessage"),
            warning_message=a.get("WarningMessage"),
            start_date=str(a["StartDate"]) if a.get("StartDate") else None,
            end_date=str(a["EndDate"]) if a.get("EndDate") else None,
            findings_found=a.get("FindingsFound"),
            analyzed_eni_count=a.get("AnalyzedEniCount"),
            tags=normalize_tags(a.get("Tags")),
        )
        for a in raw
    ]


def get_access_scope_analysis_findings(
    client_factory: ClientFactory,
    *,
    region: str,
    network_insights_access_scope_analysis_id: str,
    max_results: int = DEFAULT_MAX_FINDINGS,
) -> list[AccessScopeAnalysisFinding]:
    """Call ec2:GetNetworkInsightsAccessScopeAnalysisFindings, bounded to
    ``max_results`` findings (AWS itself paginates this call; the cap here
    bounds how many pages this tool follows, since a single scope analysis
    can produce a very large number of findings)."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_network_insights_access_scope_analysis_findings",
        "AnalysisFindings",
        max_items=max_results,
        NetworkInsightsAccessScopeAnalysisId=network_insights_access_scope_analysis_id,
    )
    return [
        AccessScopeAnalysisFinding(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:GetNetworkInsightsAccessScopeAnalysisFindings",
            finding_id=f["FindingId"],
            network_insights_access_scope_analysis_id=f["NetworkInsightsAccessScopeAnalysisId"],
            network_insights_access_scope_id=f.get("NetworkInsightsAccessScopeId"),
            finding_components=[
                AccessScopeFindingComponent(
                    component_id=(c.get("Component") or {}).get("Id"),
                    component_arn=(c.get("Component") or {}).get("Arn"),
                )
                for c in f.get("FindingComponents", [])
            ],
        )
        for f in raw
    ]


__all__ = [
    "get_access_scope_analysis_findings",
    "list_network_insights_access_scope_analyses",
    "list_network_insights_access_scopes",
    "list_network_insights_analyses",
    "list_network_insights_paths",
]
