from __future__ import annotations

from azure_network_mcp.arm.collection import CollectionResult, now_iso, record_call, track_calls
from azure_network_mcp.models.common import CollectionWarning


def test_now_iso_returns_iso8601_utc_string() -> None:
    value = now_iso()
    assert "T" in value
    assert value.endswith("+00:00")


def test_record_call_is_a_noop_outside_track_calls() -> None:
    record_call()  # must not raise


def test_track_calls_counts_calls_within_the_block() -> None:
    with track_calls() as counter:
        assert counter.count == 0
        record_call()
        record_call()
        assert counter.count == 2


def test_track_calls_resets_after_the_block() -> None:
    with track_calls():
        record_call()
    record_call()  # outside any block again -- must not raise or affect anything


def test_track_calls_is_isolated_across_nested_or_sequential_blocks() -> None:
    with track_calls() as first:
        record_call()
    with track_calls() as second:
        record_call()
        record_call()
    assert first.count == 1
    assert second.count == 2


def test_collection_result_defaults_to_empty_warnings() -> None:
    result = CollectionResult(data=[1, 2, 3])
    assert result.data == [1, 2, 3]
    assert result.warnings == []


def test_collection_result_carries_warnings() -> None:
    warning = CollectionWarning(
        resource_type="resource_group", code="FANOUT_CAP_REACHED", message="m"
    )
    result = CollectionResult(data=[], warnings=[warning])
    assert result.warnings == [warning]
