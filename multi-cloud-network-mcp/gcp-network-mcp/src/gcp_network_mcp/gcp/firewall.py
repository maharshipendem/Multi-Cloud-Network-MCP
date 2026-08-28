"""Service-layer functions for network-level Firewall rules and Firewall
Policies (hierarchical and network-scoped)."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import now_iso
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.models.firewall import (
    FirewallPolicy,
    FirewallPolicyAssociation,
    FirewallPolicyRule,
    FirewallPolicyRuleMatch,
    FirewallRule,
    ProtocolPorts,
)


def _protocol_ports(
    entries: list[compute_v1.Allowed] | list[compute_v1.Denied],
) -> list[ProtocolPorts]:
    return [ProtocolPorts(ip_protocol=e.I_p_protocol, ports=list(e.ports)) for e in entries]


def normalize_firewall_rule(rule: compute_v1.Firewall, *, project_id: str) -> FirewallRule:
    return FirewallRule(
        self_link=rule.self_link or None,
        id=str(rule.id) if rule.id else None,
        name=rule.name,
        project_id=project_id,
        network_self_link=rule.network,
        direction=rule.direction or "INGRESS",
        priority=rule.priority,
        disabled=rule.disabled,
        action="ALLOW" if rule.allowed else "DENY",
        allowed=_protocol_ports(list(rule.allowed)),
        denied=_protocol_ports(list(rule.denied)),
        source_ranges=list(rule.source_ranges),
        destination_ranges=list(rule.destination_ranges),
        source_tags=list(rule.source_tags),
        target_tags=list(rule.target_tags),
        source_service_accounts=list(rule.source_service_accounts),
        target_service_accounts=list(rule.target_service_accounts),
        observed_at=now_iso(),
        source_api="FirewallsClient.list",
    )


def list_firewall_rules(client_factory: ClientFactory, *, project_id: str) -> list[FirewallRule]:
    """Firewall rules are a global (project-scoped, not region/zone-scoped)
    resource -- one plain ``list`` call covers the whole project. Note
    this does *not* include GCP's two implied default rules (allow-all
    egress, deny-all ingress) -- see ``models.firewall.implied_firewall_rules``."""
    raw = paginate(
        client_factory.firewalls(),
        "list",
        resource_type="firewall_rule",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_firewall_rule(r, project_id=project_id) for r in raw]


def _normalize_policy_rule(rule: compute_v1.FirewallPolicyRule) -> FirewallPolicyRule:
    match = None
    if "match" in rule:
        match = FirewallPolicyRuleMatch(
            src_ip_ranges=list(rule.match.src_ip_ranges),
            dest_ip_ranges=list(rule.match.dest_ip_ranges),
            src_secure_tags=[t.name for t in rule.match.src_secure_tags],
            src_networks=list(rule.match.src_networks),
        )
    return FirewallPolicyRule(
        priority=rule.priority,
        action=rule.action,
        direction=rule.direction or "INGRESS",
        disabled=rule.disabled,
        rule_name=rule.rule_name or None,
        description=rule.description or None,
        match=match,
        target_resources=list(rule.target_resources),
        target_secure_tags=[t.name for t in rule.target_secure_tags],
        target_service_accounts=list(rule.target_service_accounts),
    )


def _normalize_policy_association(
    association: compute_v1.FirewallPolicyAssociation,
) -> FirewallPolicyAssociation:
    return FirewallPolicyAssociation(
        name=association.name or None,
        attachment_target=association.attachment_target or None,
        short_name=association.short_name or None,
    )


def normalize_firewall_policy(
    policy: compute_v1.FirewallPolicy, *, scope: str, project_id: str = ""
) -> FirewallPolicy:
    return FirewallPolicy(
        self_link=policy.self_link or None,
        id=str(policy.id) if policy.id else None,
        name=policy.name,
        project_id=project_id,
        scope=scope,
        parent=policy.parent or None,
        short_name=policy.short_name or None,
        display_name=policy.display_name or None,
        rule_tuple_count=policy.rule_tuple_count or None,
        associations=[_normalize_policy_association(a) for a in policy.associations],
        rules=[_normalize_policy_rule(r) for r in policy.rules],
        observed_at=now_iso(),
        source_api=f"FirewallPoliciesClient({scope}).list",
    )


def list_hierarchical_firewall_policies(
    client_factory: ClientFactory, *, parent_id: str
) -> list[FirewallPolicy]:
    """List Firewall Policies attached under one organization/folder.
    ``FirewallPoliciesClient.list`` is org/folder-scoped via
    ``parent_id`` -- it has no ``project`` parameter, unlike almost every
    other Compute Engine list call."""
    raw = paginate(
        client_factory.firewall_policies(),
        "list",
        resource_type="firewall_policy",
        request={"parent_id": parent_id},
    )
    return [normalize_firewall_policy(p, scope="hierarchical") for p in raw]


def list_network_firewall_policies(
    client_factory: ClientFactory, *, project_id: str
) -> list[FirewallPolicy]:
    raw = paginate(
        client_factory.network_firewall_policies(),
        "list",
        resource_type="firewall_policy",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_firewall_policy(p, scope="network", project_id=project_id) for p in raw]


__all__ = [
    "list_firewall_rules",
    "list_hierarchical_firewall_policies",
    "list_network_firewall_policies",
    "normalize_firewall_policy",
    "normalize_firewall_rule",
]
