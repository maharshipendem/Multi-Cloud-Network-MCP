from __future__ import annotations

import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.regions import list_regions, validate_region_format
from aws_cloudops_mcp.exceptions import InvalidRegionError


@pytest.mark.parametrize(
    "region",
    ["us-east-1", "eu-west-2", "ap-southeast-3", "us-gov-west-1", "sa-east-1"],
)
def test_validate_region_format_accepts_known_shapes(region: str) -> None:
    validate_region_format(region)  # must not raise


@pytest.mark.parametrize("region", ["", "not-a-region", "US-EAST-1", "us-east", "useast1"])
def test_validate_region_format_rejects_invalid_shapes(region: str) -> None:
    with pytest.raises(InvalidRegionError):
        validate_region_format(region)


@mock_aws
def test_list_regions_returns_normalized_entries(client_factory: ClientFactory) -> None:
    regions = list_regions(client_factory)

    assert len(regions) > 0
    names = {r.region_name for r in regions}
    assert "us-east-1" in names
    first = regions[0]
    assert first.region_name
    assert first.endpoint is not None


@mock_aws
def test_list_regions_rejects_malformed_region(client_factory: ClientFactory) -> None:
    with pytest.raises(InvalidRegionError):
        list_regions(client_factory, region="not-a-region")
