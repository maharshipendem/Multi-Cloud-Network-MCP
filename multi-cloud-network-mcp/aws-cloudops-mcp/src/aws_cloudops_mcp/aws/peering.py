"""AWS service layer: VPC peering connections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import VpcPeeringConnection, VpcPeeringPeer

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_peer(raw: dict[str, Any] | None) -> VpcPeeringPeer:
    raw = raw or {}
    cidr_blocks = [c["CidrBlock"] for c in raw.get("CidrBlockSet", []) if c.get("CidrBlock")] or (
        [raw["CidrBlock"]] if raw.get("CidrBlock") else []
    )
    return VpcPeeringPeer(
        vpc_id=raw.get("VpcId"),
        owner_id=raw.get("OwnerId"),
        region=raw.get("Region"),
        cidr_blocks=cidr_blocks,
    )


def list_vpc_peering_connections(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    vpc_peering_connection_ids: list[str] | None = None,
) -> list[VpcPeeringConnection]:
    """Call ec2:DescribeVpcPeeringConnections and return the normalized list.

    ``vpc_id`` matches this VPC as either the requester or the accepter.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if vpc_id:
        kwargs["Filters"] = [
            {"Name": "requester-vpc-info.vpc-id", "Values": [vpc_id]},
        ]
    elif vpc_peering_connection_ids:
        kwargs["VpcPeeringConnectionIds"] = vpc_peering_connection_ids

    raw = paginate(
        client,
        "describe_vpc_peering_connections",
        "VpcPeeringConnections",
        max_items=settings.max_page_results,
        **kwargs,
    )

    # A vpc_id filter above only matched the requester side; also fetch the
    # accepter-side matches and merge (a VPC is equally "peered" either way).
    if vpc_id:
        accepter_raw = paginate(
            client,
            "describe_vpc_peering_connections",
            "VpcPeeringConnections",
            max_items=settings.max_page_results,
            Filters=[{"Name": "accepter-vpc-info.vpc-id", "Values": [vpc_id]}],
        )
        seen_ids = {p["VpcPeeringConnectionId"] for p in raw}
        raw.extend(p for p in accepter_raw if p["VpcPeeringConnectionId"] not in seen_ids)

    return [
        VpcPeeringConnection(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            vpc_peering_connection_id=p["VpcPeeringConnectionId"],
            status_code=(p.get("Status") or {}).get("Code"),
            status_message=(p.get("Status") or {}).get("Message"),
            requester=_normalize_peer(p.get("RequesterVpcInfo")),
            accepter=_normalize_peer(p.get("AccepterVpcInfo")),
            tags=normalize_tags(p.get("Tags")),
        )
        for p in raw
    ]
