"""AWS service layer: internet gateways and egress-only internet gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import (
    EgressOnlyInternetGateway,
    InternetGateway,
    InternetGatewayAttachment,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_attachments(raw: list[dict[str, Any]]) -> list[InternetGatewayAttachment]:
    return [
        InternetGatewayAttachment(vpc_id=a["VpcId"], state=a.get("State"))
        for a in raw
        if a.get("VpcId")
    ]


def list_internet_gateways(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    internet_gateway_ids: list[str] | None = None,
) -> list[InternetGateway]:
    """Call ec2:DescribeInternetGateways and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters: dict[str, Any] = {}
    if vpc_id:
        filters = {"Filters": [{"Name": "attachment.vpc-id", "Values": [vpc_id]}]}
    elif internet_gateway_ids:
        filters = {"InternetGatewayIds": internet_gateway_ids}

    raw = paginate(
        client,
        "describe_internet_gateways",
        "InternetGateways",
        max_items=settings.max_page_results,
        **filters,
    )
    return [
        InternetGateway(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            internet_gateway_id=igw["InternetGatewayId"],
            owner_id=igw.get("OwnerId"),
            attachments=_normalize_attachments(igw.get("Attachments", [])),
            tags=normalize_tags(igw.get("Tags")),
        )
        for igw in raw
    ]


def list_egress_only_internet_gateways(
    client_factory: ClientFactory,
    *,
    region: str,
    egress_only_internet_gateway_ids: list[str] | None = None,
) -> list[EgressOnlyInternetGateway]:
    """Call ec2:DescribeEgressOnlyInternetGateways and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if egress_only_internet_gateway_ids:
        kwargs["EgressOnlyInternetGatewayIds"] = egress_only_internet_gateway_ids
    raw = paginate(
        client,
        "describe_egress_only_internet_gateways",
        "EgressOnlyInternetGateways",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        EgressOnlyInternetGateway(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            egress_only_internet_gateway_id=eigw["EgressOnlyInternetGatewayId"],
            attachments=_normalize_attachments(eigw.get("Attachments", [])),
            tags=normalize_tags(eigw.get("Tags")),
        )
        for eigw in raw
    ]
