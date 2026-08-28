"""Normalized models for network-level Firewall rules and Firewall
Policies (both hierarchical, org/folder-scoped, and network-scoped --
GCP represents both with the same underlying ``FirewallPolicy`` API
type; this server tells them apart via ``FirewallPolicy.scope``, set by
whichever service-layer function fetched the record, since the raw API
response carries no field that reliably distinguishes them)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class ProtocolPorts(BaseModel):
    ip_protocol: str
    ports: list[str] = Field(default_factory=list)


class FirewallRule(GcpResource):
    """Normalized entry from ``FirewallsClient.list``/``get``.

    ``action`` is derived, not a raw GCP field: ``"ALLOW"`` when
    ``allowed`` is populated, ``"DENY"`` when ``denied`` is populated
    (the two are mutually exclusive on a real rule). ``is_implied`` is
    always ``False`` here -- see ``IMPLIED_FIREWALL_RULES`` for GCP's two
    unlisted default rules every VPC network carries implicitly.
    """

    network_self_link: str
    direction: str
    priority: int
    disabled: bool
    action: str
    allowed: list[ProtocolPorts] = Field(default_factory=list)
    denied: list[ProtocolPorts] = Field(default_factory=list)
    source_ranges: list[str] = Field(default_factory=list)
    destination_ranges: list[str] = Field(default_factory=list)
    source_tags: list[str] = Field(default_factory=list)
    target_tags: list[str] = Field(default_factory=list)
    source_service_accounts: list[str] = Field(default_factory=list)
    target_service_accounts: list[str] = Field(default_factory=list)
    is_implied: bool = False


def implied_firewall_rules(*, network_self_link: str, network_name: str) -> list[FirewallRule]:
    """GCP gives every VPC network two default rules that never appear in
    ``FirewallsClient.list`` -- an implied allow-all egress and an implied
    deny-all ingress, both at the lowest possible priority (65535). A
    caller reasoning about "is traffic allowed" from listed rules alone
    would silently miss these; tools that evaluate firewall behavior
    (``gcp_get_vpc_topology``, any future reachability reasoning) must
    fold these two synthetic records in alongside the real ones.
    """
    return [
        FirewallRule(
            self_link=None,
            id=f"implied-allow-egress-{network_name}",
            name="implied-allow-egress",
            project_id="",
            network_self_link=network_self_link,
            direction="EGRESS",
            priority=65535,
            disabled=False,
            action="ALLOW",
            allowed=[ProtocolPorts(ip_protocol="all")],
            destination_ranges=["0.0.0.0/0"],
            is_implied=True,
            observed_at="",
            source_api="implied",
        ),
        FirewallRule(
            self_link=None,
            id=f"implied-deny-ingress-{network_name}",
            name="implied-deny-ingress",
            project_id="",
            network_self_link=network_self_link,
            direction="INGRESS",
            priority=65535,
            disabled=False,
            action="DENY",
            denied=[ProtocolPorts(ip_protocol="all")],
            source_ranges=["0.0.0.0/0"],
            is_implied=True,
            observed_at="",
            source_api="implied",
        ),
    ]


class FirewallPolicyRuleMatch(BaseModel):
    src_ip_ranges: list[str] = Field(default_factory=list)
    dest_ip_ranges: list[str] = Field(default_factory=list)
    src_secure_tags: list[str] = Field(default_factory=list)
    src_networks: list[str] = Field(default_factory=list)


class FirewallPolicyRule(BaseModel):
    """One rule within a Firewall Policy (hierarchical or network)."""

    priority: int
    action: str
    direction: str
    disabled: bool
    rule_name: str | None = None
    description: str | None = None
    match: FirewallPolicyRuleMatch | None = None
    target_resources: list[str] = Field(default_factory=list)
    target_secure_tags: list[str] = Field(default_factory=list)
    target_service_accounts: list[str] = Field(default_factory=list)


class FirewallPolicyAssociation(BaseModel):
    """One attachment of a Firewall Policy to an organization, folder, or
    VPC network."""

    name: str | None = None
    attachment_target: str | None = None
    short_name: str | None = None


class FirewallPolicy(GcpResource):
    """Normalized entry from ``FirewallPoliciesClient`` (hierarchical,
    org/folder-scoped -- ``scope="hierarchical"``) or
    ``NetworkFirewallPoliciesClient`` (project-scoped --
    ``scope="network"``). ``project_id`` is empty for a hierarchical
    policy, which has no owning project."""

    project_id: str = ""
    scope: str
    parent: str | None = None
    short_name: str | None = None
    display_name: str | None = None
    rule_tuple_count: int | None = None
    associations: list[FirewallPolicyAssociation] = Field(default_factory=list)
    rules: list[FirewallPolicyRule] = Field(default_factory=list)


__all__ = [
    "FirewallPolicy",
    "FirewallPolicyAssociation",
    "FirewallPolicyRule",
    "FirewallPolicyRuleMatch",
    "FirewallRule",
    "ProtocolPorts",
    "implied_firewall_rules",
]
