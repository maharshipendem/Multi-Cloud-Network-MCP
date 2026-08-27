from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.security import list_security_group_rules, list_security_groups


@pytest.fixture
def sg_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        web_sg = ec2.create_security_group(
            GroupName="web", Description="web tier", VpcId=vpc["VpcId"]
        )["GroupId"]
        db_sg = ec2.create_security_group(
            GroupName="db", Description="db tier", VpcId=vpc["VpcId"]
        )["GroupId"]

        ec2.authorize_security_group_ingress(
            GroupId=web_sg,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "public https"}],
                }
            ],
        )
        # db only accepts traffic from the web tier's security group -- an
        # SG-reference rule, the "SG references" fixture the milestone asks for.
        ec2.authorize_security_group_ingress(
            GroupId=db_sg,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 5432,
                    "ToPort": 5432,
                    "UserIdGroupPairs": [{"GroupId": web_sg}],
                }
            ],
        )
        yield {"vpc_id": vpc["VpcId"], "web_sg": web_sg, "db_sg": db_sg}


def test_list_security_groups_joins_rules(
    client_factory: ClientFactory, sg_fixture: dict[str, str]
) -> None:
    groups = list_security_groups(client_factory, region="us-east-1", vpc_id=sg_fixture["vpc_id"])
    web = next(g for g in groups if g.group_id == sg_fixture["web_sg"])

    ingress_rules = [r for r in web.rules if not r.is_egress]
    assert len(ingress_rules) == 1
    rule = ingress_rules[0]
    assert rule.security_group_rule_id  # stable rule ID present
    assert rule.from_port == 443
    assert rule.to_port == 443
    assert rule.peer.type == "ipv4"
    assert rule.peer.value == "0.0.0.0/0"
    assert rule.description == "public https"


def test_security_group_rule_peer_references_another_group(
    client_factory: ClientFactory, sg_fixture: dict[str, str]
) -> None:
    groups = list_security_groups(client_factory, region="us-east-1", vpc_id=sg_fixture["vpc_id"])
    db = next(g for g in groups if g.group_id == sg_fixture["db_sg"])
    ingress_rules = [r for r in db.rules if not r.is_egress and r.from_port == 5432]
    assert len(ingress_rules) == 1
    peer = ingress_rules[0].peer
    assert peer.type == "security_group"
    assert peer.referenced_group_id == sg_fixture["web_sg"]


def test_security_group_default_egress_rule_present(
    client_factory: ClientFactory, sg_fixture: dict[str, str]
) -> None:
    groups = list_security_groups(client_factory, region="us-east-1", vpc_id=sg_fixture["vpc_id"])
    web = next(g for g in groups if g.group_id == sg_fixture["web_sg"])
    assert any(r.is_egress for r in web.rules)  # AWS's default allow-all-egress rule


def test_list_security_group_rules_sorted_deterministically(
    client_factory: ClientFactory, sg_fixture: dict[str, str]
) -> None:
    rules = list_security_group_rules(
        client_factory,
        region="us-east-1",
        security_group_ids=[sg_fixture["web_sg"], sg_fixture["db_sg"]],
    )
    keys = [(r.security_group_id, r.is_egress, r.security_group_rule_id) for r in rules]
    assert keys == sorted(keys)


def test_list_security_groups_zero_resources_for_unmatched_vpc(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        # A default VPC (and its default SG) always exists in a fresh moto
        # region, so "zero resources" is exercised via a VPC filter that
        # matches nothing rather than an empty account.
        assert (
            list_security_groups(client_factory, region="us-east-1", vpc_id="vpc-doesnotexist")
            == []
        )
