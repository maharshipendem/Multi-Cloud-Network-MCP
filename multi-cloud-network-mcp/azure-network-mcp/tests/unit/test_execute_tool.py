from __future__ import annotations

from typing import Any

import pytest
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)
from azure.core.exceptions import ResourceNotFoundError as AzureResourceNotFoundError
from azure.identity import CredentialUnavailableError

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.collection import CollectionResult
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings
from azure_network_mcp.exceptions import GuardrailViolationError
from azure_network_mcp.models.common import CollectionWarning
from azure_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_subscription


class _Model:
    def __init__(self, value: str) -> None:
        self.value = value

    def model_dump(self) -> dict[str, str]:
        return {"value": self.value}


def test_success_wraps_plain_data_in_ok_envelope() -> None:
    response = execute_tool(
        tool_name="azure_test_tool",
        subscription_id="sub-1",
        func=lambda: [1, 2, 3],
    )
    assert response["success"] is True
    assert response["data"] == [1, 2, 3]
    assert response["metadata"]["count"] == 3
    assert "request_id" in response["metadata"]
    assert response["subscription_id"] == "sub-1"


def test_success_serializes_pydantic_models_via_model_dump() -> None:
    response = execute_tool(
        tool_name="azure_test_tool",
        subscription_id="sub-1",
        func=lambda: [_Model("a"), _Model("b")],
    )
    assert response["data"] == [{"value": "a"}, {"value": "b"}]


def test_success_unwraps_collection_result_and_surfaces_warnings() -> None:
    warning = CollectionWarning(
        resource_type="resource_group", code="FANOUT_CAP_REACHED", message="m"
    )
    response = execute_tool(
        tool_name="azure_test_tool",
        subscription_id="sub-1",
        func=lambda: CollectionResult(data=[1, 2], warnings=[warning]),
    )
    assert response["data"] == [1, 2]
    assert response["metadata"]["warnings"] == [
        {"resource_type": "resource_group", "code": "FANOUT_CAP_REACHED", "message": "m"}
    ]


def test_azure_network_mcp_error_becomes_fail_envelope() -> None:
    def raiser() -> Any:
        raise GuardrailViolationError("blocked", error_type="GUARDRAIL_VIOLATION")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "GUARDRAIL_VIOLATION"
    assert response["error"]["message"] == "blocked"


def test_azure_resource_not_found_error_is_translated() -> None:
    def raiser() -> Any:
        raise AzureResourceNotFoundError("nope")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "RESOURCE_NOT_FOUND"


def test_credential_unavailable_error_is_translated_to_authentication_error() -> None:
    def raiser() -> Any:
        raise CredentialUnavailableError("no credential")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "AUTHENTICATION_ERROR"


def test_client_authentication_error_is_translated() -> None:
    def raiser() -> Any:
        raise ClientAuthenticationError("bad credential")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "AUTHENTICATION_ERROR"


@pytest.mark.parametrize(
    ("status_code", "expected_type"),
    [(401, "AUTHENTICATION_ERROR"), (403, "AUTHORIZATION_ERROR"), (404, "RESOURCE_NOT_FOUND")],
)
def test_http_response_error_status_codes_are_translated(
    status_code: int, expected_type: str
) -> None:
    def raiser() -> Any:
        error = HttpResponseError("boom")
        error.status_code = status_code
        raise error

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == expected_type


def test_http_response_error_unrecognized_status_becomes_azure_service_error() -> None:
    def raiser() -> Any:
        error = HttpResponseError("boom")
        error.status_code = 500
        raise error

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "AZURE_SERVICE_ERROR"


def test_service_request_error_is_translated() -> None:
    def raiser() -> Any:
        raise ServiceRequestError("connection refused")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "AZURE_SERVICE_ERROR"


def test_unexpected_exception_becomes_internal_error_and_is_not_leaked() -> None:
    def raiser() -> Any:
        raise ValueError("some internal detail that should not leak")

    response = execute_tool(tool_name="azure_test_tool", subscription_id="sub-1", func=raiser)
    assert response["success"] is False
    assert response["error"]["type"] == "INTERNAL_ERROR"
    assert "some internal detail" not in response["error"]["message"]


def test_resource_group_is_carried_through_the_envelope() -> None:
    response = execute_tool(
        tool_name="azure_test_tool",
        subscription_id="sub-1",
        resource_group="rg-1",
        func=lambda: [],
    )
    assert response["resource_group"] == "rg-1"


def test_each_call_gets_a_distinct_request_id() -> None:
    first = execute_tool(tool_name="t", subscription_id="sub-1", func=lambda: [])
    second = execute_tool(tool_name="t", subscription_id="sub-1", func=lambda: [])
    assert first["metadata"]["request_id"] != second["metadata"]["request_id"]


def test_execute_tool_with_resolved_subscription_reports_the_resolved_value() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id="default-sub")
    client_factory = ClientFactory(settings, SubscriptionContext(settings))

    response = execute_tool_with_resolved_subscription(
        tool_name="azure_test_tool",
        client_factory=client_factory,
        subscription_id=None,
        func=lambda resolved: [{"resolved": resolved}],
    )

    assert response["success"] is True
    assert response["subscription_id"] == "default-sub"
    assert response["data"] == [{"resolved": "default-sub"}]


def test_execute_tool_with_resolved_subscription_uses_explicit_value_over_default() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id="default-sub")
    client_factory = ClientFactory(settings, SubscriptionContext(settings))

    response = execute_tool_with_resolved_subscription(
        tool_name="azure_test_tool",
        client_factory=client_factory,
        subscription_id="explicit-sub",
        func=lambda resolved: [{"resolved": resolved}],
    )

    assert response["subscription_id"] == "explicit-sub"


def test_execute_tool_with_resolved_subscription_returns_error_envelope_when_disallowed() -> None:
    settings = Settings(_env_file=None, azure_subscription_allowlist="allowed-sub")
    client_factory = ClientFactory(settings, SubscriptionContext(settings))
    called = False

    def _func(resolved: str) -> Any:
        nonlocal called
        called = True
        return []

    response = execute_tool_with_resolved_subscription(
        tool_name="azure_test_tool",
        client_factory=client_factory,
        subscription_id="not-allowed-sub",
        func=_func,
    )

    assert response["success"] is False
    assert response["error"]["type"] == "SUBSCRIPTION_NOT_ALLOWED"
    assert response["subscription_id"] == "not-allowed-sub"
    assert called is False


def test_execute_tool_with_resolved_subscription_returns_error_envelope_when_no_default() -> None:
    settings = Settings(_env_file=None, azure_default_subscription_id=None)
    client_factory = ClientFactory(settings, SubscriptionContext(settings))

    response = execute_tool_with_resolved_subscription(
        tool_name="azure_test_tool",
        client_factory=client_factory,
        subscription_id=None,
        func=lambda resolved: [],
    )

    assert response["success"] is False
    assert response["error"]["type"] == "INVALID_CONFIGURATION"
