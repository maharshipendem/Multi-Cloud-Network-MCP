"""Shared collection-time bookkeeping: timestamps and an AWS-call counter.

The counter is opt-in via ``track_calls()`` and, when active, is
incremented by ``aws.readonly.call_readonly`` and ``aws.pagination.paginate``
exactly once per underlying AWS API request (each page of a paginated call
counts separately). It powers ``aws_get_vpc_topology``'s ``api_call_count``
field and the recorded-call-budget test -- outside of a ``track_calls()``
block it is a no-op, so it has zero effect on every other tool.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aws_cloudops_mcp.models.common import CollectionWarning


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


@dataclass
class CollectionResult:
    """A service-layer return value that may carry partial-result warnings.

    Most list functions can just return a plain ``list[Model]`` -- this
    wrapper is only for functions capable of a *partial* result (bounded
    fan-out reached, an optional enrichment call denied by IAM, etc.).
    ``tools._shared.execute_tool`` unwraps it into ``data``/``metadata``.
    """

    data: Any
    warnings: list[CollectionWarning] = field(default_factory=list)


class CallCounter:
    """A mutable counter of AWS API requests made within a ``track_calls()`` block."""

    def __init__(self) -> None:
        self.count = 0

    def increment(self) -> None:
        self.count += 1


_active_counter: ContextVar[CallCounter | None] = ContextVar("_active_counter", default=None)


@contextmanager
def track_calls() -> Iterator[CallCounter]:
    """Count every AWS API request made by code running inside this block."""
    counter = CallCounter()
    token = _active_counter.set(counter)
    try:
        yield counter
    finally:
        _active_counter.reset(token)


def record_call() -> None:
    """Increment the active counter, if any. No-op outside ``track_calls()``."""
    counter = _active_counter.get()
    if counter is not None:
        counter.increment()
