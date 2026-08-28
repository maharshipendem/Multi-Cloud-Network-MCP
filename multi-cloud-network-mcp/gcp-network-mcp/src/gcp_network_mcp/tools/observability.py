"""MCP tools: gcp_query_logs, gcp_query_metrics -- explicit-opt-in,
narrowly-bounded Cloud Logging/Monitoring reads. Never a general-purpose
log/metric browser: every call requires an explicit filter and is capped
on result count and time window regardless of what the caller requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.observability import query_logs, query_metrics
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.config import Settings
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_QUERY_LOGS = "gcp_query_logs"
_QUERY_METRICS = "gcp_query_metrics"


def register(
    mcp: MCPServer,
    client_factory: ClientFactory,
    resource_context: ResourceContext,
    settings: Settings,
) -> None:
    @mcp.tool(
        name=_QUERY_LOGS,
        description=(
            "Explicit-opt-in, narrowly-bounded Cloud Logging read: requires a filter "
            "expression, capped on entry count and lookback window regardless of what is "
            "requested. Never a general-purpose log browser."
        ),
        meta=capability_meta(resource_types=["log_entry"]),
    )
    def gcp_query_logs(
        filter_expr: str, project_id: str | None = None, hours: float | None = None
    ) -> dict[str, Any]:
        """Query Cloud Logging entries.

        Args:
            filter_expr: Required Cloud Logging filter expression.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hours: Lookback window in hours. Capped at
                Settings.max_log_query_window_hours.
        """
        return execute_tool_with_resolved_project(
            tool_name=_QUERY_LOGS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: query_logs(
                client_factory,
                settings,
                project_id=resolved,
                filter_expr=filter_expr,
                hours=hours,
            ),
        )

    @mcp.tool(
        name=_QUERY_METRICS,
        description=(
            "Explicit-opt-in, narrowly-bounded Cloud Monitoring read: requires a filter "
            "expression, capped on total data points and lookback window regardless of what "
            "is requested. Never a general-purpose metric browser."
        ),
        meta=capability_meta(resource_types=["time_series"]),
    )
    def gcp_query_metrics(
        filter_expr: str, project_id: str | None = None, hours: float | None = None
    ) -> dict[str, Any]:
        """Query Cloud Monitoring time series.

        Args:
            filter_expr: Required Cloud Monitoring filter expression
                (e.g. metric.type="compute.googleapis.com/instance/network/received_bytes_count").
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hours: Lookback window in hours. Capped at
                Settings.max_metric_query_window_hours.
        """
        return execute_tool_with_resolved_project(
            tool_name=_QUERY_METRICS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: query_metrics(
                client_factory,
                settings,
                project_id=resolved,
                filter_expr=filter_expr,
                hours=hours,
            ),
        )
