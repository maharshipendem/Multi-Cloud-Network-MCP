"""MCP tool: aws_list_load_balancers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.loadbalancers import list_load_balancers
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_load_balancers"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List Application/Network/Gateway load balancers in a region, "
            "optionally filtered by VPC (elbv2:DescribeLoadBalancers), each "
            "joined with its listeners (elbv2:DescribeListeners) and target "
            "groups (elbv2:DescribeTargetGroups)."
        ),
        meta=capability_meta(resource_types=["load_balancer", "target_group"]),
    )
    def aws_list_load_balancers(
        region: str,
        vpc_id: str | None = None,
        load_balancer_arns: list[str] | None = None,
        include_target_health: bool = False,
    ) -> dict[str, Any]:
        """List load balancers.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            load_balancer_arns: Optional list of load balancer ARNs.
            include_target_health: If true, also fetch each target group's
                target health (1 extra API call per target group, bounded
                and best-effort -- see warnings in the response metadata if
                any fetch fails or the fan-out cap is reached).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_load_balancers(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                load_balancer_arns=load_balancer_arns,
                include_target_health=include_target_health,
            ),
        )
