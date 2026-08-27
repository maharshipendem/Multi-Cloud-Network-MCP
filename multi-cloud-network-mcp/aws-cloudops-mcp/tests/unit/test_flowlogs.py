from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.flowlogs import list_flow_logs


@pytest.fixture
def flow_log_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        logs = boto3.client("logs", region_name="us-east-1")
        logs.create_log_group(logGroupName="/vpc/flow-logs")
        fl = ec2.create_flow_logs(
            ResourceIds=[vpc["VpcId"]],
            ResourceType="VPC",
            TrafficType="ALL",
            LogDestinationType="cloud-watch-logs",
            LogGroupName="/vpc/flow-logs",
            DeliverLogsPermissionArn="arn:aws:iam::123456789012:role/flow-logs-role",
        )
        yield {"vpc_id": vpc["VpcId"], "flow_log_id": fl["FlowLogIds"][0]}


def test_list_flow_logs_normalizes_configuration_metadata(
    client_factory: ClientFactory, flow_log_fixture: dict[str, str]
) -> None:
    logs = list_flow_logs(client_factory, region="us-east-1")
    match = next(f for f in logs if f.flow_log_id == flow_log_fixture["flow_log_id"])
    assert match.resource_id == flow_log_fixture["vpc_id"]
    assert match.traffic_type == "ALL"
    assert match.log_destination_type == "cloud-watch-logs"
    assert match.log_group_name == "/vpc/flow-logs"


def test_list_flow_logs_never_exposes_log_contents(
    client_factory: ClientFactory, flow_log_fixture: dict[str, str]
) -> None:
    """The normalized model has no field that could hold log record
    contents -- confirm by field name inspection, not just absence in one
    fixture's data."""
    logs = list_flow_logs(client_factory, region="us-east-1")
    match = next(f for f in logs if f.flow_log_id == flow_log_fixture["flow_log_id"])
    field_names = set(type(match).model_fields.keys())
    assert not any("content" in f.lower() or "record" in f.lower() for f in field_names)


def test_list_flow_logs_filters_by_resource_id(
    client_factory: ClientFactory, flow_log_fixture: dict[str, str]
) -> None:
    logs = list_flow_logs(
        client_factory, region="us-east-1", resource_id=flow_log_fixture["vpc_id"]
    )
    assert [f.flow_log_id for f in logs] == [flow_log_fixture["flow_log_id"]]


def test_list_flow_logs_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_flow_logs(client_factory, region="us-east-1") == []
