"""Normalized models for Azure Private DNS zones/links/record sets and
Azure DNS Resolver (inbound/outbound endpoints, forwarding rulesets and
rules) -- two separate ARM providers (``Microsoft.Network/privateDnsZones``
and ``Microsoft.Network/dnsResolvers``) covering related but distinct DNS
capabilities within a VNet.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource

# --- Private DNS zones ---------------------------------------------------------


class PrivateDnsZone(AzureResource):
    """Normalized entry from PrivateZonesOperations.list/list_by_resource_group/get."""

    number_of_record_sets: int | None = None
    number_of_virtual_network_links: int | None = None


class PrivateDnsVirtualNetworkLink(AzureResource):
    """Normalized entry from VirtualNetworkLinksOperations.list/get -- a
    VNet's link into one Private DNS zone."""

    zone_name: str | None = None
    virtual_network_id: str | None = None
    registration_enabled: bool | None = None
    virtual_network_link_state: str | None = None


class PrivateDnsRecordSet(BaseModel):
    """A bounded summary of one record set from RecordSetsOperations.list --
    record values are included (they are already public DNS/private-zone
    data an operator with read access already has direct visibility into),
    but this is a summary, not a raw wire-format dump."""

    name: str | None = None
    record_type: str | None = None
    ttl: int | None = None
    values: list[str] = Field(default_factory=list)


# --- DNS Resolver ----------------------------------------------------------------


class DnsResolver(AzureResource):
    """Normalized entry from DnsResolversOperations.list/list_by_resource_group/get."""

    virtual_network_id: str | None = None
    dns_resolver_state: str | None = None


class DnsResolverInboundEndpoint(AzureResource):
    """Normalized entry from InboundEndpointsOperations.list -- an
    inbound endpoint accepting DNS queries from within the VNet."""

    dns_resolver_name: str | None = None
    subnet_ids: list[str] = Field(default_factory=list)
    private_ip_addresses: list[str] = Field(default_factory=list)


class DnsResolverOutboundEndpoint(AzureResource):
    """Normalized entry from OutboundEndpointsOperations.list -- an
    outbound endpoint used to forward DNS queries to on-premises or other
    external resolvers."""

    dns_resolver_name: str | None = None
    subnet_id: str | None = None


class DnsForwardingRuleset(AzureResource):
    """Normalized entry from DnsForwardingRulesetsOperations.list/
    list_by_resource_group -- a set of DNS forwarding rules, associated
    with one or more outbound endpoints."""

    outbound_endpoint_ids: list[str] = Field(default_factory=list)


class DnsForwardingRule(AzureResource):
    """Normalized entry from ForwardingRulesOperations.list -- one rule
    within a forwarding ruleset."""

    ruleset_name: str | None = None
    domain_name: str | None = None
    target_dns_servers: list[str] = Field(default_factory=list)
    forwarding_rule_state: str | None = None


class DnsForwardingRulesetVirtualNetworkLink(AzureResource):
    """Normalized entry from VirtualNetworkLinksOperations.list (the
    DNS-Resolver-package operation group, distinct from Private DNS's own
    ``VirtualNetworkLinksOperations``) -- a VNet's link into one
    forwarding ruleset."""

    ruleset_name: str | None = None
    virtual_network_id: str | None = None


__all__ = [
    "DnsForwardingRule",
    "DnsForwardingRuleset",
    "DnsForwardingRulesetVirtualNetworkLink",
    "DnsResolver",
    "DnsResolverInboundEndpoint",
    "DnsResolverOutboundEndpoint",
    "PrivateDnsRecordSet",
    "PrivateDnsVirtualNetworkLink",
    "PrivateDnsZone",
]
