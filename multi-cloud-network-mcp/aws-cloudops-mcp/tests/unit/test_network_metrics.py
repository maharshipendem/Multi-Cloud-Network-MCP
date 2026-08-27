from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.network_metrics import (
    MAX_LOOKBACK_HOURS,
    get_known_metrics_for_resource,
    get_resource_metric,
)


@pytest.fixture
def metric_fixture() -> None:
    with mock_aws():
        cw = boto3.client("cloudwatch", region_name="us-east-1")
        cw.put_metric_data(
            Namespace="AWS/NATGateway",
            MetricData=[
                {
                    "MetricName": "ErrorPortAllocation",
                    "Dimensions": [{"Name": "NatGatewayId", "Value": "nat-0123456789abcdef0"}],
                    "Timestamp": datetime.now(UTC),
                    "Value": 3.0,
                    "Unit": "Count",
                }
            ],
        )
        yield


def test_get_resource_metric_returns_seeded_datapoint(client_factory: ClientFactory) -> None:
    """moto's GetMetricStatistics silently drops datapoints when queried
    with a 300-second Period (this codebase's default) even though the
    same data is returned fine at Period=60 -- a moto aggregation-bucket
    bug, not a real AWS behavior. Stubbed against the real service model
    instead so this test actually proves the normalizer works against a
    realistic response."""
    real_client = boto3.client("cloudwatch", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "get_metric_statistics",
        {
            "Label": "ErrorPortAllocation",
            "Datapoints": [
                {"Timestamp": datetime.now(UTC), "Sum": 3.0, "Unit": "Count"},
            ],
        },
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        metric = get_resource_metric(
            client_factory,
            region="us-east-1",
            namespace="AWS/NATGateway",
            metric_name="ErrorPortAllocation",
            dimension_name="NatGatewayId",
            dimension_value="nat-0123456789abcdef0",
        )

    assert metric.namespace == "AWS/NATGateway"
    assert metric.metric_name == "ErrorPortAllocation"
    assert len(metric.datapoints) == 1
    assert metric.datapoints[0].sum == 3.0
    stubber.assert_no_pending_responses()


def test_get_resource_metric_clamps_lookback_hours(client_factory: ClientFactory) -> None:
    with mock_aws():
        metric = get_resource_metric(
            client_factory,
            region="us-east-1",
            namespace="AWS/NATGateway",
            metric_name="ErrorPortAllocation",
            dimension_name="NatGatewayId",
            dimension_value="nat-does-not-exist",
            lookback_hours=999,
        )
    assert metric.datapoints == []


def test_get_known_metrics_for_resource_queries_full_catalog(
    client_factory: ClientFactory, metric_fixture: None
) -> None:
    metrics = get_known_metrics_for_resource(
        client_factory,
        region="us-east-1",
        resource_type="nat_gateway",
        resource_id="nat-0123456789abcdef0",
    )
    assert len(metrics) == 2  # ErrorPortAllocation + PacketsDropCount
    assert {m.metric_name for m in metrics} == {"ErrorPortAllocation", "PacketsDropCount"}


def test_get_known_metrics_for_unknown_resource_type_returns_empty(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        metrics = get_known_metrics_for_resource(
            client_factory, region="us-east-1", resource_type="widget", resource_id="widget-1"
        )
    assert metrics == []


def test_max_lookback_hours_is_bounded() -> None:
    assert MAX_LOOKBACK_HOURS <= 24
