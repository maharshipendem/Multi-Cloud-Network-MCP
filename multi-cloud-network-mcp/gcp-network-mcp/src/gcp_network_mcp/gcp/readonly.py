"""The single call-site every GCP client library invocation in this
codebase must go through -- funnels every call past
``security.guardrails.assert_read_only_operation`` before it reaches the
GCP client library.
"""

from __future__ import annotations

from typing import Any

from gcp_network_mcp.security.guardrails import assert_read_only_operation


def call_readonly(operation_group: Any, method_name: str, /, **kwargs: Any) -> Any:
    """Call ``operation_group.<method_name>(**kwargs)`` after asserting it
    is read-only. Returns the call's raw result (a proto-plus message, or
    a ``ListPager``/``AggregatedListPager`` for list-shaped calls)."""
    assert_read_only_operation(method_name)
    method = getattr(operation_group, method_name)
    return method(**kwargs)


__all__ = ["call_readonly"]
