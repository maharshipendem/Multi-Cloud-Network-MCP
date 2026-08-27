"""The MCP tool response envelope.

Mirrors the response-envelope *concept* this project's AWS sibling
established (``success``/``tool``/scoping-context/``data``/``metadata``/
``error``) while every field stays Azure-native: ``subscription_id``
(and, where relevant, ``resource_group``) in place of AWS's
``account_id``/``region``, since an Azure ARM call is subscription-scoped
rather than region-scoped -- most of this milestone's tools return
resources spanning every Azure region in a subscription, not one region
per call.
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
    subscription_id: str | None = None
    resource_group: str | None = None
    data: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None

    @classmethod
    def ok(
        cls,
        *,
        tool: str,
        data: Any,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=True,
            tool=tool,
            subscription_id=subscription_id,
            resource_group=resource_group,
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
        subscription_id: str | None = None,
        resource_group: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResponse:
        return cls(
            success=False,
            tool=tool,
            subscription_id=subscription_id,
            resource_group=resource_group,
            data=None,
            metadata=metadata or {},
            error=ErrorDetail(type=error_type, message=message),
        )


__all__ = ["ErrorDetail", "ToolResponse"]
