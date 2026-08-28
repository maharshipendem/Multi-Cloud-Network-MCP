"""Normalized models for Azure Firewall inventory and firewall policy rule
summaries.

Rule *bodies* (source/destination CIDRs, ports, FQDN filters) are not
modeled here beyond counts -- Milestone 6 asks for "relevant rule
summaries with response limits," not a full rule-engine mirror. See
``arm/firewall.py`` for the summarization/bounding logic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource


class AzureFirewall(AzureResource):
    """Normalized entry from AzureFirewallsOperations.list/list_all/get."""

    sku_name: str | None = None
    sku_tier: str | None = None
    threat_intel_mode: str | None = None
    virtual_hub_id: str | None = None
    firewall_policy_id: str | None = None
    ip_configuration_count: int = 0
    hub_ip_addresses: list[str] = Field(default_factory=list)


class FirewallPolicy(AzureResource):
    """Normalized entry from FirewallPoliciesOperations.list/list_all/get."""

    sku_tier: str | None = None
    threat_intel_mode: str | None = None
    base_policy_id: str | None = None
    child_policy_ids: list[str] = Field(default_factory=list)
    firewall_ids: list[str] = Field(default_factory=list)
    rule_collection_group_ids: list[str] = Field(default_factory=list)


class RuleCollectionSummary(BaseModel):
    name: str | None = None
    rule_collection_type: str | None = None
    priority: int | None = None
    action: str | None = None
    rule_count: int = 0


class FirewallPolicyRuleCollectionGroup(AzureResource):
    """Normalized, bounded entry from
    FirewallPolicyRuleCollectionGroupsOperations.list/get -- individual
    rules are summarized to a count per collection, not enumerated, per
    this milestone's response-size limits."""

    firewall_policy_name: str | None = None
    priority: int | None = None
    rule_collections: list[RuleCollectionSummary] = Field(default_factory=list)


__all__ = [
    "AzureFirewall",
    "FirewallPolicy",
    "FirewallPolicyRuleCollectionGroup",
    "RuleCollectionSummary",
]
