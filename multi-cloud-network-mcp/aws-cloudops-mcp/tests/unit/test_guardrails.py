from __future__ import annotations

import pytest

from aws_cloudops_mcp.exceptions import GuardrailViolationError
from aws_cloudops_mcp.security.guardrails import (
    BLOCKED_ACTIONS,
    READ_ONLY_ACTIONS,
    assert_read_only_operation,
)

READ_ONLY_OPERATIONS = [
    "get_caller_identity",
    "describe_regions",
    "describe_vpcs",
    "describe_subnets",
    "describe_route_tables",
    "list_tags_for_resource",
    "describe_vpc_attribute",
]

BLOCKED_OPERATIONS = [
    "create_vpc",
    "delete_vpc",
    "modify_vpc_attribute",
    "update_route",
    "attach_internet_gateway",
    "detach_internet_gateway",
    "associate_route_table",
    "disassociate_route_table",
    "start_instances",
    "stop_instances",
    "reboot_instances",
    "terminate_instances",
    "put_bucket_policy",
    "authorize_security_group_ingress",
    "revoke_security_group_egress",
    "run_instances",
]


@pytest.mark.parametrize("operation", READ_ONLY_OPERATIONS)
def test_read_only_operations_are_permitted(operation: str) -> None:
    assert_read_only_operation(operation)  # must not raise


@pytest.mark.parametrize("operation", BLOCKED_OPERATIONS)
def test_mutating_operations_are_rejected(operation: str) -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation(operation)


def test_unrecognized_prefix_is_rejected() -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation("do_something_unexpected")


def test_declared_read_only_actions_all_pass() -> None:
    for operation in READ_ONLY_ACTIONS:
        assert_read_only_operation(operation)


def test_declared_blocked_actions_all_fail() -> None:
    for operation in BLOCKED_ACTIONS:
        with pytest.raises(GuardrailViolationError):
            assert_read_only_operation(operation)
