"""MCP tool: aws_list_flow_logs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.flowlogs import list_flow_logs
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_flow_logs"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List VPC Flow Log configurations and delivery/aggregation "
            "metadata, optionally filtered by resource ID "
            "(ec2:DescribeFlowLogs). Never retrieves log contents -- this "
            "tool has no such capability, opt-in or otherwise."
        ),
        meta=capability_meta(resource_types=["flow_log"]),
    )
    def aws_list_flow_logs(
        region: str, resource_id: str | None = None, flow_log_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List VPC Flow Log configurations.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            resource_id: Optional VPC/subnet/ENI ID to restrict results to.
            flow_log_ids: Optional list of flow log IDs (ignored if
                ``resource_id`` is also given).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_flow_logs(
                client_factory, region=region, resource_id=resource_id, flow_log_ids=flow_log_ids
            ),
        )
