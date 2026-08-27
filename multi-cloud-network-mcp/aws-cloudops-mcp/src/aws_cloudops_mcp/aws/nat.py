"""AWS service layer: NAT gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import NatGateway, NatGatewayAddress

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def list_nat_gateways(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    subnet_id: str | None = None,
    nat_gateway_ids: list[str] | None = None,
) -> list[NatGateway]:
    """Call ec2:DescribeNatGateways and return the normalized list.

    Deleted NAT gateways stay visible in AWS for a time with
    ``state="deleted"``; they are included here rather than filtered out so
    a caller can distinguish "never existed" from "recently removed."
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filter_pairs = [
        ("vpc-id", [vpc_id] if vpc_id else None),
        ("subnet-id", [subnet_id] if subnet_id else None),
    ]
    filters = [{"Name": name, "Values": values} for name, values in filter_pairs if values]
    kwargs: dict[str, Any] = {}
    if filters:
        kwargs["Filter"] = filters  # DescribeNatGateways uses "Filter", not "Filters"
    if nat_gateway_ids:
        kwargs["NatGatewayIds"] = nat_gateway_ids

    raw = paginate(
        client,
        "describe_nat_gateways",
        "NatGateways",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        NatGateway(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            nat_gateway_id=nat["NatGatewayId"],
            vpc_id=nat.get("VpcId", ""),
            subnet_id=nat.get("SubnetId"),
            state=nat.get("State", ""),
            connectivity_type=nat.get("ConnectivityType"),
            addresses=[
                NatGatewayAddress(
                    allocation_id=a.get("AllocationId"),
                    network_interface_id=a.get("NetworkInterfaceId"),
                    private_ip=a.get("PrivateIp"),
                    public_ip=a.get("PublicIp"),
                    is_primary=a.get("IsPrimary"),
                    status=a.get("Status"),
                )
                for a in nat.get("NatGatewayAddresses", [])
            ],
            failure_code=nat.get("FailureCode"),
            failure_message=nat.get("FailureMessage"),
            tags=normalize_tags(nat.get("Tags")),
        )
        for nat in raw
    ]
