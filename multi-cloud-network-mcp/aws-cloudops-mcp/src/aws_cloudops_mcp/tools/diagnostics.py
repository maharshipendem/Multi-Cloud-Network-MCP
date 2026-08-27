"""MCP tools: aws_explain_network_path, aws_find_network_risks, aws_get_network_health.

Every tool here collects a fresh :class:`~aws_cloudops_mcp.diagnostics.snapshot.NetworkSnapshot`
via ``aws.snapshot.collect_network_snapshot`` and hands it to the
boto3-independent ``diagnostics.*`` engine -- these tool functions
themselves do nothing but wire inputs through and let
``tools._shared.execute_tool`` handle the response envelope, exactly like
every other tool in this codebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.network_health import get_network_health
from aws_cloudops_mcp.aws.snapshot import collect_network_snapshot
from aws_cloudops_mcp.diagnostics.explain import explain_network_path
from aws_cloudops_mcp.diagnostics.models import Severity
from aws_cloudops_mcp.diagnostics.risks import find_network_risks
from aws_cloudops_mcp.exceptions import ToolExecutionError
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

EXPLAIN_PATH_TOOL_NAME = "aws_explain_network_path"
FIND_RISKS_TOOL_NAME = "aws_find_network_risks"
GET_HEALTH_TOOL_NAME = "aws_get_network_health"

_VALID_SEVERITIES: tuple[Severity, ...] = ("critical", "high", "medium", "low", "info")


def _validate_min_severity(min_severity: str | None) -> Severity | None:
    if min_severity is None:
        return None
    if min_severity not in _VALID_SEVERITIES:
        raise ToolExecutionError(
            f"Invalid min_severity '{min_severity}'; must be one of {_VALID_SEVERITIES}."
        )
    return min_severity


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=EXPLAIN_PATH_TOOL_NAME,
        description=(
            "Explain whether traffic from a source (subnet, ENI, or IP) can "
            "reach a destination IP/CIDR: deterministic route resolution "
            "(longest-prefix match across local/NAT/peering/TGW/gateway/"
            "endpoint/blackhole targets) combined with security group "
            "(stateful) and network ACL (stateless, all four legs) "
            "evaluation where enough information is given to evaluate "
            "them. Every conclusion carries severity, confidence, "
            "evidence, and reasoning steps; when required evidence is "
            "missing, the result says INDETERMINATE rather than guessing. "
            "Never claims certainty from incomplete data and never "
            "changes any AWS configuration."
        ),
        meta=capability_meta(resource_types=["network_path_explanation"]),
    )
    def aws_explain_network_path(
        region: str,
        destination: str,
        source_subnet_id: str | None = None,
        source_eni_id: str | None = None,
        source_ip: str | None = None,
        vpc_id: str | None = None,
        destination_eni_id: str | None = None,
        destination_ip: str | None = None,
        protocol: str = "tcp",
        port: int | None = None,
        include_transit_gateway: bool = False,
    ) -> dict[str, Any]:
        """Explain the routing/security path from a source to a destination.

        Args:
            region: AWS region to analyze, e.g. "us-east-1".
            destination: Destination IP address or CIDR block.
            source_subnet_id: Source subnet ID (one of source_subnet_id/
                source_eni_id/source_ip+vpc_id is required).
            source_eni_id: Source elastic network interface ID.
            source_ip: Source IP address (requires vpc_id).
            vpc_id: VPC the source_ip belongs to, if source_ip is given.
            destination_eni_id: Destination ENI, if known -- enables
                security group ingress evaluation on the destination side.
            destination_ip: Destination IP, if different from a bare
                destination CIDR -- used to resolve NACL/security group
                evaluation.
            protocol: IP protocol, e.g. "tcp", "udp", "icmp". Defaults to "tcp".
            port: Destination port, if applicable.
            include_transit_gateway: Also collect Transit Gateway route
                tables/routes so a path through a TGW can be resolved
                (bounded, opt-in -- adds AWS API calls).
        """

        def _run() -> Any:
            snapshot = collect_network_snapshot(
                client_factory, region=region, include_transit_gateway=include_transit_gateway
            )
            return explain_network_path(
                snapshot,
                destination=destination,
                source_subnet_id=source_subnet_id,
                source_eni_id=source_eni_id,
                source_ip=source_ip,
                vpc_id=vpc_id,
                destination_eni_id=destination_eni_id,
                destination_ip=destination_ip,
                protocol=protocol,
                port=port,
            )

        return execute_tool(
            tool_name=EXPLAIN_PATH_TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=_run,
        )

    @mcp.tool(
        name=FIND_RISKS_TOOL_NAME,
        description=(
            "Scan a region (optionally scoped to specific VPCs) for "
            "network misconfigurations: CIDR overlap, orphaned/"
            "unpropagated Transit Gateway attachments, asymmetric VPC "
            "peering routes, degraded/failed resource states, and "
            "internet-exposed ENIs/load balancers (distinguishing "
            "potential exposure from proven reachability). Returns every "
            "finding checked, including informational ones, unless "
            "min_severity filters them out -- 'not evaluated' never "
            "looks the same as 'checked, nothing found.' Read-only; "
            "never modifies any resource."
        ),
        meta=capability_meta(resource_types=["network_risk_finding"]),
    )
    def aws_find_network_risks(
        region: str,
        vpc_ids: list[str] | None = None,
        min_severity: str | None = None,
        include_transit_gateway: bool = False,
    ) -> dict[str, Any]:
        """Find network configuration risks across a region.

        Args:
            region: AWS region to analyze, e.g. "us-east-1".
            vpc_ids: Restrict the scan to these VPC IDs; omit for the
                whole region.
            min_severity: Drop findings less severe than this threshold
                ("critical", "high", "medium", "low", "info"); omit to
                get every finding, including informational ones.
            include_transit_gateway: Also collect Transit Gateway
                attachments/route tables so TGW-related risks (orphaned
                attachments, missing propagation) can be checked.
        """

        def _run() -> Any:
            snapshot = collect_network_snapshot(
                client_factory,
                region=region,
                vpc_ids=vpc_ids,
                include_transit_gateway=include_transit_gateway,
            )
            return find_network_risks(snapshot, min_severity=_validate_min_severity(min_severity))

        return execute_tool(
            tool_name=FIND_RISKS_TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=_run,
        )

    @mcp.tool(
        name=GET_HEALTH_TOOL_NAME,
        description=(
            "Report network resource health: degraded/failed NAT "
            "gateways, Transit Gateway attachments, and VPN tunnels; "
            "which VPCs have no Flow Log configured; and, opt-in, "
            "bounded CloudWatch metrics for NAT gateways, existing "
            "Reachability Analyzer results that found no path or "
            "failed, and recent (capped, read-only) CloudTrail network-"
            "configuration events. Never enables Flow Logs, never "
            "creates a Reachability Analyzer path/analysis, and never "
            "retrieves log record contents."
        ),
        meta=capability_meta(resource_types=["network_health_report"]),
    )
    def aws_get_network_health(
        region: str,
        vpc_ids: list[str] | None = None,
        include_metrics: bool = False,
        include_reachability_analyses: bool = False,
        include_recent_changes: bool = False,
    ) -> dict[str, Any]:
        """Report network resource health for a region.

        Args:
            region: AWS region to analyze, e.g. "us-east-1".
            vpc_ids: Restrict the report to these VPC IDs; omit for the
                whole region.
            include_metrics: Fetch bounded, opt-in CloudWatch metrics for
                NAT gateways (adds AWS API calls, bounded by
                max_fanout_calls).
            include_reachability_analyses: List existing Reachability
                Analyzer analyses and surface any that found no path or
                failed (never creates a new analysis).
            include_recent_changes: Look up recent (capped) CloudTrail
                network-configuration events.
        """
        return execute_tool(
            tool_name=GET_HEALTH_TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: get_network_health(
                client_factory,
                region=region,
                vpc_ids=vpc_ids,
                include_metrics=include_metrics,
                include_reachability_analyses=include_reachability_analyses,
                include_recent_changes=include_recent_changes,
            ),
        )
