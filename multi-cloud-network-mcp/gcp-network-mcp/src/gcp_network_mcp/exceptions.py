"""Custom exception hierarchy for gcp-network-mcp.

All exceptions carry a stable machine-readable ``error_type`` so the tool
layer can translate them into a predictable MCP error envelope without
leaking internal details such as stack traces or raw GCP API payloads.
"""

from __future__ import annotations


class GcpNetworkMCPError(Exception):
    """Base class for all application-raised errors."""

    error_type: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_type: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_type is not None:
            self.error_type = error_type


class AuthenticationError(GcpNetworkMCPError):
    """Raised when Application Default Credentials are missing, invalid, or expired."""

    error_type = "AUTHENTICATION_ERROR"


class AuthorizationError(GcpNetworkMCPError):
    """Raised when the configured identity lacks IAM permission for a call."""

    error_type = "AUTHORIZATION_ERROR"


class GcpServiceError(GcpNetworkMCPError):
    """Raised for GCP API errors that are not authentication/authorization."""

    error_type = "GCP_SERVICE_ERROR"


class ApiNotEnabledError(GcpNetworkMCPError):
    """Raised when a GCP API required for a call is not enabled on the
    target project. Never treated as "this project has zero resources of
    this type" -- see docs/security.md#never-treat-disabled-as-empty."""

    error_type = "API_NOT_ENABLED"


class ProjectNotAllowedError(GcpNetworkMCPError):
    """Raised when a requested project/folder/organization ID is not in
    the configured allowlist."""

    error_type = "PROJECT_NOT_ALLOWED"


class InvalidConfigurationError(GcpNetworkMCPError):
    """Raised for invalid or missing server configuration."""

    error_type = "INVALID_CONFIGURATION"


class ToolExecutionError(GcpNetworkMCPError):
    """Raised for unexpected failures, or invalid tool input, while executing a tool."""

    error_type = "TOOL_EXECUTION_ERROR"


class GuardrailViolationError(AuthorizationError):
    """Raised when an operation is rejected by the read-only security guardrails."""

    error_type = "GUARDRAIL_VIOLATION"


class ResourceNotFoundError(GcpNetworkMCPError):
    """Raised when a tool is asked to operate on a specific resource that
    does not exist in the configured project/region/zone."""

    error_type = "RESOURCE_NOT_FOUND"
