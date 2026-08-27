"""AWS service layer: elastic network interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.filters import ids_filter, vpc_filter
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import (
    NetworkInterface,
    NetworkInterfaceAttachment,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def list_network_interfaces(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    subnet_id: str | None = None,
    network_interface_ids: list[str] | None = None,
) -> list[NetworkInterface]:
    """Call ec2:DescribeNetworkInterfaces and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = (
        vpc_filter(vpc_id)
        or ids_filter("subnet-id", [subnet_id] if subnet_id else None)
        or ids_filter("network-interface-id", network_interface_ids)
    )
    raw = paginate(
        client,
        "describe_network_interfaces",
        "NetworkInterfaces",
        max_items=settings.max_page_results,
        **filters,
    )
    result = []
    for eni in raw:
        attachment_raw = eni.get("Attachment") or {}
        attachment = (
            NetworkInterfaceAttachment(
                attachment_id=attachment_raw.get("AttachmentId"),
                instance_id=attachment_raw.get("InstanceId"),
                device_index=attachment_raw.get("DeviceIndex"),
                status=attachment_raw.get("Status"),
                delete_on_termination=attachment_raw.get("DeleteOnTermination"),
            )
            if attachment_raw
            else None
        )
        result.append(
            NetworkInterface(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                network_interface_id=eni["NetworkInterfaceId"],
                subnet_id=eni.get("SubnetId"),
                vpc_id=eni.get("VpcId"),
                description=eni.get("Description"),
                status=eni.get("Status"),
                interface_type=eni.get("InterfaceType"),
                private_ip_address=eni.get("PrivateIpAddress"),
                private_ip_addresses=[
                    p["PrivateIpAddress"]
                    for p in eni.get("PrivateIpAddresses", [])
                    if p.get("PrivateIpAddress")
                ],
                public_ip=(eni.get("Association") or {}).get("PublicIp"),
                security_group_ids=[
                    g["GroupId"] for g in eni.get("Groups", []) if g.get("GroupId")
                ],
                attachment=attachment,
                requester_managed=eni.get("RequesterManaged", False),
                requester_id=eni.get("RequesterId"),
                tags=normalize_tags(eni.get("TagSet")),
            )
        )
    return result
