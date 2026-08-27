"""The single call-site every ARM SDK invocation in this codebase must go
through -- funnels every call past
``security.guardrails.assert_read_only_operation`` before it reaches the
Azure SDK.
"""

from __future__ import annotations

from typing import Any

from azure_network_mcp.security.guardrails import assert_read_only_operation


def call_readonly(operation_group: Any, method_name: str, /, **kwargs: Any) -> Any:
    """Call ``operation_group.<method_name>(**kwargs)`` after asserting it
    is read-only. Returns the call's raw result (a model, a Pageable
    iterator, or an LROPoller for the two explicitly allowlisted
    long-running read operations -- see ``call_readonly_lro`` below for
    the common case of also resolving the poller)."""
    assert_read_only_operation(method_name)
    method = getattr(operation_group, method_name)
    return method(**kwargs)


def call_readonly_lro(operation_group: Any, method_name: str, /, **kwargs: Any) -> Any:
    """Like ``call_readonly``, but for the two explicitly allowlisted
    ``begin_*`` long-running *read* operations (effective route table,
    effective NSGs): resolves the returned ``LROPoller`` and returns its
    final result, since callers of those two operations want the
    computed data, not the poller object."""
    poller = call_readonly(operation_group, method_name, **kwargs)
    return poller.result()


__all__ = ["call_readonly", "call_readonly_lro"]
