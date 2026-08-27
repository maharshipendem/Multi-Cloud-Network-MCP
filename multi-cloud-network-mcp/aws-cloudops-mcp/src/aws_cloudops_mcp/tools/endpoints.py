"""MCP tools: aws_list_vpc_endpoints, aws_list_vpc_endpoint_services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.endpoints import list_vpc_endpoint_services, list_vpc_endpoints
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_VPC_ENDPOINTS = "aws_list_vpc_endpoints"
_LIST_VPC_ENDPOINT_SERVICES = "aws_list_vpc_endpoint_services"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VPC_ENDPOINTS,
        description=(
            "List VPC endpoints in a region, optionally filtered by VPC "
            "(ec2:DescribeVpcEndpoints). Policy documents are omitted "
            "unless include_policies is set, and are size-capped/truncated "
            "even then."
        ),
        meta=capability_meta(resource_types=["vpc_endpoint"]),
    )
    def aws_list_vpc_endpoints(
        region: str,
        vpc_id: str | None = None,
        vpc_endpoint_ids: list[str] | None = None,
        include_policies: bool = False,
    ) -> dict[str, Any]:
        """List VPC endpoints.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            vpc_endpoint_ids: Optional list of VPC endpoint IDs.
            include_policies: If true, include each endpoint's policy
                document (redacted/size-capped -- see
                ``policy_document_truncated`` on each record).
        """
        return execute_tool(
            tool_name=_LIST_VPC_ENDPOINTS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpc_endpoints(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                vpc_endpoint_ids=vpc_endpoint_ids,
                include_policies=include_policies,
            ),
        )

    @mcp.tool(
        name=_LIST_VPC_ENDPOINT_SERVICES,
        description=(
            "List VPC endpoint services visible to this account/region -- "
            "AWS-provided services plus any of the account's own endpoint "
            "service configurations (ec2:DescribeVpcEndpointServices)."
        ),
        meta=capability_meta(resource_types=["vpc_endpoint_service"]),
    )
    def aws_list_vpc_endpoint_services(region: str) -> dict[str, Any]:
        """List VPC endpoint services.

        Args:
            region: AWS region to query, e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_VPC_ENDPOINT_SERVICES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpc_endpoint_services(client_factory, region=region),
        )
