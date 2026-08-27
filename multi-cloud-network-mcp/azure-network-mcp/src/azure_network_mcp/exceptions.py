"""Custom exception hierarchy for azure-network-mcp.

All exceptions carry a stable machine-readable ``error_type`` so the tool
layer can translate them into a predictable MCP error envelope without
leaking internal details such as stack traces or raw Azure SDK payloads
(which can include request URLs carrying subscription/tenant IDs).
"""

from __future__ import annotations


class AzureNetworkMCPError(Exception):
    """Base class for all application-raised errors."""

    error_type: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_type: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_type is not None:
            self.error_type = error_type


class AuthenticationError(AzureNetworkMCPError):
    """Raised when Azure credentials are missing, invalid, or expired."""

    error_type = "AUTHENTICATION_ERROR"


class AuthorizationError(AzureNetworkMCPError):
    """Raised when the configured Azure identity lacks RBAC permission for a call."""

    error_type = "AUTHORIZATION_ERROR"


class AzureServiceError(AzureNetworkMCPError):
    """Raised for Azure ARM API errors that are not authentication/authorization."""

    error_type = "AZURE_SERVICE_ERROR"


class SubscriptionNotAllowedError(AzureNetworkMCPError):
    """Raised when a requested subscription ID is not in the configured allowlist."""

    error_type = "SUBSCRIPTION_NOT_ALLOWED"


class InvalidConfigurationError(AzureNetworkMCPError):
    """Raised for invalid or missing server configuration."""

    error_type = "INVALID_CONFIGURATION"


class ToolExecutionError(AzureNetworkMCPError):
    """Raised for unexpected failures, or invalid tool input, while executing a tool."""

    error_type = "TOOL_EXECUTION_ERROR"


class GuardrailViolationError(AuthorizationError):
    """Raised when an operation is rejected by the read-only security guardrails."""

    error_type = "GUARDRAIL_VIOLATION"


class ResourceNotFoundError(AzureNetworkMCPError):
    """Raised when a tool is asked to operate on a specific resource that
    does not exist in the configured subscription/resource group (e.g. an
    unknown VNet name passed to ``azure_get_vnet_topology``)."""

    error_type = "RESOURCE_NOT_FOUND"
