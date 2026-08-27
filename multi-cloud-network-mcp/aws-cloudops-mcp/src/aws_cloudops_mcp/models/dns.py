"""Normalized models for Route 53 (global) and Route 53 Resolver (regional)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource

# --- Route 53 (global) ------------------------------------------------------


class HostedZone(AwsResource):
    """Normalized entry from route53:ListHostedZones.

    Global-scope (``scope="global"``) -- Route 53 has no regional
    endpoints. ``region`` is still populated (the bootstrap region the
    call was issued through) so callers filtering by ``region`` are
    unaffected; use ``scope`` to identify this as account-wide, not
    region-scoped.
    """

    hosted_zone_id: str
    name: str
    private_zone: bool = False
    record_set_count: int | None = None
    comment: str | None = None
    linked_vpc_ids: list[str] = Field(default_factory=list)


class ResourceRecordSetSummary(BaseModel):
    """One record set within a hosted zone.

    ``resource_records`` are the record values themselves (e.g. IP
    addresses, hostnames) -- these are DNS answers the zone already
    publishes to the internet/resolvers, not secret configuration, so no
    redaction is applied. Alias targets are captured separately since they
    reference other AWS resources rather than literal values.
    """

    name: str
    record_type: str
    ttl: int | None = None
    resource_records: list[str] = Field(default_factory=list)
    alias_target: str | None = None
    set_identifier: str | None = None
    # "simple" | "weighted" | "latency" | "failover" | "geo" | "multivalue"
    routing_policy: str | None = None


# --- Route 53 Resolver (regional) -------------------------------------------


class ResolverIpAddress(BaseModel):
    ip: str | None = None
    subnet_id: str | None = None
    status: str | None = None


class ResolverEndpoint(AwsResource):
    """Normalized entry from route53resolver:ListResolverEndpoints."""

    resolver_endpoint_id: str
    name: str | None = None
    status: str
    direction: str | None = None  # "INBOUND" | "OUTBOUND"
    host_vpc_id: str | None = None
    security_group_ids: list[str] = Field(default_factory=list)
    ip_addresses: list[ResolverIpAddress] = Field(default_factory=list)


class ResolverRuleTargetIp(BaseModel):
    ip: str | None = None
    port: int | None = None


class ResolverRule(AwsResource):
    """Normalized entry from route53resolver:ListResolverRules.

    ``rule_type`` is one of ``FORWARD`` (forwards queries for
    ``domain_name`` to ``target_ips``, the mechanism behind split-horizon
    DNS), ``SYSTEM`` (the default AWS-managed rule), or ``RECURSIVE``.
    """

    resolver_rule_id: str
    domain_name: str | None = None
    status: str
    rule_type: str | None = None
    resolver_endpoint_id: str | None = None
    target_ips: list[ResolverRuleTargetIp] = Field(default_factory=list)
    owner_id: str | None = None
    share_status: str | None = None  # "NOT_SHARED" | "SHARED_WITH_ME" | "SHARED_BY_ME"
    # None unless include_associations=True was passed to aws_list_resolver_rules.
    associated_vpc_ids: list[str] | None = None


class ResolverRuleAssociation(AwsResource):
    """Normalized entry from route53resolver:ListResolverRuleAssociations."""

    resolver_rule_association_id: str
    resolver_rule_id: str
    vpc_id: str | None = None
    status: str


class ResolverQueryLogConfig(AwsResource):
    """Normalized entry from route53resolver:ListResolverQueryLogConfigs.

    Metadata only (destination ARN, status) -- never the log contents
    themselves. Retrieving actual query log entries is explicitly out of
    scope for this milestone.
    """

    resolver_query_log_config_id: str
    name: str | None = None
    status: str
    destination_arn: str | None = None
    share_status: str | None = None


class DnsFirewallRuleGroup(AwsResource):
    """Normalized entry from route53resolver:ListFirewallRuleGroups.

    ``collection_completeness`` is set to ``"partial"`` (with a matching
    ``CollectionWarning``) rather than raising if this account lacks DNS
    Firewall permissions -- the milestone requires DNS Firewall visibility
    "where allowed," implying it is expected to be unavailable in some
    accounts.
    """

    firewall_rule_group_id: str
    name: str | None = None
    rule_count: int | None = None
    status: str | None = None
    owner_id: str | None = None
    share_status: str | None = None


class DnsFirewallRuleGroupAssociation(AwsResource):
    """Normalized entry from route53resolver:ListFirewallRuleGroupAssociations."""

    firewall_rule_group_association_id: str
    firewall_rule_group_id: str
    vpc_id: str | None = None
    priority: int | None = None
    mutation_protection: str | None = None
    status: str | None = None


__all__ = [
    "DnsFirewallRuleGroup",
    "DnsFirewallRuleGroupAssociation",
    "HostedZone",
    "ResolverEndpoint",
    "ResolverIpAddress",
    "ResolverQueryLogConfig",
    "ResolverRule",
    "ResolverRuleAssociation",
    "ResolverRuleTargetIp",
    "ResourceRecordSetSummary",
]
