"""MCP tools: Azure Private DNS (zones, links, record sets) and Azure DNS
Resolver (inbound/outbound endpoints, forwarding rulesets and rules)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.private_dns import (
    list_dns_forwarding_rules,
    list_dns_forwarding_ruleset_virtual_network_links,
    list_dns_forwarding_rulesets,
    list_dns_resolver_inbound_endpoints,
    list_dns_resolver_outbound_endpoints,
    list_dns_resolvers,
    list_private_dns_record_sets,
    list_private_dns_virtual_network_links,
    list_private_dns_zones,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_ZONES = "azure_list_private_dns_zones"
_LIST_ZONE_LINKS = "azure_list_private_dns_virtual_network_links"
_LIST_RECORD_SETS = "azure_list_private_dns_record_sets"
_LIST_RESOLVERS = "azure_list_dns_resolvers"
_LIST_INBOUND_ENDPOINTS = "azure_list_dns_resolver_inbound_endpoints"
_LIST_OUTBOUND_ENDPOINTS = "azure_list_dns_resolver_outbound_endpoints"
_LIST_RULESETS = "azure_list_dns_forwarding_rulesets"
_LIST_RULES = "azure_list_dns_forwarding_rules"
_LIST_RULESET_LINKS = "azure_list_dns_forwarding_ruleset_virtual_network_links"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_ZONES,
        description=(
            "List Private DNS zones (whole subscription, or one resource "
            "group), including record-set and link counts."
        ),
        meta=capability_meta(resource_types=["private_dns_zone"]),
    )
    def azure_list_private_dns_zones(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Private DNS zones.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ZONES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_private_dns_zones(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_ZONE_LINKS,
        description="List one Private DNS zone's VNet links.",
        meta=capability_meta(resource_types=["private_dns_zone"]),
    )
    def azure_list_private_dns_virtual_network_links(
        resource_group: str, zone_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Private DNS zone VNet links.

        Args:
            resource_group: Resource group containing the zone.
            zone_name: Name of the Private DNS zone.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_ZONE_LINKS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_private_dns_virtual_network_links(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                zone_name=zone_name,
            ),
        )

    @mcp.tool(
        name=_LIST_RECORD_SETS,
        description="List one Private DNS zone's record sets (bounded summary).",
        meta=capability_meta(resource_types=["private_dns_zone"]),
    )
    def azure_list_private_dns_record_sets(
        resource_group: str, zone_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List Private DNS record sets.

        Args:
            resource_group: Resource group containing the zone.
            zone_name: Name of the Private DNS zone.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RECORD_SETS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_private_dns_record_sets(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                zone_name=zone_name,
            ),
        )

    @mcp.tool(
        name=_LIST_RESOLVERS,
        description=("List Azure DNS Resolvers (whole subscription, or one resource group)."),
        meta=capability_meta(resource_types=["dns_resolver"]),
    )
    def azure_list_dns_resolvers(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List DNS resolvers.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RESOLVERS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_resolvers(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_INBOUND_ENDPOINTS,
        description="List one DNS resolver's inbound endpoints.",
        meta=capability_meta(resource_types=["dns_resolver"]),
    )
    def azure_list_dns_resolver_inbound_endpoints(
        resource_group: str, dns_resolver_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List DNS resolver inbound endpoints.

        Args:
            resource_group: Resource group containing the DNS resolver.
            dns_resolver_name: Name of the DNS resolver.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_INBOUND_ENDPOINTS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_resolver_inbound_endpoints(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                dns_resolver_name=dns_resolver_name,
            ),
        )

    @mcp.tool(
        name=_LIST_OUTBOUND_ENDPOINTS,
        description="List one DNS resolver's outbound endpoints.",
        meta=capability_meta(resource_types=["dns_resolver"]),
    )
    def azure_list_dns_resolver_outbound_endpoints(
        resource_group: str, dns_resolver_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List DNS resolver outbound endpoints.

        Args:
            resource_group: Resource group containing the DNS resolver.
            dns_resolver_name: Name of the DNS resolver.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_OUTBOUND_ENDPOINTS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_resolver_outbound_endpoints(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                dns_resolver_name=dns_resolver_name,
            ),
        )

    @mcp.tool(
        name=_LIST_RULESETS,
        description=("List DNS forwarding rulesets (whole subscription, or one resource group)."),
        meta=capability_meta(resource_types=["dns_forwarding_ruleset"]),
    )
    def azure_list_dns_forwarding_rulesets(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List DNS forwarding rulesets.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RULESETS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_forwarding_rulesets(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_RULES,
        description="List one DNS forwarding ruleset's rules.",
        meta=capability_meta(resource_types=["dns_forwarding_ruleset"]),
    )
    def azure_list_dns_forwarding_rules(
        resource_group: str, ruleset_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List DNS forwarding rules.

        Args:
            resource_group: Resource group containing the ruleset.
            ruleset_name: Name of the DNS forwarding ruleset.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RULES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_forwarding_rules(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                ruleset_name=ruleset_name,
            ),
        )

    @mcp.tool(
        name=_LIST_RULESET_LINKS,
        description="List one DNS forwarding ruleset's VNet links.",
        meta=capability_meta(resource_types=["dns_forwarding_ruleset"]),
    )
    def azure_list_dns_forwarding_ruleset_virtual_network_links(
        resource_group: str, ruleset_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List DNS forwarding ruleset VNet links.

        Args:
            resource_group: Resource group containing the ruleset.
            ruleset_name: Name of the DNS forwarding ruleset.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_RULESET_LINKS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_dns_forwarding_ruleset_virtual_network_links(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                ruleset_name=ruleset_name,
            ),
        )
