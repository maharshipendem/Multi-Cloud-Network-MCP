"""The single call-site every non-paginated AWS API call must go through.

Pairs with ``pagination.paginate`` for paginated calls. Both funnel through
``security.guardrails.assert_read_only_operation`` so no AWS service-layer
function can invoke a mutating operation, paginated or not.
"""

from __future__ import annotations

from typing import Any, Protocol

from aws_cloudops_mcp.aws.collection import record_call
from aws_cloudops_mcp.security.guardrails import assert_read_only_operation


class _BotoClient(Protocol):
    def __getattr__(self, name: str) -> Any: ...


def call_readonly(client: _BotoClient, operation_name: str, **kwargs: Any) -> Any:
    """Invoke ``client.<operation_name>(**kwargs)`` after a guardrail check."""
    assert_read_only_operation(operation_name)
    method = getattr(client, operation_name)
    record_call()
    return method(**kwargs)
