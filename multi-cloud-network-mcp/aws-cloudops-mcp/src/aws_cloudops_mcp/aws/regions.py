"""AWS service layer: region discovery and validation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.exceptions import InvalidRegionError
from aws_cloudops_mcp.models.common import RegionInfo

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# Matches standard AWS region identifiers, e.g. us-east-1, eu-west-2,
# us-gov-west-1, ap-southeast-3. This is a fast, offline sanity check --
# it does not guarantee the region exists or is enabled for the account.
_REGION_PATTERN = re.compile(r"^[a-z]{2}(-gov|-iso[a-z]?)?-[a-z]+-\d$")


def validate_region_format(region: str) -> None:
    """Raise ``InvalidRegionError`` if ``region`` is not a well-formed AWS region."""
    if not region or not _REGION_PATTERN.match(region):
        raise InvalidRegionError(f"'{region}' is not a valid AWS region identifier.")


def list_regions(client_factory: ClientFactory, *, region: str | None = None) -> list[RegionInfo]:
    """Call ec2:DescribeRegions and return the normalized region list.

    ``region`` selects which regional EC2 endpoint issues the (global-scope)
    call; it defaults to the server's configured default region.
    """
    bootstrap_region = region or client_factory.settings.aws_default_region
    validate_region_format(bootstrap_region)

    client = client_factory.get_client("ec2", region=bootstrap_region)
    response = call_readonly(client, "describe_regions", AllRegions=False)
    return [
        RegionInfo(
            region_name=entry["RegionName"],
            endpoint=entry.get("Endpoint"),
            opt_in_status=entry.get("OptInStatus"),
        )
        for entry in response.get("Regions", [])
    ]
