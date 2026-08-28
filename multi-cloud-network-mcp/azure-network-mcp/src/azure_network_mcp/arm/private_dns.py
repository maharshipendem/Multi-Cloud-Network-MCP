"""ARM service layer: Azure Private DNS (zones, links, record sets) and
Azure DNS Resolver (inbound/outbound endpoints, forwarding rulesets and
rules) -- two separate ARM clients/providers, see models/private_dns.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.private_dns import (
    DnsForwardingRule,
    DnsForwardingRuleset,
    DnsForwardingRulesetVirtualNetworkLink,
    DnsResolver,
    DnsResolverInboundEndpoint,
    DnsResolverOutboundEndpoint,
    PrivateDnsRecordSet,
    PrivateDnsVirtualNetworkLink,
    PrivateDnsZone,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory

_RECORD_FIELDS: dict[str, str] = {
    "a": "a_records",
    "aaaa": "aaaa_records",
    "mx": "mx_records",
    "ptr": "ptr_records",
    "srv": "srv_records",
    "txt": "txt_records",
}


def _record_values(record_set: Any) -> list[str]:
    values: list[str] = []
    for attr in _RECORD_FIELDS.values():
        for entry in getattr(record_set, attr, None) or []:
            values.append(
                str(getattr(entry, "ipv4_address", None) or getattr(entry, "value", None) or entry)
            )
    cname = getattr(record_set, "cname_record", None)
    if cname is not None:
        values.append(str(getattr(cname, "cname", "")))
    soa = getattr(record_set, "soa_record", None)
    if soa is not None:
        values.append(f"SOA host={getattr(soa, 'host', None)}")
    return values


# --- Private DNS zones ---------------------------------------------------------


def list_private_dns_zones(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[PrivateDnsZone]:
    """Call PrivateZonesOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_private_dns_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.private_zones,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.private_zones, "list", max_items=settings.max_page_results)

    result = []
    for zone in raw:
        parsed = parse_resource_id(zone.id)
        result.append(
            PrivateDnsZone(
                resource_id=zone.id,
                name=zone.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=zone.location,
                provisioning_state=getattr(zone, "provisioning_state", None),
                tags=normalize_tags(zone.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/privateDnsZones",
                number_of_record_sets=getattr(zone, "number_of_record_sets", None),
                number_of_virtual_network_links=getattr(
                    zone, "number_of_virtual_network_links", None
                ),
            )
        )
    return result


def list_private_dns_virtual_network_links(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, zone_name: str
) -> list[PrivateDnsVirtualNetworkLink]:
    """Call VirtualNetworkLinksOperations.list for one Private DNS zone."""
    client = client_factory.get_private_dns_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_network_links,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        private_zone_name=zone_name,
    )
    result = []
    for link_ in raw:
        parsed = parse_resource_id(link_.id)
        result.append(
            PrivateDnsVirtualNetworkLink(
                resource_id=link_.id,
                name=link_.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=link_.location,
                provisioning_state=getattr(link_, "provisioning_state", None),
                tags=normalize_tags(link_.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                zone_name=zone_name,
                virtual_network_id=(
                    link_.virtual_network.id if getattr(link_, "virtual_network", None) else None
                ),
                registration_enabled=getattr(link_, "registration_enabled", None),
                virtual_network_link_state=getattr(link_, "virtual_network_link_state", None),
            )
        )
    return result


def list_private_dns_record_sets(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, zone_name: str
) -> list[PrivateDnsRecordSet]:
    """Call RecordSetsOperations.list for one Private DNS zone. Record
    values are already-public zone data an operator with read access has
    direct visibility into; this is a bounded summary (capped by
    max_page_results), not a raw zone-file dump."""
    client = client_factory.get_private_dns_client(subscription_id)
    settings = client_factory.settings

    raw = paginate(
        client.record_sets,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        private_zone_name=zone_name,
    )
    return [
        PrivateDnsRecordSet(
            name=rs.name,
            record_type=(rs.id.rsplit("/", 2)[-2] if getattr(rs, "id", None) else None),
            ttl=getattr(rs, "ttl", None),
            values=_record_values(rs),
        )
        for rs in raw
    ]


# --- DNS Resolver ----------------------------------------------------------------


def list_dns_resolvers(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[DnsResolver]:
    """Call DnsResolversOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.dns_resolvers,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.dns_resolvers, "list", max_items=settings.max_page_results)

    result = []
    for resolver in raw:
        parsed = parse_resource_id(resolver.id)
        result.append(
            DnsResolver(
                resource_id=resolver.id,
                name=resolver.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=resolver.location,
                provisioning_state=getattr(resolver, "provisioning_state", None),
                tags=normalize_tags(resolver.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsResolvers",
                virtual_network_id=(
                    resolver.virtual_network.id
                    if getattr(resolver, "virtual_network", None)
                    else None
                ),
                dns_resolver_state=getattr(resolver, "dns_resolver_state", None),
            )
        )
    return result


def list_dns_resolver_inbound_endpoints(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    dns_resolver_name: str,
) -> list[DnsResolverInboundEndpoint]:
    """Call InboundEndpointsOperations.list for one DNS resolver."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.inbound_endpoints,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        dns_resolver_name=dns_resolver_name,
    )
    result = []
    for ep in raw:
        parsed = parse_resource_id(ep.id)
        ip_configs = getattr(ep, "ip_configurations", None) or []
        result.append(
            DnsResolverInboundEndpoint(
                resource_id=ep.id,
                name=ep.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=ep.location,
                provisioning_state=getattr(ep, "provisioning_state", None),
                tags=normalize_tags(ep.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsResolvers/inboundEndpoints",
                dns_resolver_name=dns_resolver_name,
                subnet_ids=[
                    c.subnet.id for c in ip_configs if getattr(c, "subnet", None) and c.subnet.id
                ],
                private_ip_addresses=[
                    c.private_ip_address
                    for c in ip_configs
                    if getattr(c, "private_ip_address", None)
                ],
            )
        )
    return result


def list_dns_resolver_outbound_endpoints(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    dns_resolver_name: str,
) -> list[DnsResolverOutboundEndpoint]:
    """Call OutboundEndpointsOperations.list for one DNS resolver."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.outbound_endpoints,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        dns_resolver_name=dns_resolver_name,
    )
    result = []
    for ep in raw:
        parsed = parse_resource_id(ep.id)
        result.append(
            DnsResolverOutboundEndpoint(
                resource_id=ep.id,
                name=ep.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                location=ep.location,
                provisioning_state=getattr(ep, "provisioning_state", None),
                tags=normalize_tags(ep.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsResolvers/outboundEndpoints",
                dns_resolver_name=dns_resolver_name,
                subnet_id=(ep.subnet.id if getattr(ep, "subnet", None) else None),
            )
        )
    return result


def list_dns_forwarding_rulesets(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[DnsForwardingRuleset]:
    """Call DnsForwardingRulesetsOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.dns_forwarding_rulesets,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.dns_forwarding_rulesets, "list", max_items=settings.max_page_results)

    result = []
    for ruleset in raw:
        parsed = parse_resource_id(ruleset.id)
        result.append(
            DnsForwardingRuleset(
                resource_id=ruleset.id,
                name=ruleset.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=ruleset.location,
                provisioning_state=getattr(ruleset, "provisioning_state", None),
                tags=normalize_tags(ruleset.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsForwardingRulesets",
                outbound_endpoint_ids=[
                    e.id
                    for e in (getattr(ruleset, "dns_resolver_outbound_endpoints", None) or [])
                    if getattr(e, "id", None)
                ],
            )
        )
    return result


def list_dns_forwarding_rules(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, ruleset_name: str
) -> list[DnsForwardingRule]:
    """Call ForwardingRulesOperations.list for one forwarding ruleset."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.forwarding_rules,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        dns_forwarding_ruleset_name=ruleset_name,
    )
    result = []
    for rule in raw:
        parsed = parse_resource_id(rule.id)
        result.append(
            DnsForwardingRule(
                resource_id=rule.id,
                name=rule.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(rule, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsForwardingRulesets/forwardingRules",
                ruleset_name=ruleset_name,
                domain_name=getattr(rule, "domain_name", None),
                target_dns_servers=[
                    d.ip_address
                    for d in (getattr(rule, "target_dns_servers", None) or [])
                    if getattr(d, "ip_address", None)
                ],
                forwarding_rule_state=getattr(rule, "forwarding_rule_state", None),
            )
        )
    return result


def list_dns_forwarding_ruleset_virtual_network_links(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, ruleset_name: str
) -> list[DnsForwardingRulesetVirtualNetworkLink]:
    """Call VirtualNetworkLinksOperations.list (the DNS-Resolver-package
    operation group) for one forwarding ruleset."""
    client = client_factory.get_dns_resolver_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_network_links,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        dns_forwarding_ruleset_name=ruleset_name,
    )
    result = []
    for link_ in raw:
        parsed = parse_resource_id(link_.id)
        result.append(
            DnsForwardingRulesetVirtualNetworkLink(
                resource_id=link_.id,
                name=link_.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=resource_group,
                provisioning_state=getattr(link_, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/dnsForwardingRulesets/virtualNetworkLinks",
                ruleset_name=ruleset_name,
                virtual_network_id=(
                    link_.virtual_network.id if getattr(link_, "virtual_network", None) else None
                ),
            )
        )
    return result


__all__ = [
    "list_dns_forwarding_rules",
    "list_dns_forwarding_ruleset_virtual_network_links",
    "list_dns_forwarding_rulesets",
    "list_dns_resolver_inbound_endpoints",
    "list_dns_resolver_outbound_endpoints",
    "list_dns_resolvers",
    "list_private_dns_record_sets",
    "list_private_dns_virtual_network_links",
    "list_private_dns_zones",
]
