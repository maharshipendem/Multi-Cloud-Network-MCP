"""Normalized model for VPC Flow Log configurations.

Configuration and delivery metadata only. There is no tool, model field,
or code path in this codebase that retrieves flow log *contents* (the
actual traffic records written to CloudWatch Logs/S3/Kinesis Firehose) --
that is an explicit, unconditional guardrail for this milestone, not an
opt-in choice.
"""

from __future__ import annotations

from aws_cloudops_mcp.models.common import AwsResource


class FlowLogConfig(AwsResource):
    """Normalized entry from ec2:DescribeFlowLogs."""

    flow_log_id: str
    flow_log_status: str | None = None
    resource_id: str
    traffic_type: str | None = None
    log_destination_type: str | None = None  # "cloud-watch-logs" | "s3" | "kinesis-data-firehose"
    log_destination: str | None = None
    log_group_name: str | None = None
    deliver_logs_status: str | None = None
    deliver_logs_error_message: str | None = None
    log_format: str | None = None
    max_aggregation_interval: int | None = None


__all__ = ["FlowLogConfig"]
