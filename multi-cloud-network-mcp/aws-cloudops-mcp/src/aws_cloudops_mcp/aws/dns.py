"""AWS service layer: Route 53 (global) and Route 53 Resolver (regional).

Route 53 itself has no regional API -- ``list_hosted_zones`` is called
through whatever regional endpoint the client factory builds (boto3
resolves it to Route 53's single global endpoint regardless), and every
``HostedZone`` record is stamped ``scope="global"``. Resolver, and DNS
Firewall (part of the Resolver API), are genuinely regional.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.dns import (
    DnsFirewallRuleGroup,
    DnsFirewallRuleGroupAssociation,
    HostedZone,
    ResolverEndpoint,
    ResolverIpAddress,
    ResolverQueryLogConfig,
    ResolverRule,
    ResolverRuleAssociation,
    ResolverRuleTargetIp,
    ResourceRecordSetSummary,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

DEFAULT_MAX_RECORD_SETS = 300


def list_hosted_zones(client_factory: ClientFactory, *, region: str) -> list[HostedZone]:
    """Call route53:ListHostedZones and return the normalized list (global scope)."""
    validate_region_format(region)
    client = client_factory.get_client("route53", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(client, "list_hosted_zones", "HostedZones", max_items=settings.max_page_results)
    result = []
    for zone in raw:
        config = zone.get("Config", {})
        linked_vpc_ids: list[str] = []
        if config.get("PrivateZone"):
            try:
                detail = call_readonly(client, "get_hosted_zone", Id=zone["Id"])
                linked_vpc_ids = [v["VPCId"] for v in detail.get("VPCs", []) if v.get("VPCId")]
            except ClientError:
                pass  # best-effort; zone is still returned without VPC links
        result.append(
            HostedZone(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="route53:ListHostedZones",
                hosted_zone_id=zone["Id"].removeprefix("/hostedzone/"),
                name=zone.get("Name", ""),
                private_zone=config.get("PrivateZone", False),
                record_set_count=zone.get("ResourceRecordSetCount"),
                comment=config.get("Comment"),
                linked_vpc_ids=linked_vpc_ids,
                tags={},
            )
        )
    return result


def list_resource_record_sets(
    client_factory: ClientFactory,
    *,
    region: str,
    hosted_zone_id: str,
    max_record_sets: int = DEFAULT_MAX_RECORD_SETS,
) -> CollectionResult:
    """Call route53:ListResourceRecordSets for one zone, capped at ``max_record_sets``.

    A zone can hold an unbounded number of record sets; this is the
    milestone's "bound ... hosted-zone record retrieval" requirement. If
    the cap is reached before the zone is exhausted, a
    ``CollectionWarning`` is returned alongside the (partial) list.
    """
    validate_region_format(region)
    client = client_factory.get_client("route53", region=region)
    capped = min(max_record_sets, 1000)

    raw = paginate(
        client,
        "list_resource_record_sets",
        "ResourceRecordSets",
        max_items=capped,
        HostedZoneId=hosted_zone_id,
    )
    warnings: list[CollectionWarning] = []
    if len(raw) >= capped:
        warnings.append(
            CollectionWarning(
                resource_type="resource_record_set",
                code="OUTPUT_CAP_REACHED",
                message=(
                    f"Hosted zone {hosted_zone_id} may have more record sets than the "
                    f"{capped}-record cap for a single call; results are truncated."
                ),
            )
        )

    record_sets = [
        ResourceRecordSetSummary(
            name=rr.get("Name", ""),
            record_type=rr.get("Type", ""),
            ttl=rr.get("TTL"),
            resource_records=[r.get("Value", "") for r in rr.get("ResourceRecords", [])],
            alias_target=(rr.get("AliasTarget") or {}).get("DNSName"),
            set_identifier=rr.get("SetIdentifier"),
            routing_policy=_routing_policy(rr),
        )
        for rr in raw
    ]
    return CollectionResult(data=record_sets, warnings=warnings)


def _routing_policy(raw: dict[str, Any]) -> str | None:
    if "Weight" in raw:
        return "weighted"
    if "Region" in raw:
        return "latency"
    if "Failover" in raw:
        return "failover"
    if "GeoLocation" in raw:
        return "geo"
    if "MultiValueAnswer" in raw:
        return "multivalue"
    if "SetIdentifier" in raw:
        return None  # policy present but not one of the above (e.g. geoproximity)
    return "simple"


def list_resolver_endpoints(
    client_factory: ClientFactory, *, region: str
) -> list[ResolverEndpoint]:
    """Call route53resolver:ListResolverEndpoints and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        max_items=settings.max_page_results,
    )
    result = []
    for ep in raw:
        ip_response = call_readonly(
            client, "list_resolver_endpoint_ip_addresses", ResolverEndpointId=ep["Id"]
        )
        result.append(
            ResolverEndpoint(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="route53resolver:ListResolverEndpoints",
                resolver_endpoint_id=ep["Id"],
                name=ep.get("Name"),
                status=ep.get("Status", ""),
                direction=ep.get("Direction"),
                host_vpc_id=ep.get("HostVPCId"),
                security_group_ids=ep.get("SecurityGroupIds", []),
                ip_addresses=[
                    ResolverIpAddress(
                        ip=ip.get("Ip"), subnet_id=ip.get("SubnetId"), status=ip.get("Status")
                    )
                    for ip in ip_response.get("IpAddresses", [])
                ],
            )
        )
    return result


