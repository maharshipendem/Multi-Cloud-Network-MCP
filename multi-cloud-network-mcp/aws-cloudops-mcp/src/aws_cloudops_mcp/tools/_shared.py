"""Shared tool-execution plumbing: correlation IDs, logging, and error translation.

Every MCP tool function in this package delegates its body to
``execute_tool`` so that logging, the response envelope, and exception
translation are implemented exactly once instead of being duplicated (and
inevitably drifting) across five-plus tool modules.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
)

from aws_cloudops_mcp.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AWSCloudOpsMCPError,
    AWSServiceError,
    InvalidRegionError,
)
from aws_cloudops_mcp.logging.setup import get_logger, request_id_var
from aws_cloudops_mcp.models.responses import ToolResponse

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_logger = get_logger("aws_cloudops_mcp.tools")

_AUTHENTICATION_ERROR_CODES = {
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "ExpiredToken",
    "ExpiredTokenException",
    "AuthFailure",
}
_AUTHORIZATION_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "Unauthorized",
}


def _translate_client_error(exc: ClientError) -> AWSCloudOpsMCPError:
    error = exc.response.get("Error", {})
    code = error.get("Code", "Unknown")

    if code in _AUTHENTICATION_ERROR_CODES:
        return AuthenticationError(
            "The configured AWS credentials could not be validated.",
            error_type="AUTHENTICATION_ERROR",
        )
    if code in _AUTHORIZATION_ERROR_CODES:
        return AuthorizationError(
            f"The configured AWS identity does not have permission to perform "
            f"this action ({code}).",
            error_type="AUTHORIZATION_ERROR",
        )
    return AWSServiceError(
        f"The AWS API returned an error ({code}).", error_type="AWS_SERVICE_ERROR"
    )


def execute_tool(
    *,
    tool_name: str,
    client_factory: ClientFactory,
    region: str | None,
    role_arn: str | None = None,
    func: Callable[[], Any],
) -> dict[str, Any]:
    """Run ``func`` under a correlation ID, log the outcome, and return an envelope.

    ``func`` should return already-normalized data (e.g. a list of pydantic
    models or a single model); this wrapper handles serialization,
    account-id enrichment, logging, and translating any raised exception
    into the standard error envelope. ``func`` must not raise anything
    other than ``AWSCloudOpsMCPError`` subclasses or botocore exceptions.
    """
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.monotonic()
    status = "success"
    account_id: str | None = None

    try:
        try:
            account_id = client_factory.get_account_id(role_arn=role_arn)
        except Exception:  # noqa: BLE001 - identity lookup is best-effort here
            account_id = None

        try:
            data = func()
        except AWSCloudOpsMCPError:
            raise
        except ClientError as exc:
            raise _translate_client_error(exc) from exc
        except NoCredentialsError as exc:
            raise AuthenticationError("No AWS credentials could be found.") from exc
        except (EndpointConnectionError, NoRegionError) as exc:
            raise InvalidRegionError(
                "Could not connect to the AWS endpoint for the specified region."
            ) from exc

        payload = _to_jsonable(data)
        metadata: dict[str, Any] = {"request_id": request_id}
        if isinstance(payload, list):
            metadata["count"] = len(payload)

        return ToolResponse.ok(
            tool=tool_name,
            data=payload,
            account_id=account_id,
            region=region,
            metadata=metadata,
        ).model_dump()

    except AWSCloudOpsMCPError as exc:
        status = "error"
        _logger.warning(
            "tool invocation failed: %s",
            exc.message,
            extra={"tool_name": tool_name, "aws_error_code": exc.error_type},
        )
        return ToolResponse.fail(
            tool=tool_name,
            error_type=exc.error_type,
            message=exc.message,
            account_id=account_id,
            region=region,
            metadata={"request_id": request_id},
        ).model_dump()

    except Exception:
        status = "error"
        _logger.exception("unhandled tool error", extra={"tool_name": tool_name})
        return ToolResponse.fail(
            tool=tool_name,
            error_type="INTERNAL_ERROR",
            message="An unexpected internal error occurred while executing the tool.",
            account_id=account_id,
            region=region,
            metadata={"request_id": request_id},
        ).model_dump()

    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        _logger.info(
            "tool_invocation",
            extra={
                "tool_name": tool_name,
                "account_id": account_id,
                "region": region,
                "duration_ms": duration_ms,
                "status": status,
            },
        )
        request_id_var.reset(token)


def _to_jsonable(data: Any) -> Any:
    if isinstance(data, list):
        return [_to_jsonable(item) for item in data]
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data
