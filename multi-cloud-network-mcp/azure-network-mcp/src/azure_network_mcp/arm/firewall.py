"""ARM service layer: Azure Firewall inventory and firewall policy rule
collection group summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.firewall import (
    AzureFirewall,
    FirewallPolicy,
    FirewallPolicyRuleCollectionGroup,
    RuleCollectionSummary,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _hub_public_ip_addresses(fw: object) -> list[str]:
    hub_ips = getattr(fw, "hub_ip_addresses", None)
    public_ips = getattr(hub_ips, "public_i_ps", None) if hub_ips else None
    addresses = getattr(public_ips, "addresses", None) if public_ips else None
    return [a.address for a in (addresses or []) if getattr(a, "address", None)]


def list_azure_firewalls(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[AzureFirewall]:
    """Call AzureFirewallsOperations.list (one resource group) or
    .list_all (whole subscription)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.azure_firewalls,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.azure_firewalls, "list_all", max_items=settings.max_page_results)

    result = []
    for fw in raw:
        parsed = parse_resource_id(fw.id)
        sku = getattr(fw, "sku", None)
        result.append(
            AzureFirewall(
                resource_id=fw.id,
                name=fw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=fw.location,
                provisioning_state=getattr(fw, "provisioning_state", None),
                tags=normalize_tags(fw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/azureFirewalls",
                sku_name=(getattr(sku, "name", None) if sku else None),
                sku_tier=(getattr(sku, "tier", None) if sku else None),
                threat_intel_mode=getattr(fw, "threat_intel_mode", None),
                virtual_hub_id=(fw.virtual_hub.id if getattr(fw, "virtual_hub", None) else None),
                firewall_policy_id=(
                    fw.firewall_policy.id if getattr(fw, "firewall_policy", None) else None
                ),
                ip_configuration_count=len(getattr(fw, "ip_configurations", None) or []),
                hub_ip_addresses=_hub_public_ip_addresses(fw),
            )
        )
    return result


def list_firewall_policies(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[FirewallPolicy]:
    """Call FirewallPoliciesOperations.list (one resource group) or
    .list_all (whole subscription)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.firewall_policies,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.firewall_policies, "list_all", max_items=settings.max_page_results)

    result = []
    for policy in raw:
        parsed = parse_resource_id(policy.id)
        sku = getattr(policy, "sku", None)
        result.append(
            FirewallPolicy(
                resource_id=policy.id,
                name=policy.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=policy.location,
                provisioning_state=getattr(policy, "provisioning_state", None),
                tags=normalize_tags(policy.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/firewallPolicies",
                sku_tier=(getattr(sku, "tier", None) if sku else None),
                threat_intel_mode=getattr(policy, "threat_intel_mode", None),
                base_policy_id=(
                    policy.base_policy.id if getattr(policy, "base_policy", None) else None
                ),
                child_policy_ids=[
                    c.id
                    for c in (getattr(policy, "child_policies", None) or [])
                    if getattr(c, "id", None)
                ],
                firewall_ids=[
                    f.id
                    for f in (getattr(policy, "firewalls", None) or [])
                    if getattr(f, "id", None)
                ],
                rule_collection_group_ids=[
                    g.id
                    for g in (getattr(policy, "rule_collection_groups", None) or [])
                    if getattr(g, "id", None)
                ],
            )
        )
    return result


def list_firewall_policy_rule_collection_groups(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    firewall_policy_name: str,
) -> list[FirewallPolicyRuleCollectionGroup]:
    """Call FirewallPolicyRuleCollectionGroupsOperations.list -- rules are
    summarized to a count per collection, not enumerated, per this
    milestone's response-size limits."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.firewall_policy_rule_collection_groups,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        firewall_policy_name=firewall_policy_name,
    )
    result = []
    for group in raw:
        parsed = parse_resource_id(group.id)
        result.append(
            FirewallPolicyRuleCollectionGroup(
                resource_id=group.id,
                name=group.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(group, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/firewallPolicies/ruleCollectionGroups",
                firewall_policy_name=firewall_policy_name,
                priority=getattr(group, "priority", None),
                rule_collections=[
                    RuleCollectionSummary(
                        name=getattr(rc, "name", None),
                        rule_collection_type=getattr(rc, "rule_collection_type", None),
                        priority=getattr(rc, "priority", None),
                        action=(
                            getattr(rc.action, "type", None)
                            if getattr(rc, "action", None)
                            else None
                        ),
                        rule_count=len(getattr(rc, "rules", None) or []),
                    )
                    for rc in (group.rule_collections or [])
                ],
            )
        )
    return result


__all__ = [
    "list_azure_firewalls",
    "list_firewall_policies",
    "list_firewall_policy_rule_collection_groups",
]