def list_resolver_rules(
    client_factory: ClientFactory, *, region: str, include_associations: bool = False
) -> CollectionResult:
    """Call route53resolver:ListResolverRules and return the normalized list.

    ``include_associations`` opts into one extra ``ListResolverRuleAssociations``
    call per rule (bounded by ``Settings.max_fanout_calls``) to show which
    VPCs each rule is actually associated with -- the mechanism behind
    split-horizon DNS (a private zone plus a forwarding rule scoped to
    specific VPCs).
    """
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client, "list_resolver_rules", "ResolverRules", max_items=settings.max_page_results
    )
    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    rules = []
    for rule in raw:
        rule_id = rule["Id"]
        associated_vpc_ids: list[str] | None = None
        if include_associations:
            if fanout_budget > 0:
                assoc_response = call_readonly(
                    client,
                    "list_resolver_rule_associations",
                    Filters=[{"Name": "ResolverRuleId", "Values": [rule_id]}],
                )
                fanout_budget -= 1
                associated_vpc_ids = [
                    a["VPCId"]
                    for a in assoc_response.get("ResolverRuleAssociations", [])
                    if a.get("VPCId")
                ]
            else:
                warnings.append(
                    CollectionWarning(
                        resource_type="resolver_rule_association",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"Skipped association lookup for {rule_id}: "
                            f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                        ),
                    )
                )

        rules.append(
            ResolverRule(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="route53resolver:ListResolverRules",
                resolver_rule_id=rule_id,
                domain_name=rule.get("DomainName"),
                status=rule.get("Status", ""),
                rule_type=rule.get("RuleType"),
                resolver_endpoint_id=rule.get("ResolverEndpointId"),
                target_ips=[
                    ResolverRuleTargetIp(ip=t.get("Ip"), port=t.get("Port"))
                    for t in rule.get("TargetIps", [])
                ],
                owner_id=rule.get("OwnerId"),
                share_status=rule.get("ShareStatus"),
                associated_vpc_ids=associated_vpc_ids,
            )
        )

    return CollectionResult(data=rules, warnings=warnings)


