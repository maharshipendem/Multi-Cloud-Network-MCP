from __future__ import annotations

import pytest

from azure_network_mcp.exceptions import GuardrailViolationError
from azure_network_mcp.security.guardrails import (
    BLOCKED_ACTIONS,
    READ_ONLY_ACTIONS,
    assert_read_only_operation,
)


@pytest.mark.parametrize(
    "method_name",
    [
        "get",
        "list",
        "list_all",
        "list_locations",
        "get_effective_route_table_ignored",  # starts with "get"
    ],
)
def test_allows_get_and_list_prefixed_methods(method_name: str) -> None:
    assert_read_only_operation(method_name)  # must not raise


@pytest.mark.parametrize("method_name", sorted(READ_ONLY_ACTIONS))
def test_allows_explicitly_allowlisted_lro_read_operations(method_name: str) -> None:
    assert_read_only_operation(method_name)  # must not raise


@pytest.mark.parametrize("method_name", sorted(BLOCKED_ACTIONS))
def test_blocks_known_mutating_operations(method_name: str) -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation(method_name)


@pytest.mark.parametrize(
    "method_name",
    [
        "begin_create_or_update",
        "begin_delete",
        "begin_reset_virtual_machine",
        "update_tags",
        "create_or_update",
        "delete",
        "put_bastion_shareable_link",
        "cancel",
        "restart",
        "reset",
        "generate_vpn_profile",
        "rotate_virtual_wan_key",
        "purge",
        "failover",
        "swap_public_ip_addresses",
        "move_ip_configurations",
        "prepare_network_policies",
        "unprepare_network_policies",
        "migrate_to_ip_based",
    ],
)
def test_blocks_every_documented_mutating_keyword(method_name: str) -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation(method_name)


def test_blocks_unrecognized_method_names_by_default() -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation("some_future_sdk_method")


def test_blocked_keyword_match_is_whole_word_not_substring() -> None:
    # "get_updated_summary" contains "update" as a substring but not as a
    # whole underscore-delimited word -- must not be blocked by that alone,
    # and does start with the "get" prefix, so it's allowed.
    assert_read_only_operation("get_updated_summary")


def test_case_and_whitespace_insensitive() -> None:
    assert_read_only_operation("  LIST_ALL  ")
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation("  BEGIN_DELETE  ")
