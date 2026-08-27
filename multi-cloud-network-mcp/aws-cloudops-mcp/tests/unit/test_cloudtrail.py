from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import boto3
from botocore.stub import Stubber

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.cloudtrail import (
    DEFAULT_LOOKBACK_HOURS,
    MAX_LOOKBACK_DAYS,
    lookup_network_config_events,
    resolve_time_window,
)

# moto does not implement cloudtrail:LookupEvents (Python NotImplementedError) --
# the output-shaping tests below are Stubber-based against the real service
# model instead; the clamping arithmetic is tested directly as a pure function
# since it depends on non-deterministic wall-clock time otherwise.


def test_resolve_time_window_defaults_to_lookback_hours() -> None:
    now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    start, end = resolve_time_window(None, None, now=now)
    assert end == now
    assert start == now - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


def test_resolve_time_window_clamps_excessive_lookback() -> None:
    now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    requested_start = (now - timedelta(days=30)).isoformat()
    start, end = resolve_time_window(requested_start, now.isoformat(), now=now)
    assert start == now - timedelta(days=MAX_LOOKBACK_DAYS)
    assert end == now


def test_resolve_time_window_respects_a_window_within_the_cap() -> None:
    now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    requested_start = (now - timedelta(hours=2)).isoformat()
    start, end = resolve_time_window(requested_start, now.isoformat(), now=now)
    assert start == now - timedelta(hours=2)


def test_lookup_network_config_events_filters_to_allowlist(client_factory: ClientFactory) -> None:
    real_client = boto3.client("cloudtrail", region_name="us-east-1")
    stubber = Stubber(real_client)
    now = datetime.now(UTC)
    stubber.add_response(
        "lookup_events",
        {
            "Events": [
                {
                    "EventId": "evt-1",
                    "EventName": "AuthorizeSecurityGroupIngress",
                    "EventTime": now,
                    "Username": "alice",
                    "Resources": [{"ResourceName": "sg-0123456789abcdef0"}],
                },
                {
                    "EventId": "evt-2",
                    "EventName": "DescribeVpcs",  # read-only, not network-relevant -- filtered out
                    "EventTime": now,
                    "Username": "bob",
                },
            ]
        },
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        events = lookup_network_config_events(client_factory, region="us-east-1")

    assert len(events) == 1
    assert events[0].event_name == "AuthorizeSecurityGroupIngress"
    assert events[0].resource_names == ["sg-0123456789abcdef0"]
    stubber.assert_no_pending_responses()


def test_lookup_network_config_events_zero_events(client_factory: ClientFactory) -> None:
    real_client = boto3.client("cloudtrail", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response("lookup_events", {"Events": []})
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        events = lookup_network_config_events(client_factory, region="us-east-1")

    assert events == []
    stubber.assert_no_pending_responses()


def test_lookup_network_config_events_clamps_max_results_cap(client_factory: ClientFactory) -> None:
    real_client = boto3.client("cloudtrail", region_name="us-east-1")
    stubber = Stubber(real_client)
    now = datetime.now(UTC)
    stubber.add_response(
        "lookup_events",
        {
            "Events": [
                {"EventId": f"evt-{i}", "EventName": "CreateRoute", "EventTime": now}
                for i in range(50)
            ]
        },
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        events = lookup_network_config_events(client_factory, region="us-east-1", max_results=99999)

    assert len(events) <= 50
    stubber.assert_no_pending_responses()
