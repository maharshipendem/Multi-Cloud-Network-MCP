from __future__ import annotations

import pytest
from google.api_core import exceptions as gax

from gcp_network_mcp.exceptions import (
    ApiNotEnabledError,
    AuthorizationError,
    GcpServiceError,
    GuardrailViolationError,
    ResourceNotFoundError,
)
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.security.guardrails import assert_read_only_operation

# --- guardrails ---------------------------------------------------------


@pytest.mark.parametrize(
    "method_name",
    [
        "list",
        "get",
        "aggregated_list",
        "search_projects",
        "list_xpn_hosts",
        "get_xpn_host",
        "get_xpn_resources",
        "get_health",
        "get_effective_firewalls",
        "list_peering_routes",
        "list_usable",
        "get_nat_ip_info",
        "get_router_status",
    ],
)
def test_read_only_methods_are_permitted(method_name: str) -> None:
    assert_read_only_operation(method_name)  # must not raise


@pytest.mark.parametrize(
    "method_name",
    [
        "insert",
        "delete",
        "patch",
        "update",
        "set_labels",
        "set_iam_policy",
        "add_peering",
        "remove_peering",
        "enable_xpn_host",
        "disable_xpn_host",
        "start_instance",
        "stop_instance",
        "reset_instance",
        "attach_disk",
        "bulk_insert",
    ],
)
def test_mutating_methods_are_blocked(method_name: str) -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation(method_name)


def test_unrecognized_method_name_is_blocked() -> None:
    with pytest.raises(GuardrailViolationError):
        assert_read_only_operation("frobnicate")


def test_blocked_keyword_check_matches_whole_words_only() -> None:
    # "list_updated_resources" contains "update" as a substring but not as
    # a whole "_"-delimited word segment -- must not be blocked by that.
    assert_read_only_operation("list_updated_resources")


# --- error translation ---------------------------------------------------


def _forbidden(message: str) -> gax.Forbidden:
    return gax.Forbidden(message)


def test_translate_not_found() -> None:
    error = translate_gcp_error(gax.NotFound("nope"), resource_type="network", project_id="p1")
    assert isinstance(error, ResourceNotFoundError)
    assert "network" in error.message


def test_translate_forbidden_with_disabled_api_marker() -> None:
    error = translate_gcp_error(
        _forbidden("Compute Engine API has not been used in project 123 before or it is disabled."),
        resource_type="network",
        project_id="p1",
    )
    assert isinstance(error, ApiNotEnabledError)


def test_translate_forbidden_without_disabled_marker_is_authorization_error() -> None:
    error = translate_gcp_error(
        _forbidden("Required 'compute.networks.list' permission"),
        resource_type="network",
        project_id="p1",
    )
    assert isinstance(error, AuthorizationError)
    assert not isinstance(error, ApiNotEnabledError)


def test_translate_generic_api_call_error() -> None:
    error = translate_gcp_error(gax.BadRequest("bad"), resource_type="network")
    assert isinstance(error, GcpServiceError)


def test_translate_non_api_error_still_returns_service_error() -> None:
    error = translate_gcp_error(ValueError("boom"), resource_type="network")
    assert isinstance(error, GcpServiceError)
