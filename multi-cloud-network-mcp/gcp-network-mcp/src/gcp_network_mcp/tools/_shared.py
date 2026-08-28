"""Shared tool-execution plumbing: correlation IDs, logging, and error translation.

Every MCP tool function in this package delegates its body to
``execute_tool`` so that logging, the response envelope, and exception
translation are implemented exactly once instead of being duplicated (and
inevitably drifting) across a dozen-plus tool modules.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from google.api_core import exceptions as gax
from google.auth import exceptions as google_auth_exceptions

from gcp_network_mcp.exceptions import AuthenticationError, GcpNetworkMCPError
from gcp_network_mcp.gcp.collection import CollectionResult
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.logging.setup import get_logger, request_id_var
from gcp_network_mcp.models.responses import ToolResponse

if TYPE_CHECKING:
    from gcp_network_mcp.auth.session import ResourceContext

_logger = get_logger("gcp_network_mcp.tools")


def execute_tool(
    *,
    tool_name: str,
    project_id: str | None,
    func: Callable[[], Any],
) -> dict[str, Any]:
    """Run ``func`` under a correlation ID, log the outcome, and return an envelope.

    ``func`` should return already-normalized data (e.g. a list of
    pydantic models, a single model, or a ``CollectionResult``); this
    wrapper handles serialization, logging, and translating any raised
    exception into the standard error envelope. ``func`` may raise
    ``GcpNetworkMCPError`` subclasses or a raw ``google.api_core``/
    ``google.auth`` exception -- both are translated, so service-layer
    functions that don't go through ``gcp.pagination``/``gcp.readonly``
    (e.g. a single non-paginated call) are still covered here as a
    safety net.
    """
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.monotonic()
    status = "success"

    try:
        try:
            data = func()
        except GcpNetworkMCPError:
            raise
        except google_auth_exceptions.DefaultCredentialsError as exc:
            raise AuthenticationError(
                "No usable Application Default Credentials could be found. Run "
                "'gcloud auth application-default login', or configure a service "
                "account/workload identity for this environment.",
                error_type="AUTHENTICATION_ERROR",
            ) from exc
        except google_auth_exceptions.RefreshError as exc:
            raise AuthenticationError(
                "The configured Google credentials could not be refreshed.",
                error_type="AUTHENTICATION_ERROR",
            ) from exc
        except gax.GoogleAPICallError as exc:
            raise translate_gcp_error(exc, resource_type=tool_name) from exc

        warnings: list[Any] = []
        if isinstance(data, CollectionResult):
            warnings = data.warnings
            data = data.data

        payload = _to_jsonable(data)
        metadata: dict[str, Any] = {"request_id": request_id}
        if isinstance(payload, list):
            metadata["count"] = len(payload)
        if warnings:
            metadata["warnings"] = [_to_jsonable(w) for w in warnings]

        return ToolResponse.ok(
            tool=tool_name,
            data=payload,
            project_id=project_id,
            metadata=metadata,
        ).model_dump()

    except GcpNetworkMCPError as exc:
        status = "error"
        _logger.warning(
            "tool invocation failed: %s",
            exc.message,
            extra={"tool_name": tool_name, "gcp_error_code": exc.error_type},
        )
        return ToolResponse.fail(
            tool=tool_name,
            error_type=exc.error_type,
            message=exc.message,
            project_id=project_id,
            metadata={"request_id": request_id},
        ).model_dump()

    except Exception:
        status = "error"
        _logger.exception("unhandled tool error", extra={"tool_name": tool_name})
        return ToolResponse.fail(
            tool=tool_name,
            error_type="INTERNAL_ERROR",
            message="An unexpected internal error occurred while executing the tool.",
            project_id=project_id,
            metadata={"request_id": request_id},
        ).model_dump()

    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        _logger.info(
            "tool_invocation",
            extra={
                "tool_name": tool_name,
                "project_id": project_id,
                "duration_ms": duration_ms,
                "status": status,
            },
        )
        request_id_var.reset(token)


def execute_tool_with_resolved_project(
    *,
    tool_name: str,
    resource_context: ResourceContext,
    project_id: str | None,
    func: Callable[[str], Any],
) -> dict[str, Any]:
    """Like ``execute_tool``, but also resolves ``project_id`` (falling
    back to ``Settings.gcp_default_project_id``, then validating against
    the configured allowlist) *inside* the same guarded call.

    Every tool that accepts an optional ``project_id`` needs this: doing
    the resolution before calling ``execute_tool`` would raise
    ``InvalidConfigurationError``/``ProjectNotAllowedError`` outside
    ``execute_tool``'s try/except, crashing the MCP tool call instead of
    returning this server's normal structured error envelope. ``func``
    receives the resolved project ID and should call the GCP service
    layer with it. On success, the returned envelope's ``project_id`` is
    the *resolved* value (not just the caller's possibly-omitted input),
    matching every other tool's convention of reporting the scope
    actually queried.
    """
    resolved_box: dict[str, str] = {}

    def _run() -> Any:
        resolved = resource_context.resolve_project_id(project_id)
        resolved_box["value"] = resolved
        return func(resolved)

    response = execute_tool(tool_name=tool_name, project_id=project_id, func=_run)
    if "value" in resolved_box:
        response["project_id"] = resolved_box["value"]
    return response


def _to_jsonable(data: Any) -> Any:
    if isinstance(data, list):
        return [_to_jsonable(item) for item in data]
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data
