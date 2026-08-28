from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from google.api import metric_pb2, monitored_resource_pb2
from google.cloud import monitoring_v3
from google.cloud.logging_v2.types import ListLogEntriesRequest, LogEntry
from google.logging.type import log_severity_pb2
from google.protobuf.struct_pb2 import Struct
from tests.conftest import PROJECT_ID, FakePager

from gcp_network_mcp.exceptions import InvalidConfigurationError
from gcp_network_mcp.gcp.observability import (
    _MAX_PAYLOAD_CHARS,
    _normalize_log_entry,
    _normalize_time_series,
    _render_payload,
    _typed_value,
    query_logs,
    query_metrics,
)


def _time_series(
    points: list[float], *, metric_type: str = "compute.googleapis.com/x"
) -> monitoring_v3.TimeSeries:
    interval = monitoring_v3.TimeInterval(
        start_time=datetime(2026, 1, 1, tzinfo=UTC), end_time=datetime(2026, 1, 1, 1, tzinfo=UTC)
    )
    return monitoring_v3.TimeSeries(
        metric=metric_pb2.Metric(type=metric_type, labels={"instance": "vm-1"}),
        resource=monitored_resource_pb2.MonitoredResource(
            type="gce_instance", labels={"zone": "us-central1-a"}
        ),
        points=[
            monitoring_v3.Point(interval=interval, value=monitoring_v3.TypedValue(double_value=v))
            for v in points
        ],
    )


# --- _render_payload ------------------------------------------------------------


def test_render_payload_text_payload_within_bound() -> None:
    entry = LogEntry(text_payload="hello world")
    assert _render_payload(entry) == "hello world"


def test_render_payload_text_payload_truncated_at_max_chars() -> None:
    long_text = "x" * (_MAX_PAYLOAD_CHARS + 500)
    entry = LogEntry(text_payload=long_text)
    rendered = _render_payload(entry)
    assert rendered is not None
    assert len(rendered) == _MAX_PAYLOAD_CHARS
    assert rendered == long_text[:_MAX_PAYLOAD_CHARS]


def test_render_payload_json_payload_serialized_and_truncated() -> None:
    struct = Struct()
    struct.update({"message": "x" * (_MAX_PAYLOAD_CHARS + 500)})
    entry = LogEntry(json_payload=struct)
    rendered = _render_payload(entry)
    assert rendered is not None
    assert len(rendered) == _MAX_PAYLOAD_CHARS


def test_render_payload_proto_payload_renders_type_url_only() -> None:
    entry = LogEntry(proto_payload={"type_url": "type.googleapis.com/google.foo.Bar", "value": b""})
    assert _render_payload(entry) == "<proto_payload type_url=type.googleapis.com/google.foo.Bar>"


def test_render_payload_returns_none_when_no_payload_set() -> None:
    assert _render_payload(LogEntry()) is None


# --- _normalize_log_entry --------------------------------------------------------


def test_normalize_log_entry_maps_fields() -> None:
    entry = LogEntry(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        severity=log_severity_pb2.LogSeverity.ERROR,
        log_name="projects/p/logs/x",
        resource={"type": "gce_instance"},
        insert_id="abc123",
        text_payload="boom",
    )
    summary = _normalize_log_entry(entry)
    assert summary.timestamp == entry.timestamp.rfc3339()
    assert summary.severity == "ERROR"
    assert summary.log_name == "projects/p/logs/x"
    assert summary.resource_type == "gce_instance"
    assert summary.insert_id == "abc123"
    assert summary.payload == "boom"


def test_normalize_log_entry_degrades_unset_fields_to_none() -> None:
    summary = _normalize_log_entry(LogEntry())
    assert summary.timestamp is None
    assert summary.severity == "DEFAULT"
    assert summary.log_name is None
    assert summary.resource_type is None
    assert summary.insert_id is None
    assert summary.payload is None


