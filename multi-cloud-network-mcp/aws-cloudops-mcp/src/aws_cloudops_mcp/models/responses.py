"""Standard MCP tool response envelope.

Every tool in aws-cloudops-mcp returns exactly this shape, whether it
succeeds or fails, so MCP clients can rely on a single predictable schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """Normalized, client-safe error detail. Never contains stack traces."""

    type: str
    message: str


class ToolResponse(BaseModel):
    """Standard envelope returned by every aws-cloudops-mcp tool."""

    success: bool
    tool: str
    account_id: str | None = None
    region: str | None = None
    data: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: ToolError | None = None

    @classmethod
    def ok(
        cls,
        *,
        tool: str,
        data: Any,
        account_id: str | None = None,
        region: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=True,
            tool=tool,
            account_id=account_id,
            region=region,
            data=data,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        *,
        tool: str,
        error_type: str,
        message: str,
        account_id: str | None = None,
        region: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=False,
            tool=tool,
            account_id=account_id,
            region=region,
            data=None,
            metadata=metadata or {},
            error=ToolError(type=error_type, message=message),
        )
