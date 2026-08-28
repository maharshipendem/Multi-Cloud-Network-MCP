"""Standard request/response/error/partial-result/pagination metadata --
the one envelope shape every cloud repo's normalized-export tool wraps
its data in. Deliberately mirrors the ``{success, tool, ..., data,
metadata, error}`` shape all three cloud repos already independently
converged on (see each repo's ``models/responses.py``) rather than
inventing something novel; the only real change is replacing each
repo's flat, provider-specific scope fields (``account_id``/``region``
vs. ``subscription_id``/``resource_group`` vs. ``project_id``) with one
shared ``CloudScope``.

``data`` stays ``Any`` (not a Pydantic generic) on purpose: a normalized
export tool's payload shape varies by call (one resource, a list of
resources, a topology graph, a list of findings), and a generic
``ResponseEnvelope[T]`` would need a distinct JSON Schema ``$id`` per
concrete ``T`` -- more machinery than this contract's actual consumers
need. Structural validity of ``data`` is instead the job of whichever
resource/topology/diagnostic schema the caller already knows to expect
for a given tool.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from multicloud_network_mcp.contracts.models.common import CloudScope
from multicloud_network_mcp.contracts.models.enums import Completeness


class ErrorDetail(BaseModel):
    """Normalized, client-safe error detail -- never a stack trace or
    raw provider exception repr. ``provider_error_code`` preserves the
    provider's own error code/type string (e.g. botocore's
    ``AccessDenied``, an ARM error code, a ``google.api_core.exceptions``
    class name) for a consumer that wants provider-specific handling
    without this contract needing to enumerate every provider's error
    taxonomy."""

    type: str
    message: str
    provider_error_code: str | None = None


class CollectionWarning(BaseModel):
    """A non-fatal issue collecting one resource type/scope -- a
    disabled API, a missing IAM/RBAC permission, an unreachable
    region/scope, a bounded fan-out cap reached. Identical in spirit to
    what all three cloud repos already call ``CollectionWarning``;
    unified here into one shape.

    ``resource_type`` is free text (not the closed ``ResourceType``
    enum) because a warning can legitimately be about something outside
    this contract's 19 canonical resource kinds (e.g. a Shared VPC host
    status lookup, a metrics query) -- ``resource_type_hint`` is set
    when the warning genuinely does concern one of the canonical types,
    for a consumer that wants to filter/aggregate by it.

    A disabled API or missing permission must never be silently treated
    as "this scope has zero resources of this type" -- it must surface
    here instead. See ``docs/normalization.md``'s partial-result
    guardrail and ``tests/contracts/test_partial_collections.py``.
    """

    resource_type: str
    resource_type_hint: str | None = None
    code: str
    message: str
    scope: CloudScope | None = None


class PartialResultMetadata(BaseModel):
    """Whether a response reflects everything the requested scope
    actually contains, or only what could be collected. ``completeness``
    is ``PARTIAL`` whenever ``warnings`` is non-empty -- enforced here at
    construction time (raises ``ValueError``, not just a documented
    convention a caller could violate by mistake); see
    ``tests/contracts/test_partial_collections.py``."""

    completeness: Completeness = Completeness.COMPLETE
    warnings: list[CollectionWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def _partial_whenever_warnings_present(self) -> PartialResultMetadata:
        if self.warnings and self.completeness != Completeness.PARTIAL:
            raise ValueError(
                "completeness must be PARTIAL whenever warnings is non-empty "
                f"(got completeness={self.completeness!r} with {len(self.warnings)} warning(s))"
            )
        return self


class PaginationMetadata(BaseModel):
    """Present only on a response whose ``data`` is a bounded/paginated
    collection. ``next_cursor`` is opaque and provider-defined --
    meaningful only to the same tool that issued it, never something
    this contract parses or constructs itself (each cloud repo's own
    pagination internals stay entirely its own concern; this contract
    only standardizes how "there was more, here's how much we returned,
    and whether it was capped" is reported)."""

    returned_items: int
    max_items: int | None = None
    truncated: bool = False
    next_cursor: str | None = None


class ResponseEnvelope(BaseModel):
    """The standard wrapper every normalized-export MCP tool call
    returns. ``request_id`` correlates one call with its logs; distinct
    from any resource's own ``urn``."""

    success: bool
    tool: str
    contract_version: str
    request_id: str
    scope: CloudScope
    data: Any | None = None
    pagination: PaginationMetadata | None = None
    partial_result: PartialResultMetadata | None = None
    error: ErrorDetail | None = None

    @classmethod
    def ok(
        cls,
        *,
        tool: str,
        contract_version: str,
        request_id: str,
        scope: CloudScope,
        data: Any,
        pagination: PaginationMetadata | None = None,
        partial_result: PartialResultMetadata | None = None,
    ) -> ResponseEnvelope:
        return cls(
            success=True,
            tool=tool,
            contract_version=contract_version,
            request_id=request_id,
            scope=scope,
            data=data,
            pagination=pagination,
            partial_result=partial_result,
            error=None,
        )

    @classmethod
    def fail(
        cls,
        *,
        tool: str,
        contract_version: str,
        request_id: str,
        scope: CloudScope,
        error: ErrorDetail,
    ) -> ResponseEnvelope:
        return cls(
            success=False,
            tool=tool,
            contract_version=contract_version,
            request_id=request_id,
            scope=scope,
            data=None,
            error=error,
        )


__all__ = [
    "CollectionWarning",
    "ErrorDetail",
    "PaginationMetadata",
    "PartialResultMetadata",
    "ResponseEnvelope",
]
