"""Reusable pagination handling for Azure SDK list operations.

Azure SDK list/list_all methods return an ``ItemPaged`` iterator that
transparently issues additional REST requests as it's consumed; a tool
that doesn't cap consumption can trigger an unbounded number of requests
against a large subscription. ``paginate`` walks pages via ``by_page()``
(one REST request per page) and applies a safety cap so a single tool
invocation cannot return an unbounded response.
"""

from __future__ import annotations

from typing import Any

from azure_network_mcp.arm.collection import record_call
from azure_network_mcp.arm.readonly import call_readonly
from azure_network_mcp.security.guardrails import assert_read_only_operation

DEFAULT_MAX_ITEMS = 1000


def paginate(
    operation_group: Any,
    method_name: str,
    *,
    max_items: int = DEFAULT_MAX_ITEMS,
    **kwargs: Any,
) -> list[Any]:
    """Call ``operation_group.<method_name>(**kwargs)`` (asserted
    read-only) and return up to ``max_items`` results, flattened across
    pages."""
    assert_read_only_operation(method_name)
    pageable = call_readonly(operation_group, method_name, **kwargs)

    items: list[Any] = []
    for page in pageable.by_page():
        record_call()  # each page is one real Azure REST request
        for item in page:
            items.append(item)
            if len(items) >= max_items:
                return items
    return items


__all__ = ["DEFAULT_MAX_ITEMS", "paginate"]
