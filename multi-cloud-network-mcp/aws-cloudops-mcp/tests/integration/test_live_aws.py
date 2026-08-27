"""Integration tests against a real AWS account.

These are NOT run by default (see the ``addopts = "-m 'not integration'"``
setting in pyproject.toml). Run them explicitly with valid AWS credentials
available (env vars, a profile, or an assumable role) via:

    pytest -m integration

Each test is read-only and safe to run against a real account, but does
require actual AWS API access and will incur normal AWS API request costs
(typically negligible/free for Describe*/Get* calls).
"""

from __future__ import annotations

import re

import pytest

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.accounts import get_caller_identity
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.networking import list_route_tables, list_subnets, list_vpcs
from aws_cloudops_mcp.aws.regions import list_regions
from aws_cloudops_mcp.config import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_client_factory() -> ClientFactory:
    settings = get_settings()
    return ClientFactory(settings, SessionManager(settings))


def test_get_caller_identity_against_real_aws(live_client_factory: ClientFactory) -> None:
    identity = get_caller_identity(live_client_factory)
    assert re.fullmatch(r"\d{12}", identity.account_id)
    assert identity.arn.startswith("arn:aws:")


def test_list_regions_against_real_aws(live_client_factory: ClientFactory) -> None:
    regions = list_regions(live_client_factory)
    assert any(r.region_name == "us-east-1" for r in regions)


def test_list_vpcs_against_real_aws(live_client_factory: ClientFactory) -> None:
    vpcs = list_vpcs(live_client_factory, region=get_settings().aws_default_region)
    assert isinstance(vpcs, list)  # may legitimately be empty


def test_list_subnets_against_real_aws(live_client_factory: ClientFactory) -> None:
    subnets = list_subnets(live_client_factory, region=get_settings().aws_default_region)
    assert isinstance(subnets, list)


def test_list_route_tables_against_real_aws(live_client_factory: ClientFactory) -> None:
    route_tables = list_route_tables(live_client_factory, region=get_settings().aws_default_region)
    assert isinstance(route_tables, list)
