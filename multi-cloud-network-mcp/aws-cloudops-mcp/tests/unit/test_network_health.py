from __future__ import annotations

import boto3
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.network_health import get_network_health


def test_get_network_health_flags_failed_nat_and_missing_flow_logs(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        nat = ec2.create_nat_gateway(SubnetId=subnet["SubnetId"], ConnectivityType="public")[
            "NatGateway"
        ]
        ec2.delete_nat_gateway(NatGatewayId=nat["NatGatewayId"])

        report = get_network_health(client_factory, region="us-east-1")

    assert report.region == "us-east-1"
    assert vpc["VpcId"] in report.vpcs_without_flow_logs
    # no metrics/reachability/changes requested -> all opt-in sections empty
    assert report.metrics == []
    assert report.unhealthy_reachability_analyses == []
    assert report.recent_config_changes == []


def test_get_network_health_flow_log_configured_vpc_not_flagged(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        logs = boto3.client("logs", region_name="us-east-1")
        logs.create_log_group(logGroupName="/vpc/flow-logs")
        ec2.create_flow_logs(
            ResourceIds=[vpc["VpcId"]],
            ResourceType="VPC",
            TrafficType="ALL",
            LogDestinationType="cloud-watch-logs",
            LogGroupName="/vpc/flow-logs",
            DeliverLogsPermissionArn="arn:aws:iam::123456789012:role/flow-logs-role",
        )

        report = get_network_health(client_factory, region="us-east-1")

    assert vpc["VpcId"] not in report.vpcs_without_flow_logs


def test_get_network_health_zero_resources(client_factory: ClientFactory) -> None:
    """A fresh moto account has a default VPC per region (like real AWS)
    -- "zero resources" here means zero degraded resources, not a
    literally empty VPC/flow-log-coverage list."""
    with mock_aws():
        report = get_network_health(client_factory, region="us-east-1")
    assert report.degraded_resources == []
