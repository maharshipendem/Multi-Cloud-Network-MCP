from __future__ import annotations

from aws_cloudops_mcp.aws.tags import normalize_tags


def test_normalize_tags_basic() -> None:
    raw = [
        {"Key": "Name", "Value": "production-vpc"},
        {"Key": "Environment", "Value": "prod"},
    ]
    assert normalize_tags(raw) == {"Name": "production-vpc", "Environment": "prod"}


def test_normalize_tags_none() -> None:
    assert normalize_tags(None) == {}


def test_normalize_tags_empty_list() -> None:
    assert normalize_tags([]) == {}


def test_normalize_tags_missing_value_defaults_to_empty_string() -> None:
    assert normalize_tags([{"Key": "Name"}]) == {"Name": ""}


def test_normalize_tags_skips_entries_without_key() -> None:
    raw = [{"Value": "orphan"}, {"Key": "Name", "Value": "ok"}]
    assert normalize_tags(raw) == {"Name": "ok"}
