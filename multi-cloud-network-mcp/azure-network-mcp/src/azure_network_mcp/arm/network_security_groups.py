"""ARM service layer: network security groups, security rules, and
effective NSGs (the rules Azure actually applies to a NIC)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly_lro
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import (
    EffectiveNetworkSecurityGroup,
    EffectiveSecurityRule,
    NetworkSecurityGroup,
    SecurityRule,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _normalize_security_rule(
    rule: Any, *, subscription_id: str, observed_at: str, source_api: str
) -> SecurityRule:
    parsed = parse_resource_id(rule.id) if getattr(rule, "id", None) else None
    return SecurityRule(
        resource_id=rule.id or "",
        name=rule.name,
        subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
        resource_group=parsed.resource_group if parsed else None,
        provisioning_state=getattr(rule, "provisioning_state", None),
        observed_at=observed_at,
        source_api=source_api,
        protocol=getattr(rule, "protocol", None),
        source_port_range=getattr(rule, "source_port_range", None),
        source_port_ranges=list(getattr(rule, "source_port_ranges", None) or []),
        destination_port_range=getattr(rule, "destination_port_range", None),
        destination_port_ranges=list(getattr(rule, "destination_port_ranges", None) or []),
        source_address_prefix=getattr(rule, "source_address_prefix", None),
        source_address_prefixes=list(getattr(rule, "source_address_prefixes", None) or []),
        destination_address_prefix=getattr(rule, "destination_address_prefix", None),
        destination_address_prefixes=list(
            getattr(rule, "destination_address_prefixes", None) or []
        ),
        access=getattr(rule, "access", None),
        priority=getattr(rule, "priority", None),
        direction=getattr(rule, "direction", None),
        description=getattr(rule, "description", None),
    )


def list_network_security_groups(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[NetworkSecurityGroup]:
    """Call NetworkSecurityGroupsOperations.list_all (whole subscription)
    or .list (one resource group).

    Custom rules (``security_rules``) and Azure's own built-in defaults
    (``default_security_rules``, e.g. AllowVnetInBound, DenyAllInBound)
    are kept as separate fields on the normalized model -- see
    ``NetworkSecurityGroup``'s docstring.
    """
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.network_security_groups,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(
            client.network_security_groups, "list_all", max_items=settings.max_page_results
        )

    result = []
    for nsg in raw:
        parsed = parse_resource_id(nsg.id)
        result.append(
            NetworkSecurityGroup(
                resource_id=nsg.id,
                name=nsg.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=nsg.location,
                provisioning_state=getattr(nsg, "provisioning_state", None),
                tags=normalize_tags(nsg.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/networkSecurityGroups",
                security_rules=[
                    _normalize_security_rule(
                        r,
                        subscription_id=subscription_id,
                        observed_at=observed_at,
                        source_api="Microsoft.Network/networkSecurityGroups (embedded)",
                    )
                    for r in (nsg.security_rules or [])
                ],
                default_security_rules=[
                    _normalize_security_rule(
                        r,
                        subscription_id=subscription_id,
                        observed_at=observed_at,
                        source_api="Microsoft.Network/networkSecurityGroups (embedded default)",
                    )
                    for r in (nsg.default_security_rules or [])
                ],
                network_interface_ids=[n.id for n in (nsg.network_interfaces or []) if n.id],
                subnet_ids=[s.id for s in (nsg.subnets or []) if s.id],
            )
        )
    return result


def list_security_rules(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_security_group_name: str,
) -> list[SecurityRule]:
    """Call SecurityRulesOperations.list for one NSG's custom rules."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.security_rules,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        network_security_group_name=network_security_group_name,
    )
    return [
        _normalize_security_rule(
            r,
            subscription_id=subscription_id,
            observed_at=observed_at,
            source_api="Microsoft.Network/networkSecurityGroups/securityRules",
        )
        for r in raw
    ]


def get_effective_network_security_groups(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_interface_name: str,
) -> list[EffectiveNetworkSecurityGroup]:
    """Call NetworkInterfacesOperations.begin_list_effective_network_security_groups
    -- the NSG rules Azure actually applies to a NIC, across subnet- and
    NIC-level associations, with Application Security Group references
    expanded into their concrete IP prefixes. Read-only despite the
    ``begin_`` prefix; see security/guardrails.py's module docstring.
    """
    client = client_factory.get_network_client(subscription_id)
    result = call_readonly_lro(
        client.network_interfaces,
        "begin_list_effective_network_security_groups",
        resource_group_name=resource_group,
        network_interface_name=network_interface_name,
    )
    return [
        EffectiveNetworkSecurityGroup(
            network_security_group_id=(
                nsg.network_security_group.id if nsg.network_security_group else None
            ),
            effective_security_rules=[
                EffectiveSecurityRule(
                    name=r.name,
                    protocol=getattr(r, "protocol", None),
                    source_port_ranges=list(getattr(r, "source_port_ranges", None) or []),
                    destination_port_ranges=list(getattr(r, "destination_port_ranges", None) or []),
                    source_address_prefixes=list(getattr(r, "source_address_prefixes", None) or []),
                    destination_address_prefixes=list(
                        getattr(r, "destination_address_prefixes", None) or []
                    ),
                    expanded_source_address_prefix=list(
                        getattr(r, "expanded_source_address_prefix", None) or []
                    ),
                    expanded_destination_address_prefix=list(
                        getattr(r, "expanded_destination_address_prefix", None) or []
                    ),
                    access=getattr(r, "access", None),
                    priority=getattr(r, "priority", None),
                    direction=getattr(r, "direction", None),
                )
                for r in (nsg.effective_security_rules or [])
            ],
        )
        for nsg in (result.value or [])
    ]


__all__ = [
    "get_effective_network_security_groups",
    "list_network_security_groups",
    "list_security_rules",
]
