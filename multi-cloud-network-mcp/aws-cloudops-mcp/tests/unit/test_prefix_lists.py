from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.prefix_lists import list_managed_prefix_lists
from aws_cloudops_mcp.config import Settings


@pytest.fixture
def prefix_list_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        pl = ec2.create_managed_prefix_list(
            PrefixListName="test-pl",
            MaxEntries=10,
            AddressFamily="IPv4",
            Entries=[
                {"Cidr": "10.0.0.0/24", "Description": "office"},
                {"Cidr": "10.0.1.0/24", "Description": "vpn"},
            ],
        )["PrefixList"]
        yield {"prefix_list_id": pl["PrefixListId"]}


def test_list_managed_prefix_lists_without_entries(
    client_factory: ClientFactory, prefix_list_fixture: dict[str, str]
) -> None:
    result = list_managed_prefix_lists(client_factory, region="us-east-1")
    match = next(
        p for p in result.data if p.prefix_list_id == prefix_list_fixture["prefix_list_id"]
    )
    assert match.prefix_list_name == "test-pl"
    assert match.entries is None
    assert result.warnings == []


def test_list_managed_prefix_lists_with_entries(
    client_factory: ClientFactory, prefix_list_fixture: dict[str, str]
) -> None:
    result = list_managed_prefix_lists(client_factory, region="us-east-1", include_entries=True)
    match = next(
        p for p in result.data if p.prefix_list_id == prefix_list_fixture["prefix_list_id"]
    )
    assert match.entries is not None
    cidrs = {e.cidr for e in match.entries}
    assert cidrs == {"10.0.0.0/24", "10.0.1.0/24"}
    assert result.warnings == []


def test_list_managed_prefix_lists_respects_fanout_cap(
    prefix_list_fixture: dict[str, str],
) -> None:
    """With max_fanout_calls=0, entry enrichment must be skipped and
    recorded as a warning rather than silently omitted.

    A fresh moto account already has several AWS-managed prefix lists
    (e.g. com.amazonaws.<region>.s3), so this asserts on our specific
    fixture's prefix list rather than the total warning count.
    """
    settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
    client_factory = ClientFactory(settings, SessionManager(settings))

    result = list_managed_prefix_lists(client_factory, region="us-east-1", include_entries=True)
    match = next(
        p for p in result.data if p.prefix_list_id == prefix_list_fixture["prefix_list_id"]
    )
    assert match.entries is None
    assert all(w.code == "FANOUT_CAP_REACHED" for w in result.warnings)
    assert any(prefix_list_fixture["prefix_list_id"] in w.message for w in result.warnings)


def test_list_managed_prefix_lists_filters_by_id(
    client_factory: ClientFactory, prefix_list_fixture: dict[str, str]
) -> None:
    result = list_managed_prefix_lists(
        client_factory,
        region="us-east-1",
        prefix_list_ids=[prefix_list_fixture["prefix_list_id"]],
    )
    assert [p.prefix_list_id for p in result.data] == [prefix_list_fixture["prefix_list_id"]]


def test_list_managed_prefix_lists_zero_resources_for_unmatched_id(
    client_factory: ClientFactory,
) -> None:
    # A fresh moto account always has AWS-managed prefix lists (S3,
    # DynamoDB, ...), so "zero resources" is exercised via an ID filter
    # that matches nothing rather than a genuinely empty account.
    with mock_aws():
        result = list_managed_prefix_lists(
            client_factory, region="us-east-1", prefix_list_ids=["pl-doesnotexist"]
        )
        assert result.data == []
        assert result.warnings == []
