from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from azure_network_mcp.arm.readonly import call_readonly, call_readonly_lro
from azure_network_mcp.exceptions import GuardrailViolationError


def test_call_readonly_invokes_the_named_method_with_kwargs() -> None:
    operation_group = MagicMock()
    operation_group.list.return_value = ["a", "b"]

    result = call_readonly(operation_group, "list", resource_group_name="rg-1")

    operation_group.list.assert_called_once_with(resource_group_name="rg-1")
    assert result == ["a", "b"]


def test_call_readonly_rejects_mutating_method_before_calling_it() -> None:
    operation_group = MagicMock()
    with pytest.raises(GuardrailViolationError):
        call_readonly(operation_group, "begin_delete", resource_group_name="rg-1")
    operation_group.begin_delete.assert_not_called()


def test_call_readonly_lro_resolves_the_poller() -> None:
    operation_group = MagicMock()
    poller = MagicMock()
    poller.result.return_value = "resolved-value"
    operation_group.begin_get_effective_route_table.return_value = poller

    result = call_readonly_lro(
        operation_group,
        "begin_get_effective_route_table",
        resource_group_name="rg-1",
        network_interface_name="nic-1",
    )

    poller.result.assert_called_once_with()
    assert result == "resolved-value"


def test_call_readonly_lro_rejects_unallowlisted_begin_methods() -> None:
    operation_group = MagicMock()
    with pytest.raises(GuardrailViolationError):
        call_readonly_lro(operation_group, "begin_create_or_update", resource_group_name="rg-1")
    operation_group.begin_create_or_update.assert_not_called()
