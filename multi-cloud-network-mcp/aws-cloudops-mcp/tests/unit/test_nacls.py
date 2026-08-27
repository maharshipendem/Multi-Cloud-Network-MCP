from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.nacls import list_network_acls


@pytest.fixture
def nacl_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        nacl = ec2.create_network_acl(VpcId=vpc["VpcId"])["NetworkAcl"]
        nacl_id = nacl["NetworkAclId"]

        # Deliberately out of numeric order to prove the service layer sorts.
        ec2.create_network_acl_entry(
            NetworkAclId=nacl_id,
            RuleNumber=200,
            Protocol="6",
            RuleAction="allow",
            Egress=False,
            CidrBlock="10.0.0.0/16",
            PortRange={"From": 22, "To": 22},
        )
        ec2.create_network_acl_entry(
            NetworkAclId=nacl_id,
            RuleNumber=100,
            Protocol="6",
            RuleAction="allow",
            Egress=False,
            CidrBlock="0.0.0.0/0",
            PortRange={"From": 443, "To": 443},
        )
        # Move the subnet from its default NACL onto our custom one, so the
        # fixture has a real subnet association to assert on.
        default_acl = ec2.describe_network_acls(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc["VpcId"]]},
                {"Name": "default", "Values": ["true"]},
            ]
        )["NetworkAcls"][0]
        association_id = default_acl["Associations"][0]["NetworkAclAssociationId"]
        ec2.replace_network_acl_association(AssociationId=association_id, NetworkAclId=nacl_id)

        yield {"vpc_id": vpc["VpcId"], "subnet_id": subnet["SubnetId"], "nacl_id": nacl_id}


def test_network_acl_entries_sorted_by_direction_and_rule_number(
    client_factory: ClientFactory, nacl_fixture: dict[str, str]
) -> None:
    acls = list_network_acls(client_factory, region="us-east-1", vpc_id=nacl_fixture["vpc_id"])
    match = next(a for a in acls if a.network_acl_id == nacl_fixture["nacl_id"])

    ingress_entries = [e for e in match.entries if not e.egress]
    rule_numbers = [e.rule_number for e in ingress_entries]
    assert rule_numbers == sorted(rule_numbers)
    assert 100 in rule_numbers
    assert 200 in rule_numbers


def test_network_acl_association_present(
    client_factory: ClientFactory, nacl_fixture: dict[str, str]
) -> None:
    acls = list_network_acls(client_factory, region="us-east-1", vpc_id=nacl_fixture["vpc_id"])
    match = next(a for a in acls if a.network_acl_id == nacl_fixture["nacl_id"])
    assert any(a.subnet_id == nacl_fixture["subnet_id"] for a in match.associations)


def test_list_network_acls_zero_resources_for_unmatched_vpc(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert (
            list_network_acls(client_factory, region="us-east-1", vpc_id="vpc-doesnotexist") == []
        )
