"""Tests for the shared tool-execution wrapper: envelope shape and error translation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from aws_cloudops_mcp.exceptions import GuardrailViolationError, InvalidRegionError
from aws_cloudops_mcp.tools._shared import execute_tool


@pytest.fixture
def fake_client_factory() -> MagicMock:
    factory = MagicMock()
    factory.get_account_id.return_value = "123456789012"
    return factory


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="DescribeVpcs",
    )


def test_success_envelope_shape(fake_client_factory: MagicMock) -> None:
    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="us-east-1",
        func=lambda: [{"vpc_id": "vpc-1"}],
    )

    assert result["success"] is True
    assert result["tool"] == "aws_list_vpcs"
    assert result["account_id"] == "123456789012"
    assert result["region"] == "us-east-1"
    assert result["data"] == [{"vpc_id": "vpc-1"}]
    assert result["metadata"]["count"] == 1
    assert "request_id" in result["metadata"]
    assert result["error"] is None


def test_application_error_envelope(fake_client_factory: MagicMock) -> None:
    def _raise() -> None:
        raise InvalidRegionError("'bogus' is not a valid AWS region identifier.")

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="bogus",
        func=_raise,
    )

    assert result["success"] is False
    assert result["error"]["type"] == "INVALID_REGION"
    assert "bogus" in result["error"]["message"]
    assert result["data"] is None


def test_guardrail_violation_maps_to_authorization_error(fake_client_factory: MagicMock) -> None:
    def _raise() -> None:
        raise GuardrailViolationError("blocked")

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="us-east-1",
        func=_raise,
    )
    assert result["success"] is False
    assert result["error"]["type"] == "GUARDRAIL_VIOLATION"


@pytest.mark.parametrize(
    "code,expected_type",
    [
        ("AccessDenied", "AUTHORIZATION_ERROR"),
        ("UnauthorizedOperation", "AUTHORIZATION_ERROR"),
        ("InvalidClientTokenId", "AUTHENTICATION_ERROR"),
        ("ExpiredToken", "AUTHENTICATION_ERROR"),
        ("Throttling", "AWS_SERVICE_ERROR"),
    ],
)
def test_client_error_translation(
    fake_client_factory: MagicMock, code: str, expected_type: str
) -> None:
    def _raise() -> None:
        raise _client_error(code)

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="us-east-1",
        func=_raise,
    )
    assert result["success"] is False
    assert result["error"]["type"] == expected_type
    assert "boom" not in result["error"]["message"]  # raw AWS message not leaked verbatim


def test_no_credentials_error_translation(fake_client_factory: MagicMock) -> None:
    def _raise() -> None:
        raise NoCredentialsError()

    result = execute_tool(
        tool_name="aws_get_caller_identity",
        client_factory=fake_client_factory,
        region=None,
        func=_raise,
    )
    assert result["success"] is False
    assert result["error"]["type"] == "AUTHENTICATION_ERROR"


def test_endpoint_connection_error_translation(fake_client_factory: MagicMock) -> None:
    def _raise() -> None:
        raise EndpointConnectionError(endpoint_url="https://ec2.bogus.amazonaws.com")

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="bogus-region-1",
        func=_raise,
    )
    assert result["success"] is False
    assert result["error"]["type"] == "INVALID_REGION"


def test_unexpected_exception_does_not_leak_internals(fake_client_factory: MagicMock) -> None:
    def _raise() -> None:
        raise ValueError("some internal detail: /etc/secret/path")

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="us-east-1",
        func=_raise,
    )
    assert result["success"] is False
    assert result["error"]["type"] == "INTERNAL_ERROR"
    assert "/etc/secret/path" not in result["error"]["message"]


def test_account_id_lookup_failure_does_not_block_tool_execution(
    fake_client_factory: MagicMock,
) -> None:
    fake_client_factory.get_account_id.side_effect = RuntimeError("identity lookup failed")

    result = execute_tool(
        tool_name="aws_list_vpcs",
        client_factory=fake_client_factory,
        region="us-east-1",
        func=lambda: [{"vpc_id": "vpc-1"}],
    )

    assert result["success"] is True
    assert result["account_id"] is None
