from __future__ import annotations

from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.dns import (
    _routing_policy,
    list_dns_firewall_rule_group_associations,
    list_dns_firewall_rule_groups,
    list_hosted_zones,
    list_resolver_endpoints,
    list_resolver_query_log_configs,
    list_resolver_rule_associations,
    list_resolver_rules,
    list_resource_record_sets,
)
from aws_cloudops_mcp.config import Settings


@pytest.fixture
def dns_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]

        route53 = boto3.client("route53")
        zone = route53.create_hosted_zone(
            Name="private.example.com",
            CallerReference="test-ref",
            HostedZoneConfig={"PrivateZone": True},
            VPC={"VPCRegion": "us-east-1", "VPCId": vpc["VpcId"]},
        )["HostedZone"]
        zone_id = zone["Id"].removeprefix("/hostedzone/")
        route53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                "Changes": [
                    {
                        "Action": "CREATE",
                        "ResourceRecordSet": {
                            "Name": "app.private.example.com",
                            "Type": "A",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": "10.0.1.5"}],
                        },
                    }
                ]
            },
        )

        r53r = boto3.client("route53resolver", region_name="us-east-1")
        subnet_a = ec2.create_subnet(
            VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )["Subnet"]
        subnet_b = ec2.create_subnet(
            VpcId=vpc["VpcId"], CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )["Subnet"]
        sg = ec2.create_security_group(
            GroupName="resolver-sg", Description="t", VpcId=vpc["VpcId"]
        )["GroupId"]
        # Route 53 Resolver requires >= 2 IP addresses (2 AZs) per endpoint.
        endpoint = r53r.create_resolver_endpoint(
            CreatorRequestId="req-1",
            SecurityGroupIds=[sg],
            Direction="OUTBOUND",
            IpAddresses=[
                {"SubnetId": subnet_a["SubnetId"]},
                {"SubnetId": subnet_b["SubnetId"]},
            ],
        )["ResolverEndpoint"]
        rule = r53r.create_resolver_rule(
            CreatorRequestId="req-2",
            RuleType="FORWARD",
            DomainName="onprem.example.com",
            TargetIps=[{"Ip": "192.168.1.1", "Port": 53}],
            ResolverEndpointId=endpoint["Id"],
        )["ResolverRule"]
        r53r.associate_resolver_rule(ResolverRuleId=rule["Id"], VPCId=vpc["VpcId"])

        yield {
            "vpc_id": vpc["VpcId"],
            "zone_id": zone_id,
            "resolver_endpoint_id": endpoint["Id"],
            "resolver_rule_id": rule["Id"],
        }