# --- query_logs -------------------------------------------------------------------


def test_query_logs_calls_list_log_entries_with_request_only_and_no_flattened_kwargs(
    client_factory, settings
) -> None:
    """gapic's ``list_log_entries`` raises ``ValueError`` if called with a
    mix of ``request=`` and flattened kwargs -- a real bug once present
    here. Every field this call needs (including ``page_size``, only
    settable via the request object) must go through a single
    ``ListLogEntriesRequest``, so the underlying call must be invoked
    with exactly ``request=`` and nothing else."""
    entry = LogEntry(text_payload="hi")
    client_factory.logs().list_log_entries.return_value = FakePager(
        [SimpleNamespace(entries=[entry])]
    )

    query_logs(client_factory, settings, project_id=PROJECT_ID, filter_expr='severity>="ERROR"')

    call = client_factory.logs().list_log_entries.call_args
    assert call.args == ()
    assert set(call.kwargs.keys()) == {"request"}
    request = call.kwargs["request"]
    assert isinstance(request, ListLogEntriesRequest)
    assert request.resource_names == [f"projects/{PROJECT_ID}"]
    assert 'severity>="ERROR"' in request.filter
    assert "timestamp>=" in request.filter
    assert request.order_by == "timestamp desc"
    assert request.page_size == min(settings.max_log_entries, 1000)


def test_query_logs_normalizes_entries_and_reports_bounded_filter(client_factory, settings) -> None:
    entry = LogEntry(text_payload="hi", severity=log_severity_pb2.LogSeverity.WARNING)
    client_factory.logs().list_log_entries.return_value = FakePager(
        [SimpleNamespace(entries=[entry])]
    )

    result = query_logs(
        client_factory, settings, project_id=PROJECT_ID, filter_expr="resource.type=x"
    )

    assert result.project_id == PROJECT_ID
    assert "resource.type=x" in result.filter_expr
    assert len(result.entries) == 1
    assert result.entries[0].payload == "hi"
    assert result.truncated is False


def test_query_logs_empty_results(client_factory, settings) -> None:
    client_factory.logs().list_log_entries.return_value = FakePager([SimpleNamespace(entries=[])])
    result = query_logs(client_factory, settings, project_id=PROJECT_ID, filter_expr="x")
    assert result.entries == []
    assert result.truncated is False


def test_query_logs_truncated_flag_set_when_max_entries_reached(client_factory, settings) -> None:
    settings.max_log_entries = 2
    entries = [LogEntry(text_payload=f"entry-{i}") for i in range(2)]
    client_factory.logs().list_log_entries.return_value = FakePager(
        [SimpleNamespace(entries=entries)]
    )

    result = query_logs(client_factory, settings, project_id=PROJECT_ID, filter_expr="x")
    assert len(result.entries) == 2
    assert result.truncated is True


def test_query_logs_caps_window_at_settings_max_regardless_of_requested_hours(
    client_factory, settings
) -> None:
    settings.max_log_query_window_hours = 2.0
    client_factory.logs().list_log_entries.return_value = FakePager([SimpleNamespace(entries=[])])

    before = datetime.now(UTC)
    query_logs(client_factory, settings, project_id=PROJECT_ID, filter_expr="x", hours=1000)
    after = datetime.now(UTC)

    request = client_factory.logs().list_log_entries.call_args.kwargs["request"]
    match = re.search(r'timestamp>="([^"]+)"', request.filter)
    assert match is not None
    since = datetime.fromisoformat(match.group(1))
    assert before - timedelta(hours=2, seconds=5) <= since <= after - timedelta(hours=2, seconds=-5)


def test_query_logs_rejects_non_positive_hours(client_factory, settings) -> None:
    with pytest.raises(InvalidConfigurationError):
        query_logs(client_factory, settings, project_id=PROJECT_ID, filter_expr="x", hours=-1)


# --- _typed_value -----------------------------------------------------------------


