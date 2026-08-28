"""The MCP tool response envelope.

Mirrors the response-envelope *concept* this project's AWS/Azure siblings
established (``success``/``tool``/scoping-context/``data``/``metadata``/
``error``) while every field stays GCP-native: ``project_id`` in place of
AWS's ``account_id``/Azure's ``subscription_id``. Provider-native in
naming, not yet runtime-coupled to the sibling servers' envelopes --
Milestone 9 unifies this across clouds.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    type: str
    message: str


class ToolResponse(BaseModel):
    success: bool
    tool: str
    project_id: str | None = None
    data: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None

    @classmethod
    def ok(
        cls,
        *,
        tool: str,
        data: Any,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=True,
            tool=tool,
            project_id=project_id,
            data=data,
            metadata=metadata or {},
            error=None,
        )

    @classmethod
    def fail(
        cls,
        *,
        tool: str,
        error_type: str,
        message: str,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=False,
            tool=tool,
            project_id=project_id,
            data=None,
            metadata=metadata or {},
            error=ErrorDetail(type=error_type, message=message),
        )


__all__ = ["ErrorDetail", "ToolResponse"]
