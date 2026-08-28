"""Translates raw ``google.api_core.exceptions`` into this codebase's
own exception hierarchy.

This is the one place that decides whether a 403 means "the caller
lacks IAM permission" (``AuthorizationError``) or "the required GCP API
is not enabled on this project" (``ApiNotEnabledError``) -- the two are
easy to conflate because Compute Engine returns the same HTTP status
(403 Forbidden) for both, distinguished only by message text. Getting
this right matters: per this project's guardrails, an API-not-enabled
response must never be silently treated as "this project has zero
resources of this type" -- callers (the service layer, then the tool
layer) use the resulting ``ApiNotEnabledError``/``AuthorizationError``
to surface an explicit partial-result warning instead of an empty list.
"""

from __future__ import annotations

from google.api_core import exceptions as gax

from gcp_network_mcp.exceptions import (
    ApiNotEnabledError,
    AuthorizationError,
    GcpNetworkMCPError,
    GcpServiceError,
    ResourceNotFoundError,
)

_DISABLED_API_MARKERS = (
    "has not been used in project",
    "it is disabled",
    "api is not enabled",
    "accessnotconfigured",
    "service_disabled",
)


def translate_gcp_error(
    exc: Exception, *, resource_type: str, project_id: str | None = None
) -> GcpNetworkMCPError:
    """Map a raw GCP client library exception to a ``GcpNetworkMCPError``.

    ``resource_type``/``project_id`` are folded into the resulting
    message only -- never used to change control flow -- so callers can
    tell which collection step failed without re-deriving it from the
    original exception.
    """
    project_suffix = f" in project '{project_id}'" if project_id else ""
    if isinstance(exc, gax.NotFound):
        return ResourceNotFoundError(f"{resource_type} not found{project_suffix}: {exc.message}")
    if isinstance(exc, gax.Forbidden):
        message = (exc.message or str(exc)).lower()
        if any(marker in message for marker in _DISABLED_API_MARKERS):
            return ApiNotEnabledError(
                f"A GCP API required to list {resource_type}{project_suffix} "
                f"is not enabled: {exc.message}"
            )
        return AuthorizationError(
            f"Not authorized to list {resource_type}{project_suffix}: {exc.message}"
        )
    if isinstance(exc, gax.GoogleAPICallError):
        return GcpServiceError(
            f"GCP API error while listing {resource_type}{project_suffix}: {exc.message}"
        )
    return GcpServiceError(f"Unexpected error while listing {resource_type}: {exc}")


__all__ = ["translate_gcp_error"]
