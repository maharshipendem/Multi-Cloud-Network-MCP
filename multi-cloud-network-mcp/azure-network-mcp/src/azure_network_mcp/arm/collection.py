"""Shared collection-time bookkeeping: timestamps, an Azure-call counter,
and the ``CollectionResult`` wrapper for partial-result warnings.

The counter is opt-in via ``track_calls()`` and, when active, is
incremented by ``arm.pagination.paginate()`` exactly once per underlying
Azure REST request (each page of a paged result counts separately). It
powers ``azure_get_vnet_topology``'s call-count field and any
recorded-call-budget tests -- outside a ``track_calls()`` block it is a
no-op.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from azure_network_mcp.models.common import CollectionWarning


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


@dataclass
class CollectionResult:
    """A service-layer return value that may carry partial-result warnings."""

    data: Any
    warnings: list[CollectionWarning] = field(default_factory=list)


@dataclass
class CallCounter:
    count: int = 0


_call_counter: ContextVar[CallCounter | None] = ContextVar("call_counter", default=None)


@contextmanager
def track_calls() -> Iterator[CallCounter]:
    counter = CallCounter()
    token = _call_counter.set(counter)
    try:
        yield counter
    finally:
        _call_counter.reset(token)


def record_call() -> None:
    counter = _call_counter.get()
    if counter is not None:
        counter.count += 1


__all__ = ["CallCounter", "CollectionResult", "now_iso", "record_call", "track_calls"]
