"""AWS service layer: VPC Flow Log configurations.

Configuration and delivery metadata only -- see ``models/flowlogs.py``'s
module docstring. This module has no function, parameter, or code path
that retrieves flow log contents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.flowlogs import FlowLogConfig

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def list_flow_logs(
    client_factory: ClientFactory,
    *,
    region: str,
    resource_id: str | None = None,
    flow_log_ids: list[str] | None = None,
) -> list[FlowLogConfig]:
    """Call ec2:DescribeFlowLogs and return normalized configuration/delivery metadata."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if resource_id:
        # DescribeFlowLogs uses "Filter" (singular), not "Filters".
        kwargs["Filter"] = [{"Name": "resource-id", "Values": [resource_id]}]
    elif flow_log_ids:
        kwargs["FlowLogIds"] = flow_log_ids

    raw = paginate(
        client, "describe_flow_logs", "FlowLogs", max_items=settings.max_page_results, **kwargs
    )
    return [
        FlowLogConfig(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeFlowLogs",
            flow_log_id=fl["FlowLogId"],
            flow_log_status=fl.get("FlowLogStatus"),
            resource_id=fl.get("ResourceId", ""),
            traffic_type=fl.get("TrafficType"),
            log_destination_type=fl.get("LogDestinationType"),
            log_destination=fl.get("LogDestination"),
            log_group_name=fl.get("LogGroupName"),
            deliver_logs_status=fl.get("DeliverLogsStatus"),
            deliver_logs_error_message=fl.get("DeliverLogsErrorMessage"),
            log_format=fl.get("LogFormat"),
            max_aggregation_interval=fl.get("MaxAggregationInterval"),
            tags=normalize_tags(fl.get("Tags")),
        )
        for fl in raw
    ]