def test_list_hosted_zones_captures_linked_vpc(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    zones = list_hosted_zones(client_factory, region="us-east-1")
    match = next(z for z in zones if z.hosted_zone_id == dns_fixture["zone_id"])
    assert match.private_zone is True
    assert match.scope == "global"
    assert dns_fixture["vpc_id"] in match.linked_vpc_ids


def test_list_resource_record_sets(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    result = list_resource_record_sets(
        client_factory, region="us-east-1", hosted_zone_id=dns_fixture["zone_id"]
    )
    names = {r.name for r in result.data}
    assert "app.private.example.com." in names
    assert result.warnings == []


def test_list_resource_record_sets_output_cap_warns(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    result = list_resource_record_sets(
        client_factory,
        region="us-east-1",
        hosted_zone_id=dns_fixture["zone_id"],
        max_record_sets=1,
    )
    assert len(result.data) <= 1
    assert any(w.code == "OUTPUT_CAP_REACHED" for w in result.warnings)


def test_routing_policy_classifies_all_known_policy_types() -> None:
    assert _routing_policy({"Weight": 10}) == "weighted"
    assert _routing_policy({"Region": "us-east-1"}) == "latency"
    assert _routing_policy({"Failover": "PRIMARY"}) == "failover"
    assert _routing_policy({"GeoLocation": {"CountryCode": "US"}}) == "geo"
    assert _routing_policy({"MultiValueAnswer": True}) == "multivalue"
    assert _routing_policy({"SetIdentifier": "geoprox-1"}) is None
    assert _routing_policy({}) == "simple"


def test_list_hosted_zones_degrades_gracefully_when_vpc_lookup_denied(
    client_factory: ClientFactory,
) -> None:
    """A private zone whose get_hosted_zone call is denied is still
    returned -- just without linked_vpc_ids -- rather than failing the
    whole tool call."""
    real_client = boto3.client("route53")
    stubber = Stubber(real_client)
    stubber.add_response(
        "list_hosted_zones",
        {
            "HostedZones": [
                {
                    "Id": "/hostedzone/Z123",
                    "Name": "private.example.com.",
                    "CallerReference": "ref-1",
                    "Config": {"PrivateZone": True},
                    "ResourceRecordSetCount": 1,
                }
            ],
            "IsTruncated": False,
            "MaxItems": "100",
            "Marker": "",
        },
    )
    stubber.add_client_error(
        "get_hosted_zone",
        service_error_code="AccessDenied",
        service_message="User is not authorized to perform this action",
        http_status_code=403,
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        zones = list_hosted_zones(client_factory, region="us-east-1")

    assert len(zones) == 1
    assert zones[0].private_zone is True
    assert zones[0].linked_vpc_ids == []
    stubber.assert_no_pending_responses()


def test_list_resolver_endpoints(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    endpoints = list_resolver_endpoints(client_factory, region="us-east-1")
    endpoint_id = dns_fixture["resolver_endpoint_id"]
    match = next(e for e in endpoints if e.resolver_endpoint_id == endpoint_id)
    assert match.direction == "OUTBOUND"
    assert match.host_vpc_id == dns_fixture["vpc_id"]


def test_list_resolver_rules_without_associations(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    result = list_resolver_rules(client_factory, region="us-east-1")
    match = next(r for r in result.data if r.resolver_rule_id == dns_fixture["resolver_rule_id"])
    assert match.domain_name == "onprem.example.com."
    assert match.associated_vpc_ids is None


def test_list_resolver_rules_with_associations_shows_split_horizon_dns(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    """A FORWARD rule associated with a specific VPC, alongside a private
    hosted zone linked to that same VPC, is exactly the split-horizon DNS
    pattern the milestone asks tests to cover."""
    result = list_resolver_rules(client_factory, region="us-east-1", include_associations=True)
    match = next(r for r in result.data if r.resolver_rule_id == dns_fixture["resolver_rule_id"])
    assert match.associated_vpc_ids == [dns_fixture["vpc_id"]]


def test_resolver_rules_fanout_cap(dns_fixture: dict[str, str]) -> None:
    settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
    client_factory = ClientFactory(settings, SessionManager(settings))

    result = list_resolver_rules(client_factory, region="us-east-1", include_associations=True)
    match = next(r for r in result.data if r.resolver_rule_id == dns_fixture["resolver_rule_id"])
    assert match.associated_vpc_ids is None
    assert any(w.code == "FANOUT_CAP_REACHED" for w in result.warnings)


def test_list_resolver_rule_associations_filters_by_rule(
    client_factory: ClientFactory, dns_fixture: dict[str, str]
) -> None:
    associations = list_resolver_rule_associations(
        client_factory, region="us-east-1", resolver_rule_id=dns_fixture["resolver_rule_id"]
    )
    assert len(associations) == 1
    assert associations[0].vpc_id == dns_fixture["vpc_id"]


def test_list_resolver_query_log_configs(client_factory: ClientFactory) -> None:
    with mock_aws():
        r53r = boto3.client("route53resolver", region_name="us-east-1")
        created = r53r.create_resolver_query_log_config(
            Name="test-query-log",
            DestinationArn="arn:aws:s3:::my-query-log-bucket",
            CreatorRequestId="req-1",
        )["ResolverQueryLogConfig"]

        configs = list_resolver_query_log_configs(client_factory, region="us-east-1")

    match = next(c for c in configs if c.resolver_query_log_config_id == created["Id"])
    assert match.name == "test-query-log"
    assert match.destination_arn == "arn:aws:s3:::my-query-log-bucket"
    assert match.status == "CREATED"


# --- DNS Firewall: Stubber-based -----------------------------------------
#
# moto does not implement ListFirewallRuleGroups or
# ListFirewallRuleGroupAssociations at all (Python NotImplementedError),
# so both the happy path and the access-denied degradation path are
# stubbed against the real service model.


def test_list_dns_firewall_rule_groups_happy_path(client_factory: ClientFactory) -> None:
    """ListFirewallRuleGroups' actual response shape (per the botocore
    service model) carries only Id/Arn/Name/OwnerId/CreatorRequestId/
    ShareStatus -- RuleCount and Status are GetFirewallRuleGroup-only
    fields, so they are legitimately None from this call."""
    real_client = boto3.client("route53resolver", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "list_firewall_rule_groups",
        {
            "FirewallRuleGroups": [
                {
                    "Id": "rslvr-frg-abc123",
                    "Name": "test-firewall-group",
                    "OwnerId": "123456789012",
                    "ShareStatus": "NOT_SHARED",
                }
            ]
        },
        {},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_dns_firewall_rule_groups(client_factory, region="us-east-1")

    assert result.warnings == []
    assert len(result.data) == 1
    assert result.data[0].firewall_rule_group_id == "rslvr-frg-abc123"
    assert result.data[0].name == "test-firewall-group"
    assert result.data[0].rule_count is None
    stubber.assert_no_pending_responses()


def test_list_dns_firewall_rule_group_associations_happy_path(
    client_factory: ClientFactory,
) -> None:
    real_client = boto3.client("route53resolver", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "list_firewall_rule_group_associations",
        {
            "FirewallRuleGroupAssociations": [
                {
                    "Id": "rslvr-frgassoc-abc123",
                    "FirewallRuleGroupId": "rslvr-frg-abc123",
                    "VpcId": "vpc-abc123",
                    "Priority": 100,
                    "MutationProtection": "DISABLED",
                    "Status": "COMPLETE",
                }
            ]
        },
        {},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_dns_firewall_rule_group_associations(client_factory, region="us-east-1")

    assert result.warnings == []
    assert len(result.data) == 1
    assert result.data[0].vpc_id == "vpc-abc123"
    assert result.data[0].priority == 100
    stubber.assert_no_pending_responses()


def test_list_dns_firewall_rule_group_associations_degrades_gracefully_when_denied(
    client_factory: ClientFactory,
) -> None:
    real_client = boto3.client("route53resolver", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_client_error(
        "list_firewall_rule_group_associations",
        service_error_code="AccessDeniedException",
        service_message="User is not authorized to perform this action",
        http_status_code=403,
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_dns_firewall_rule_group_associations(client_factory, region="us-east-1")

    assert result.data == []
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "ACCESS_DENIED"
    stubber.assert_no_pending_responses()


def test_list_dns_firewall_rule_groups_degrades_gracefully_when_denied(
    client_factory: ClientFactory,
) -> None:
    """moto does not implement ListFirewallRuleGroups (raises a Python
    NotImplementedError, not a botocore ClientError -- not representative
    of what real AWS returns for a permission gap). Stubbed against a
    real AccessDeniedException instead, to prove the "where allowed"
    degradation path actually triggers on the error shape AWS would send."""
    real_client = boto3.client("route53resolver", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_client_error(
        "list_firewall_rule_groups",
        service_error_code="AccessDeniedException",
        service_message="User is not authorized to perform this action",
        http_status_code=403,
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_dns_firewall_rule_groups(client_factory, region="us-east-1")

    assert result.data == []
    assert len(result.warnings) == 1
    assert result.warnings[0].resource_type == "dns_firewall_rule_group"
    assert result.warnings[0].code == "ACCESS_DENIED"
    stubber.assert_no_pending_responses()


def test_list_hosted_zones_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_hosted_zones(client_factory, region="us-east-1") == []
