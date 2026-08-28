from __future__ import annotations

from google.api_core import exceptions as gax
from google.auth import exceptions as auth_exceptions

from gcp_network_mcp.exceptions import ResourceNotFoundError
from gcp_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_project


def test_execute_tool_ok_path_serializes_pydantic_model() -> None:
    from gcp_network_mcp.models.identity import CallerIdentity

    response = execute_tool(
        tool_name="t",
        project_id=None,
        func=lambda: CallerIdentity(credential_type="X"),
    )
    assert response["success"] is True
    assert response["data"]["credential_type"] == "X"


def test_execute_tool_wraps_collection_result_warnings_into_metadata() -> None:
    from gcp_network_mcp.gcp.collection import CollectionResult
    from gcp_network_mcp.models.common import CollectionWarning

    response = execute_tool(
        tool_name="t",
        project_id="p1",
        func=lambda: CollectionResult(
            data=[1, 2], warnings=[CollectionWarning(resource_type="x", code="C", message="m")]
        ),
    )
    assert response["data"] == [1, 2]
    assert response["metadata"]["count"] == 2
    assert response["metadata"]["warnings"][0]["code"] == "C"


def test_execute_tool_passes_through_domain_error() -> None:
    def _raise() -> None:
        raise ResourceNotFoundError("gone", error_type="RESOURCE_NOT_FOUND")

    response = execute_tool(tool_name="t", project_id=None, func=_raise)
    assert response["success"] is False
    assert response["error"]["type"] == "RESOURCE_NOT_FOUND"


def test_execute_tool_translates_raw_google_api_call_error() -> None:
    """A service-layer function that (incorrectly) let a raw
    google.api_core exception escape must still be translated -- this is
    the safety net for anything not already covered by
    gcp.pagination/gcp.readonly's own translation."""

    def _raise() -> None:
        raise gax.NotFound("no such thing")

    response = execute_tool(tool_name="t", project_id=None, func=_raise)
    assert response["success"] is False
    assert response["error"]["type"] == "RESOURCE_NOT_FOUND"


def test_execute_tool_translates_default_credentials_error() -> None:
    def _raise() -> None:
        raise auth_exceptions.DefaultCredentialsError("no adc")

    response = execute_tool(tool_name="t", project_id=None, func=_raise)
    assert response["error"]["type"] == "AUTHENTICATION_ERROR"


def test_execute_tool_translates_refresh_error() -> None:
    def _raise() -> None:
        raise auth_exceptions.RefreshError("expired")

    response = execute_tool(tool_name="t", project_id=None, func=_raise)
    assert response["error"]["type"] == "AUTHENTICATION_ERROR"


def test_execute_tool_wraps_unexpected_exception_as_internal_error() -> None:
    def _raise() -> None:
        raise RuntimeError("boom")

    response = execute_tool(tool_name="t", project_id=None, func=_raise)
    assert response["success"] is False
    assert response["error"]["type"] == "INTERNAL_ERROR"
    assert "unexpected" in response["error"]["message"].lower()


def test_execute_tool_with_resolved_project_reports_resolved_value() -> None:
    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.config import Settings

    ctx = ResourceContext(Settings(_env_file=None, gcp_default_project_id="resolved-proj"))
    response = execute_tool_with_resolved_project(
        tool_name="t", resource_context=ctx, project_id=None, func=lambda resolved: [resolved]
    )
    assert response["project_id"] == "resolved-proj"
    assert response["data"] == ["resolved-proj"]


def test_execute_tool_with_resolved_project_keeps_original_on_resolution_failure() -> None:
    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.config import Settings

    ctx = ResourceContext(Settings(_env_file=None))  # no default, no allowlist
    response = execute_tool_with_resolved_project(
        tool_name="t", resource_context=ctx, project_id=None, func=lambda resolved: [resolved]
    )
    assert response["success"] is False
    assert response["project_id"] is None
    assert response["error"]["type"] == "INVALID_CONFIGURATION"
