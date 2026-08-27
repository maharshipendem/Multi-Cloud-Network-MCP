"""AWS service layer: security groups and their rules.

Group metadata comes from ``DescribeSecurityGroups``; rules come from the
newer ``DescribeSecurityGroupRules`` (rather than the legacy nested
``IpPermissions``/``IpPermissionsEgress`` blocks) because it is the only
API that gives each rule a stable ``SecurityGroupRuleId``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.filters import ids_filter, vpc_filter
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import (
    SecurityGroup,
    SecurityGroupRule,
    SecurityGroupRulePeer,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_peer(raw: dict[str, Any]) -> SecurityGroupRulePeer:
    if raw.get("CidrIpv4"):
        return SecurityGroupRulePeer(type="ipv4", value=raw["CidrIpv4"])
    if raw.get("CidrIpv6"):
        return SecurityGroupRulePeer(type="ipv6", value=raw["CidrIpv6"])
    if raw.get("PrefixListId"):
        return SecurityGroupRulePeer(type="prefix_list", value=raw["PrefixListId"])
    group = raw.get("ReferencedGroupInfo") or {}
    if group.get("GroupId"):
        return SecurityGroupRulePeer(
            type="security_group",
            value=group["GroupId"],
            referenced_group_id=group.get("GroupId"),
            referenced_vpc_id=group.get("VpcId"),
            referenced_owner_id=group.get("UserId"),
        )
    return SecurityGroupRulePeer(type="unknown", value="")


def _normalize_rule(
    raw: dict[str, Any], *, account_id: str, region: str, observed_at: str
) -> SecurityGroupRule:
    return SecurityGroupRule(
        account_id=account_id,
        region=region,
        observed_at=observed_at,
        security_group_rule_id=raw["SecurityGroupRuleId"],
        security_group_id=raw["GroupId"],
        vpc_id=raw.get("VpcId"),
        is_egress=raw.get("IsEgress", False),
        ip_protocol=raw.get("IpProtocol", "-1"),
        from_port=raw.get("FromPort"),
        to_port=raw.get("ToPort"),
        peer=_normalize_peer(raw),
        description=raw.get("Description"),
        tags=normalize_tags(raw.get("Tags")),
    )


def list_security_group_rules(
    client_factory: ClientFactory,
    *,
    region: str,
    security_group_ids: list[str] | None = None,
) -> list[SecurityGroupRule]:
    """Call ec2:DescribeSecurityGroupRules and return the normalized list.

    Sorted by (``security_group_id``, ``is_egress``, ``security_group_rule_id``)
    for deterministic output.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if security_group_ids:
        kwargs["Filters"] = [{"Name": "group-id", "Values": security_group_ids}]

    raw = paginate(
        client,
        "describe_security_group_rules",
        "SecurityGroupRules",
        max_items=settings.max_page_results,
        **kwargs,
    )
    rules = [
        _normalize_rule(r, account_id=account_id, region=region, observed_at=observed_at)
        for r in raw
    ]
    rules.sort(key=lambda r: (r.security_group_id, r.is_egress, r.security_group_rule_id))
    return rules


def list_security_groups(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    security_group_ids: list[str] | None = None,
) -> list[SecurityGroup]:
    """Call ec2:DescribeSecurityGroups (+ DescribeSecurityGroupRules) and join them.

    One extra call is made to fetch rules for exactly the groups returned
    by the first call (via a ``group-id`` filter), not one call per group,
    so this stays a two-call operation regardless of how many groups exist.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    filters = vpc_filter(vpc_id) or ids_filter("group-id", security_group_ids)
    raw_groups = paginate(
        client,
        "describe_security_groups",
        "SecurityGroups",
        max_items=settings.max_page_results,
        **filters,
    )
    group_ids = [g["GroupId"] for g in raw_groups]
    rules_by_group: dict[str, list[SecurityGroupRule]] = {}
    if group_ids:
        for rule in list_security_group_rules(
            client_factory, region=region, security_group_ids=group_ids
        ):
            rules_by_group.setdefault(rule.security_group_id, []).append(rule)

    return [
        SecurityGroup(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            group_id=g["GroupId"],
            group_name=g.get("GroupName", ""),
            description=g.get("Description"),
            vpc_id=g.get("VpcId"),
            owner_id=g.get("OwnerId"),
            rules=rules_by_group.get(g["GroupId"], []),
            tags=normalize_tags(g.get("Tags")),
        )
        for g in raw_groups
    ]
