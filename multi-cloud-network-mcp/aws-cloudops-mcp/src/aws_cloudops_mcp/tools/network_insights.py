"""MCP tools: Reachability Analyzer and Network Access Analyzer read-only
result retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.network_insights import (
    get_access_scope_analysis_findings,
    list_network_insights_access_scope_analyses,
    list_network_insights_access_scopes,
    list_network_insights_analyses,
    list_network_insights_paths,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name="aws_list_network_insights_paths",
        description=(
            "List existing Reachability Analyzer path definitions. "
            "Read-only -- never creates a path (ec2:CreateNetworkInsightsPath "
            "is a mutating operation, out of scope)."
        ),
        meta=capability_meta(resource_types=["network_insights_path"]),
    )
    def aws_list_network_insights_paths(
        region: str, network_insights_path_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List Reachability Analyzer paths.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            network_insights_path_ids: Filter to specific path IDs.
        """
        return execute_tool(
            tool_name="aws_list_network_insights_paths",
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_insights_paths(
                client_factory, region=region, network_insights_path_ids=network_insights_path_ids
            ),
        )

    @mcp.tool(
        name="aws_list_network_insights_analyses",
        description=(
            "List existing Reachability Analyzer analyses for a path, "
            "including whether a network path was found. Read-only -- "
            "never starts a new analysis (ec2:StartNetworkInsightsAnalysis "
            "is a mutating operation, out of scope)."
        ),
        meta=capability_meta(resource_types=["network_insights_analysis"]),
    )
    def aws_list_network_insights_analyses(
        region: str,
        network_insights_path_id: str | None = None,
        network_insights_analysis_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List Reachability Analyzer analyses.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            network_insights_path_id: Filter to analyses for this path.
            network_insights_analysis_ids: Filter to specific analysis IDs.
        """
        return execute_tool(
            tool_name="aws_list_network_insights_analyses",
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_insights_analyses(
                client_factory,
                region=region,
                network_insights_path_id=network_insights_path_id,
                network_insights_analysis_ids=network_insights_analysis_ids,
            ),
        )

    @mcp.tool(
        name="aws_list_network_insights_access_scopes",
        description=(
            "List existing Network Access Analyzer scope definitions. "
            "Read-only -- never creates a scope "
            "(ec2:CreateNetworkInsightsAccessScope is a mutating "
            "operation, out of scope)."
        ),
        meta=capability_meta(resource_types=["network_insights_access_scope"]),
    )
    def aws_list_network_insights_access_scopes(
        region: str, network_insights_access_scope_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List Network Access Analyzer access scopes.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            network_insights_access_scope_ids: Filter to specific scope IDs.
        """
        return execute_tool(
            tool_name="aws_list_network_insights_access_scopes",
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_insights_access_scopes(
                client_factory,
                region=region,
                network_insights_access_scope_ids=network_insights_access_scope_ids,
            ),
        )

    @mcp.tool(
        name="aws_list_network_insights_access_scope_analyses",
        description=(
            "List existing Network Access Analyzer scope analyses, "
            "including whether findings were found. Read-only -- never "
            "starts a new scope analysis "
            "(ec2:StartNetworkInsightsAccessScopeAnalysis is a mutating "
            "operation, out of scope)."
        ),
        meta=capability_meta(resource_types=["network_insights_access_scope_analysis"]),
    )
    def aws_list_network_insights_access_scope_analyses(
        region: str, network_insights_access_scope_id: str | None = None
    ) -> dict[str, Any]:
        """List Network Access Analyzer scope analyses.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            network_insights_access_scope_id: Filter to analyses for this scope.
        """
        return execute_tool(
            tool_name="aws_list_network_insights_access_scope_analyses",
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_insights_access_scope_analyses(
                client_factory,
                region=region,
                network_insights_access_scope_id=network_insights_access_scope_id,
            ),
        )

    @mcp.tool(
        name="aws_get_network_insights_access_scope_analysis_findings",
        description=(
            "Retrieve findings for a completed Network Access Analyzer "
            "scope analysis, bounded to a maximum number of findings. "
            "Each finding's components are a summary (component ID/ARN), "
            "not AWS's full explanation payload. Read-only."
        ),
        meta=capability_meta(resource_types=["network_insights_access_scope_analysis_finding"]),
    )
    def aws_get_network_insights_access_scope_analysis_findings(
        region: str, network_insights_access_scope_analysis_id: str, max_results: int = 100
    ) -> dict[str, Any]:
        """Retrieve Network Access Analyzer scope analysis findings.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            network_insights_access_scope_analysis_id: The scope analysis
                to retrieve findings for.
            max_results: Maximum number of findings to return (bounded).
        """
        return execute_tool(
            tool_name="aws_get_network_insights_access_scope_analysis_findings",
            client_factory=client_factory,
            region=region,
            func=lambda: get_access_scope_analysis_findings(
                client_factory,
                region=region,
                network_insights_access_scope_analysis_id=network_insights_access_scope_analysis_id,
                max_results=max_results,
            ),
        )
