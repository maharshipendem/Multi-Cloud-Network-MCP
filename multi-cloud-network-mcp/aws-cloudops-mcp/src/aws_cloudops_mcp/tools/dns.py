"""MCP tools: Route 53 hosted zones/record sets, Resolver, and DNS Firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.dns import (
    DEFAULT_MAX_RECORD_SETS,
    list_dns_firewall_rule_group_associations,
    list_dns_firewall_rule_groups,
    list_hosted_zones,
    list_resolver_endpoints,
    list_resolver_query_log_configs,
    list_resolver_rule_associations,
    list_resolver_rules,
    list_resource_record_sets,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_HOSTED_ZONES = "aws_list_hosted_zones"
_LIST_RECORD_SETS = "aws_list_resource_record_sets"
_LIST_RESOLVER_ENDPOINTS = "aws_list_resolver_endpoints"
_LIST_RESOLVER_RULES = "aws_list_resolver_rules"
_LIST_RESOLVER_RULE_ASSOCIATIONS = "aws_list_resolver_rule_associations"
_LIST_RESOLVER_QUERY_LOG_CONFIGS = "aws_list_resolver_query_log_configs"
_LIST_DNS_FIREWALL_RULE_GROUPS = "aws_list_dns_firewall_rule_groups"
_LIST_DNS_FIREWALL_RULE_GROUP_ASSOCIATIONS = "aws_list_dns_firewall_rule_group_associations"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_HOSTED_ZONES,
        description=(
            "List Route 53 hosted zones (global scope), including linked VPC "
            "IDs for private zones (route53:ListHostedZones+GetHostedZone)."
        ),
        meta=capability_meta(resource_types=["hosted_zone"]),
    )
    def aws_list_hosted_zones(region: str) -> dict[str, Any]:
        """List Route 53 hosted zones.

        Args:
            region: Region whose endpoint issues the call (Route 53 itself
                has no regional API), e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_HOSTED_ZONES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_hosted_zones(client_factory, region=region),
        )

    @mcp.tool(
        name=_LIST_RECORD_SETS,
        description=(
            "List record-set summaries for one hosted zone, bounded by "
            f"max_record_sets (default {DEFAULT_MAX_RECORD_SETS}, capped at "
            "1000) (route53:ListResourceRecordSets)."
        ),
        meta=capability_meta(resource_types=["resource_record_set"]),
    )
    def aws_list_resource_record_sets(
        region: str, hosted_zone_id: str, max_record_sets: int = DEFAULT_MAX_RECORD_SETS
    ) -> dict[str, Any]:
        """List a hosted zone's record sets.

        Args:
            region: Region whose endpoint issues the call, e.g. "us-east-1".
            hosted_zone_id: The hosted zone to list record sets for.
            max_record_sets: Maximum record sets to return (bounded output cap).
        """
        return execute_tool(
            tool_name=_LIST_RECORD_SETS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_resource_record_sets(
                client_factory,
                region=region,
                hosted_zone_id=hosted_zone_id,
                max_record_sets=max_record_sets,
            ),
        )

    @mcp.tool(
        name=_LIST_RESOLVER_ENDPOINTS,
        description="List Route 53 Resolver endpoints (route53resolver:ListResolverEndpoints).",
        meta=capability_meta(resource_types=["resolver_endpoint"]),
    )
    def aws_list_resolver_endpoints(region: str) -> dict[str, Any]:
        """List Resolver endpoints.

        Args:
            region: AWS region to query, e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_RESOLVER_ENDPOINTS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_resolver_endpoints(client_factory, region=region),
        )

    @mcp.tool(
        name=_LIST_RESOLVER_RULES,
        description=(
            "List Route 53 Resolver rules (forwarding rules behind split-"
            "horizon DNS), optionally with their VPC associations "
            "(route53resolver:ListResolverRules+ListResolverRuleAssociations)."
        ),
        meta=capability_meta(resource_types=["resolver_rule"]),
    )
    def aws_list_resolver_rules(region: str, include_associations: bool = False) -> dict[str, Any]:
        """List Resolver rules.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            include_associations: If true, also fetch each rule's associated
                VPC IDs (1 extra API call per rule, bounded and best-effort).
        """
        return execute_tool(
            tool_name=_LIST_RESOLVER_RULES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_resolver_rules(
                client_factory, region=region, include_associations=include_associations
            ),
        )

    @mcp.tool(
        name=_LIST_RESOLVER_RULE_ASSOCIATIONS,
        description=(
            "List Resolver rule-to-VPC associations, optionally filtered by "
            "rule (route53resolver:ListResolverRuleAssociations)."
        ),
        meta=capability_meta(resource_types=["resolver_rule_association"]),
    )
    def aws_list_resolver_rule_associations(
        region: str, resolver_rule_id: str | None = None
    ) -> dict[str, Any]:
        """List Resolver rule associations.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            resolver_rule_id: Optional Resolver rule ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_RESOLVER_RULE_ASSOCIATIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_resolver_rule_associations(
                client_factory, region=region, resolver_rule_id=resolver_rule_id
            ),
        )

    @mcp.tool(
        name=_LIST_RESOLVER_QUERY_LOG_CONFIGS,
        description=(
            "List Resolver query logging configurations -- metadata only "
            "(destination, status); never log contents "
            "(route53resolver:ListResolverQueryLogConfigs)."
        ),
        meta=capability_meta(resource_types=["resolver_query_log_config"]),
    )
    def aws_list_resolver_query_log_configs(region: str) -> dict[str, Any]:
        """List Resolver query log configurations.

        Args:
            region: AWS region to query, e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_RESOLVER_QUERY_LOG_CONFIGS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_resolver_query_log_configs(client_factory, region=region),
        )

    @mcp.tool(
        name=_LIST_DNS_FIREWALL_RULE_GROUPS,
        description=(
            "List DNS Firewall rule groups, where the configured identity "
            "has permission (route53resolver:ListFirewallRuleGroups). A "
            "permission gap degrades to an empty list with a warning, not "
            "an error."
        ),
        meta=capability_meta(resource_types=["dns_firewall_rule_group"]),
    )
    def aws_list_dns_firewall_rule_groups(region: str) -> dict[str, Any]:
        """List DNS Firewall rule groups.

        Args:
            region: AWS region to query, e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_DNS_FIREWALL_RULE_GROUPS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_dns_firewall_rule_groups(client_factory, region=region),
        )

    @mcp.tool(
        name=_LIST_DNS_FIREWALL_RULE_GROUP_ASSOCIATIONS,
        description=(
            "List DNS Firewall rule group VPC associations, where allowed "
            "(route53resolver:ListFirewallRuleGroupAssociations)."
        ),
        meta=capability_meta(resource_types=["dns_firewall_rule_group_association"]),
    )
    def aws_list_dns_firewall_rule_group_associations(
        region: str, vpc_id: str | None = None
    ) -> dict[str, Any]:
        """List DNS Firewall rule group associations.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_DNS_FIREWALL_RULE_GROUP_ASSOCIATIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_dns_firewall_rule_group_associations(
                client_factory, region=region, vpc_id=vpc_id
            ),
        )
