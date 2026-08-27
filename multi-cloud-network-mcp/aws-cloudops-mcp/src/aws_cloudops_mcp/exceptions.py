"""Custom exception hierarchy for aws-cloudops-mcp.

All exceptions carry a stable machine-readable ``error_type`` so the tool
layer can translate them into a predictable MCP error envelope without
leaking internal details such as stack traces or raw botocore payloads.
"""

from __future__ import annotations


class AWSCloudOpsMCPError(Exception):
    """Base class for all application-raised errors."""

    error_type: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_type: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_type is not None:
            self.error_type = error_type


class AuthenticationError(AWSCloudOpsMCPError):
    """Raised when AWS credentials are missing, invalid, or expired."""

    error_type = "AUTHENTICATION_ERROR"


class AuthorizationError(AWSCloudOpsMCPError):
    """Raised when the configured AWS identity lacks permission for a call."""

    error_type = "AUTHORIZATION_ERROR"


class AWSServiceError(AWSCloudOpsMCPError):
    """Raised for AWS API errors that are not authentication/authorization."""

    error_type = "AWS_SERVICE_ERROR"


class InvalidRegionError(AWSCloudOpsMCPError):
    """Raised when a region is malformed or cannot be reached."""

    error_type = "INVALID_REGION"


class InvalidConfigurationError(AWSCloudOpsMCPError):
    """Raised for invalid or missing server configuration (e.g. bad profile)."""

    error_type = "INVALID_CONFIGURATION"


class ToolExecutionError(AWSCloudOpsMCPError):
    """Raised for unexpected failures while executing a tool."""

    error_type = "TOOL_EXECUTION_ERROR"


class GuardrailViolationError(AuthorizationError):
    """Raised when an operation is rejected by the read-only security guardrails."""

    error_type = "GUARDRAIL_VIOLATION"
