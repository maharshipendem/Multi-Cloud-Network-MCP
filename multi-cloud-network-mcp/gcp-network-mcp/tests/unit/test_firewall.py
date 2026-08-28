from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_pager

from gcp_network_mcp.gcp.firewall import (
    list_firewall_rules,
    list_hierarchical_firewall_policies,
    list_network_firewall_policies,
    normalize_firewall_policy,
)
from gcp_network_mcp.models.firewall import implied_firewall_rules

NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)


def test_normalize_firewall_rule_action_derived_from_allowed() -> None:
    rule = compute_v1.Firewall(
        name="allow-ssh",
        network=NETWORK_SELF_LINK,
        direction="INGRESS",
        priority=1000,
        allowed=[compute_v1.Allowed(I_p_protocol="tcp", ports=["22"])],
        source_ranges=["0.0.0.0/0"],
    )
    from gcp_network_mcp.gcp.firewall import normalize_firewall_rule

    normalized = normalize_firewall_rule(rule, project_id=PROJECT_ID)
    assert normalized.action == "ALLOW"
    assert normalized.allowed[0].ip_protocol == "tcp"
    assert normalized.allowed[0].ports == ["22"]
    assert normalized.is_implied is False


def test_normalize_firewall_rule_action_derived_from_denied() -> None:
    rule = compute_v1.Firewall(
        name="deny-all",
        network=NETWORK_SELF_LINK,
        direction="INGRESS",
        priority=2000,
        denied=[compute_v1.Denied(I_p_protocol="all")],
    )
    from gcp_network_mcp.gcp.firewall import normalize_firewall_rule

    normalized = normalize_firewall_rule(rule, project_id=PROJECT_ID)
    assert normalized.action == "DENY"


def test_list_firewall_rules_is_project_scoped(client_factory) -> None:
    rule = compute_v1.Firewall(
        name="r1",
        network=NETWORK_SELF_LINK,
        priority=1000,
        allowed=[compute_v1.Allowed(I_p_protocol="tcp")],
    )
    client_factory.firewalls().list.return_value = make_pager([rule])
    rules = list_firewall_rules(client_factory, project_id=PROJECT_ID)
    assert len(rules) == 1
    assert rules[0].network_self_link == NETWORK_SELF_LINK


def test_implied_firewall_rules_are_flagged_and_not_from_api() -> None:
    implied = implied_firewall_rules(network_self_link=NETWORK_SELF_LINK, network_name="vpc-1")
    assert len(implied) == 2
    egress = next(r for r in implied if r.direction == "EGRESS")
    ingress = next(r for r in implied if r.direction == "INGRESS")
    assert egress.action == "ALLOW"
    assert egress.priority == 65535
    assert egress.is_implied is True
    assert egress.source_api == "implied"
    assert ingress.action == "DENY"
    assert ingress.is_implied is True


def test_normalize_firewall_policy_extracts_rules_and_associations() -> None:
    policy = compute_v1.FirewallPolicy(
        name="org-policy",
        short_name="org-policy",
        parent="organizations/12345",
        rules=[
            compute_v1.FirewallPolicyRule(
                priority=1000,
                action="allow",
                direction="INGRESS",
                disabled=False,
                rule_name="allow-internal",
                target_resources=[NETWORK_SELF_LINK],
            )
        ],
        associations=[
            compute_v1.FirewallPolicyAssociation(
                name="assoc-1", attachment_target=NETWORK_SELF_LINK
            )
        ],
    )
    normalized = normalize_firewall_policy(policy, scope="hierarchical")
    assert normalized.scope == "hierarchical"
    assert normalized.project_id == ""
    assert normalized.parent == "organizations/12345"
    assert len(normalized.rules) == 1
    assert normalized.rules[0].rule_name == "allow-internal"
    assert len(normalized.associations) == 1
    assert normalized.associations[0].attachment_target == NETWORK_SELF_LINK


def test_list_hierarchical_firewall_policies_uses_parent_id_request(client_factory) -> None:
    policy = compute_v1.FirewallPolicy(name="org-policy", parent="organizations/12345")
    client_factory.firewall_policies().list.return_value = make_pager([policy])
    policies = list_hierarchical_firewall_policies(client_factory, parent_id="organizations/12345")
    assert len(policies) == 1
    assert policies[0].scope == "hierarchical"
    _, kwargs = client_factory.firewall_policies().list.call_args
    assert kwargs == {"request": {"parent_id": "organizations/12345"}}


def test_list_network_firewall_policies_is_project_scoped(client_factory) -> None:
    policy = compute_v1.FirewallPolicy(name="net-policy")
    client_factory.network_firewall_policies().list.return_value = make_pager([policy])
    policies = list_network_firewall_policies(client_factory, project_id=PROJECT_ID)
    assert len(policies) == 1
    assert policies[0].scope == "network"
    assert policies[0].project_id == PROJECT_ID