def test_typed_value_double() -> None:
    assert _typed_value(monitoring_v3.TypedValue(double_value=3.5)) == 3.5


def test_typed_value_int64_coerced_to_float() -> None:
    value = _typed_value(monitoring_v3.TypedValue(int64_value=42))
    assert value == 42.0
    assert isinstance(value, float)


def test_typed_value_bool_coerced_to_float() -> None:
    assert _typed_value(monitoring_v3.TypedValue(bool_value=True)) == 1.0


def test_typed_value_unset_returns_none() -> None:
    assert _typed_value(monitoring_v3.TypedValue()) is None


# --- _normalize_time_series --------------------------------------------------------


def test_normalize_time_series_maps_fields() -> None:
    series = _time_series([1.0, 2.0, 3.0])
    summary = _normalize_time_series(series, max_points=10)
    assert summary.metric_type == "compute.googleapis.com/x"
    assert summary.resource_type == "gce_instance"
    assert summary.resource_labels == {"zone": "us-central1-a"}
    assert summary.metric_labels == {"instance": "vm-1"}
    assert [p.value for p in summary.points] == [1.0, 2.0, 3.0]
    assert summary.points[0].start_time is not None
    assert summary.points[0].end_time is not None


def test_normalize_time_series_caps_points_at_max_points() -> None:
    series = _time_series([1.0, 2.0, 3.0, 4.0, 5.0])
    summary = _normalize_time_series(series, max_points=2)
    assert len(summary.points) == 2


# --- query_metrics ------------------------------------------------------------------


def test_query_metrics_calls_list_time_series_with_expected_kwargs(
    client_factory, settings
) -> None:
    client_factory.metrics().list_time_series.return_value = FakePager(
        [SimpleNamespace(time_series=[])]
    )
    query_metrics(client_factory, settings, project_id=PROJECT_ID, filter_expr='metric.type="x"')

    call = client_factory.metrics().list_time_series.call_args
    assert call.kwargs["name"] == f"projects/{PROJECT_ID}"
    assert call.kwargs["filter"] == 'metric.type="x"'
    assert isinstance(call.kwargs["interval"], monitoring_v3.TimeInterval)
    assert call.kwargs["view"] == monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL


def test_query_metrics_normalizes_series(client_factory, settings) -> None:
    series = _time_series([1.0, 2.0])
    client_factory.metrics().list_time_series.return_value = FakePager(
        [SimpleNamespace(time_series=[series])]
    )
    result = query_metrics(client_factory, settings, project_id=PROJECT_ID, filter_expr="x")
    assert len(result.time_series) == 1
    assert [p.value for p in result.time_series[0].points] == [1.0, 2.0]
    assert result.truncated is False


def test_query_metrics_empty_results(client_factory, settings) -> None:
    client_factory.metrics().list_time_series.return_value = FakePager(
        [SimpleNamespace(time_series=[])]
    )
    result = query_metrics(client_factory, settings, project_id=PROJECT_ID, filter_expr="x")
    assert result.time_series == []
    assert result.truncated is False


def test_query_metrics_caps_total_points_at_settings_max_time_series_points(
    client_factory, settings
) -> None:
    settings.max_time_series_points = 2
    series1 = _time_series([1.0, 2.0])
    series2 = _time_series([3.0, 4.0])
    client_factory.metrics().list_time_series.return_value = FakePager(
        [SimpleNamespace(time_series=[series1, series2])]
    )

    result = query_metrics(client_factory, settings, project_id=PROJECT_ID, filter_expr="x")

    total_points = sum(len(ts.points) for ts in result.time_series)
    assert total_points == 2
    assert result.truncated is True


def test_query_metrics_rejects_non_positive_hours(client_factory, settings) -> None:
    with pytest.raises(InvalidConfigurationError):
        query_metrics(client_factory, settings, project_id=PROJECT_ID, filter_expr="x", hours=-1)