def list_resolver_rule_associations(
    client_factory: ClientFactory, *, region: str, resolver_rule_id: str | None = None
) -> list[ResolverRuleAssociation]:
    """Call route53resolver:ListResolverRuleAssociations and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if resolver_rule_id:
        kwargs["Filters"] = [{"Name": "ResolverRuleId", "Values": [resolver_rule_id]}]

    raw = paginate(
        client,
        "list_resolver_rule_associations",
        "ResolverRuleAssociations",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        ResolverRuleAssociation(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="route53resolver:ListResolverRuleAssociations",
            resolver_rule_association_id=a["Id"],
            resolver_rule_id=a.get("ResolverRuleId", ""),
            vpc_id=a.get("VPCId"),
            status=a.get("Status", ""),
        )
        for a in raw
    ]


def list_resolver_query_log_configs(
    client_factory: ClientFactory, *, region: str
) -> list[ResolverQueryLogConfig]:
    """Call route53resolver:ListResolverQueryLogConfigs -- metadata only,
    never log contents."""
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "list_resolver_query_log_configs",
        "ResolverQueryLogConfigs",
        max_items=settings.max_page_results,
    )
    return [
        ResolverQueryLogConfig(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="route53resolver:ListResolverQueryLogConfigs",
            resolver_query_log_config_id=c["Id"],
            name=c.get("Name"),
            status=c.get("Status", ""),
            destination_arn=c.get("DestinationArn"),
            share_status=c.get("ShareStatus"),
        )
        for c in raw
    ]


def list_dns_firewall_rule_groups(
    client_factory: ClientFactory, *, region: str
) -> CollectionResult:
    """Call route53resolver:ListFirewallRuleGroups -- best-effort.

    DNS Firewall is a distinct, separately-permissioned capability within
    the Resolver API; the milestone asks for it "where allowed." A denied
    call degrades to an empty list with a ``CollectionWarning`` rather
    than failing the whole tool call.
    """
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    try:
        raw = paginate(
            client,
            "list_firewall_rule_groups",
            "FirewallRuleGroups",
            max_items=settings.max_page_results,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return CollectionResult(
            data=[],
            warnings=[
                CollectionWarning(
                    resource_type="dns_firewall_rule_group",
                    code="ACCESS_DENIED" if "Denied" in code or "Access" in code else "UNAVAILABLE",
                    message=f"Could not list DNS Firewall rule groups: {code}.",
                )
            ],
        )

    groups = [
        DnsFirewallRuleGroup(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="route53resolver:ListFirewallRuleGroups",
            firewall_rule_group_id=g["Id"],
            name=g.get("Name"),
            rule_count=g.get("RuleCount"),
            status=g.get("Status"),
            owner_id=g.get("OwnerId"),
            share_status=g.get("ShareStatus"),
        )
        for g in raw
    ]
    return CollectionResult(data=groups, warnings=[])


def list_dns_firewall_rule_group_associations(
    client_factory: ClientFactory, *, region: str, vpc_id: str | None = None
) -> CollectionResult:
    """Call route53resolver:ListFirewallRuleGroupAssociations -- best-effort,
    same access-denied degradation as ``list_dns_firewall_rule_groups``."""
    validate_region_format(region)
    client = client_factory.get_client("route53resolver", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if vpc_id:
        kwargs["VpcId"] = vpc_id

    try:
        raw = paginate(
            client,
            "list_firewall_rule_group_associations",
            "FirewallRuleGroupAssociations",
            max_items=settings.max_page_results,
            **kwargs,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return CollectionResult(
            data=[],
            warnings=[
                CollectionWarning(
                    resource_type="dns_firewall_rule_group_association",
                    code="ACCESS_DENIED" if "Denied" in code or "Access" in code else "UNAVAILABLE",
                    message=f"Could not list DNS Firewall rule group associations: {code}.",
                )
            ],
        )

    associations = [
        DnsFirewallRuleGroupAssociation(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="route53resolver:ListFirewallRuleGroupAssociations",
            firewall_rule_group_association_id=a["Id"],
            firewall_rule_group_id=a.get("FirewallRuleGroupId", ""),
            vpc_id=a.get("VpcId"),
            priority=a.get("Priority"),
            mutation_protection=a.get("MutationProtection"),
            status=a.get("Status"),
        )
        for a in raw
    ]
    return CollectionResult(data=associations, warnings=[])
