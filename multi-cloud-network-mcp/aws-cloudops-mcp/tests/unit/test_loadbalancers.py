from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.loadbalancers import list_load_balancers
from aws_cloudops_mcp.config import Settings


@pytest.fixture
def alb_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet_a = ec2.create_subnet(
            VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )["Subnet"]
        subnet_b = ec2.create_subnet(
            VpcId=vpc["VpcId"], CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )["Subnet"]

        elbv2 = boto3.client("elbv2", region_name="us-east-1")
        lb = elbv2.create_load_balancer(
            Name="test-alb",
            Subnets=[subnet_a["SubnetId"], subnet_b["SubnetId"]],
            Type="application",
            Tags=[{"Key": "Name", "Value": "test-alb"}],
        )["LoadBalancers"][0]
        tg = elbv2.create_target_group(
            Name="test-tg",
            Protocol="HTTP",
            Port=80,
            VpcId=vpc["VpcId"],
            TargetType="ip",
        )["TargetGroups"][0]
        elbv2.add_tags(
            ResourceArns=[tg["TargetGroupArn"]], Tags=[{"Key": "Name", "Value": "test-tg"}]
        )
        elbv2.create_listener(
            LoadBalancerArn=lb["LoadBalancerArn"],
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg["TargetGroupArn"]}],
        )
        elbv2.register_targets(
            TargetGroupArn=tg["TargetGroupArn"], Targets=[{"Id": "10.0.1.5", "Port": 80}]
        )

        yield {
            "vpc_id": vpc["VpcId"],
            "lb_arn": lb["LoadBalancerArn"],
            "tg_arn": tg["TargetGroupArn"],
            "subnet_a": subnet_a["SubnetId"],
            "subnet_b": subnet_b["SubnetId"],
        }


def test_list_load_balancers_joins_listeners_and_target_groups(
    client_factory: ClientFactory, alb_fixture: dict[str, str]
) -> None:
    result = list_load_balancers(client_factory, region="us-east-1", vpc_id=alb_fixture["vpc_id"])
    lb = next(x for x in result.data if x.load_balancer_arn == alb_fixture["lb_arn"])

    assert lb.type == "application"
    assert lb.tags == {"Name": "test-alb"}
    assert {az.subnet_id for az in lb.availability_zones} == {
        alb_fixture["subnet_a"],
        alb_fixture["subnet_b"],
    }
    assert len(lb.listeners) == 1
    assert lb.listeners[0].port == 80
    assert lb.listeners[0].default_actions[0].target_group_arn == alb_fixture["tg_arn"]

    assert len(lb.target_groups) == 1
    tg = lb.target_groups[0]
    assert tg.target_group_arn == alb_fixture["tg_arn"]
    assert tg.tags == {"Name": "test-tg"}
    assert tg.targets is None  # not requested
    assert result.warnings == []


def test_list_load_balancers_include_target_health(
    client_factory: ClientFactory, alb_fixture: dict[str, str]
) -> None:
    result = list_load_balancers(
        client_factory,
        region="us-east-1",
        vpc_id=alb_fixture["vpc_id"],
        include_target_health=True,
    )
    lb = next(x for x in result.data if x.load_balancer_arn == alb_fixture["lb_arn"])
    tg = lb.target_groups[0]
    assert tg.targets is not None
    assert len(tg.targets) == 1
    assert tg.targets[0].target_id == "10.0.1.5"


def test_list_load_balancers_target_health_respects_fanout_cap(
    alb_fixture: dict[str, str],
) -> None:
    settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
    client_factory = ClientFactory(settings, SessionManager(settings))

    result = list_load_balancers(
        client_factory,
        region="us-east-1",
        vpc_id=alb_fixture["vpc_id"],
        include_target_health=True,
    )
    lb = next(x for x in result.data if x.load_balancer_arn == alb_fixture["lb_arn"])
    assert lb.target_groups[0].targets is None
    assert any(w.code == "FANOUT_CAP_REACHED" for w in result.warnings)


def test_list_load_balancers_filters_by_arn(
    client_factory: ClientFactory, alb_fixture: dict[str, str]
) -> None:
    result = list_load_balancers(
        client_factory, region="us-east-1", load_balancer_arns=[alb_fixture["lb_arn"]]
    )
    assert [lb.load_balancer_arn for lb in result.data] == [alb_fixture["lb_arn"]]


def test_list_load_balancers_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        result = list_load_balancers(client_factory, region="us-east-1")
        assert result.data == []
        assert result.warnings == []
