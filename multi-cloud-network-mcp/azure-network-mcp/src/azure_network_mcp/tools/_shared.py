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

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)
from azure.core.exceptions import ResourceNotFoundError as AzureResourceNotFoundError
from azure.identity import CredentialUnavailableError

from azure_network_mcp.arm.collection import CollectionResult
from azure_network_mcp.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AzureNetworkMCPError,
    AzureServiceError,
    ResourceNotFoundError,
)
from azure_network_mcp.logging.setup import get_logger, request_id_var
from azure_network_mcp.models.responses import ToolResponse

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory

_logger = get_logger("azure_network_mcp.tools")


def _translate_http_error(exc: HttpResponseError) -> AzureNetworkMCPError:
    status = getattr(exc, "status_code", None)
    code = getattr(getattr(exc, "error", None), "code", None) or "Unknown"

    if status == 401:
        return AuthenticationError(
            "The configured Azure credential could not be validated.",
            error_type="AUTHENTICATION_ERROR",
        )
    if status == 403:
        return AuthorizationError(
            f"The configured Azure identity does not have permission to perform "
            f"this action ({code}).",
            error_type="AUTHORIZATION_ERROR",
        )
    if status == 404:
        return ResourceNotFoundError(
            f"The requested Azure resource was not found ({code}).",
            error_type="RESOURCE_NOT_FOUND",
        )
    return AzureServiceError(
        f"The Azure API returned an error ({code}).", error_type="AZURE_SERVICE_ERROR"
    )


def execute_tool(
    *,
    tool_name: str,
    subscription_id: str | None,
    resource_group: str | None = None,
    func: Callable[[], Any],
) -> dict[str, Any]:
    """Run ``func`` under a correlation ID, log the outcome, and return an envelope.

    ``func`` should return already-normalized data (e.g. a list of
    pydantic models or a single model); this wrapper handles
    serialization, logging, and translating any raised exception into
    the standard error envelope. ``func`` must not raise anything other
    than ``AzureNetworkMCPError`` subclasses or Azure SDK exceptions.
    """
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.monotonic()
    status = "success"

    try:
        try:
            data = func()
        except AzureNetworkMCPError:
            raise
        except AzureResourceNotFoundError as exc:
            raise ResourceNotFoundError(
                "The requested Azure resource was not found.", error_type="RESOURCE_NOT_FOUND"
            ) from exc
        except CredentialUnavailableError as exc:
            raise AuthenticationError(
                "No usable Azure credential could be found.", error_type="AUTHENTICATION_ERROR"
            ) from exc
        except ClientAuthenticationError as exc:
            raise AuthenticationError(
                "The configured Azure credential could not be validated.",
                error_type="AUTHENTICATION_ERROR",
            ) from exc
        except HttpResponseError as exc:
            raise _translate_http_error(exc) from exc
        except ServiceRequestError as exc:
            raise AzureServiceError(
                "Could not connect to the Azure Resource Manager endpoint.",
                error_type="AZURE_SERVICE_ERROR",
            ) from exc

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
            subscription_id=subscription_id,
            resource_group=resource_group,
            metadata=metadata,
        ).model_dump()

    except AzureNetworkMCPError as exc:
        status = "error"
        _logger.warning(
            "tool invocation failed: %s",
            exc.message,
            extra={"tool_name": tool_name, "azure_error_code": exc.error_type},
        )
        return ToolResponse.fail(
            tool=tool_name,
            error_type=exc.error_type,
            message=exc.message,
            subscription_id=subscription_id,
            resource_group=resource_group,
            metadata={"request_id": request_id},
        ).model_dump()

    except Exception:
        status = "error"
        _logger.exception("unhandled tool error", extra={"tool_name": tool_name})
        return ToolResponse.fail(
            tool=tool_name,
            error_type="INTERNAL_ERROR",
            message="An unexpected internal error occurred while executing the tool.",
            subscription_id=subscription_id,
            resource_group=resource_group,
            metadata={"request_id": request_id},
        ).model_dump()

    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        _logger.info(
            "tool_invocation",
            extra={
                "tool_name": tool_name,
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "duration_ms": duration_ms,
                "status": status,
            },
        )
        request_id_var.reset(token)


def execute_tool_with_resolved_subscription(
    *,
    tool_name: str,
    client_factory: ClientFactory,
    subscription_id: str | None,
    resource_group: str | None = None,
    func: Callable[[str], Any],
) -> dict[str, Any]:
    """Like ``execute_tool``, but also resolves ``subscription_id`` (falling
    back to ``Settings.azure_default_subscription_id``, then validating
    against the configured allowlist) *inside* the same guarded call.

    Every tool that accepts an optional ``subscription_id`` needs this: doing
    the resolution before calling ``execute_tool`` would raise
    ``InvalidConfigurationError``/``SubscriptionNotAllowedError`` outside
    ``execute_tool``'s try/except, crashing the MCP tool call instead of
    returning this server's normal structured error envelope. ``func``
    receives the resolved subscription ID and should call the ARM service
    layer with it. On success, the returned envelope's ``subscription_id``
    is the *resolved* value (not just the caller's possibly-omitted input),
    matching every other tool's convention of reporting the scope actually
    queried.
    """
    resolved_box: dict[str, str] = {}

    def _run() -> Any:
        resolved = client_factory.subscription_context.resolve_subscription_id(subscription_id)
        resolved_box["value"] = resolved
        return func(resolved)

    response = execute_tool(
        tool_name=tool_name,
        subscription_id=subscription_id,
        resource_group=resource_group,
        func=_run,
    )
    if "value" in resolved_box:
        response["subscription_id"] = resolved_box["value"]
    return response


def _to_jsonable(data: Any) -> Any:
    if isinstance(data, list):
        return [_to_jsonable(item) for item in data]
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data
