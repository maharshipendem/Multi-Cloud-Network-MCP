"""AWS service layer: network ACLs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.filters import ids_filter, vpc_filter
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import (
    NetworkAcl,
    NetworkAclAssociation,
    NetworkAclEntry,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_entry(raw: dict[str, Any]) -> NetworkAclEntry:
    port_range = raw.get("PortRange") or {}
    icmp = raw.get("IcmpTypeCode") or {}
    return NetworkAclEntry(
        rule_number=raw["RuleNumber"],
        protocol=raw.get("Protocol", "-1"),
        rule_action=raw.get("RuleAction", ""),
        egress=raw.get("Egress", False),
        cidr_block=raw.get("CidrBlock"),
        ipv6_cidr_block=raw.get("Ipv6CidrBlock"),
        icmp_type=icmp.get("Type"),
        icmp_code=icmp.get("Code"),
        port_range_from=port_range.get("From"),
        port_range_to=port_range.get("To"),
    )


def list_network_acls(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    network_acl_ids: list[str] | None = None,
) -> list[NetworkAcl]:
    """Call ec2:DescribeNetworkAcls and return the normalized list.

    Each ACL's ``entries`` are sorted by (``egress``, ``rule_number``) so
    the evaluation order that determines which rule actually applies is
    explicit in the output.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = vpc_filter(vpc_id) or ids_filter("network-acl-id", network_acl_ids)
    raw = paginate(
        client,
        "describe_network_acls",
        "NetworkAcls",
        max_items=settings.max_page_results,
        **filters,
    )
    acls = []
    for nacl in raw:
        entries = sorted(
            (_normalize_entry(e) for e in nacl.get("Entries", [])),
            key=lambda e: (e.egress, e.rule_number),
        )
        acls.append(
            NetworkAcl(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                network_acl_id=nacl["NetworkAclId"],
                vpc_id=nacl.get("VpcId", ""),
                is_default=nacl.get("IsDefault", False),
                entries=entries,
                associations=[
                    NetworkAclAssociation(
                        network_acl_association_id=a.get("NetworkAclAssociationId"),
                        subnet_id=a.get("SubnetId"),
                    )
                    for a in nacl.get("Associations", [])
                ],
                tags=normalize_tags(nacl.get("Tags")),
            )
        )
    return acls
