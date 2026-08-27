"""Reusable pagination handling for AWS list/describe APIs.

AWS APIs frequently paginate; a tool that only reads the first page will
silently under-report results. ``paginate`` walks every page via boto3's
built-in paginators (falling back to a single call for non-paginated
operations) and applies a safety cap so a single tool invocation cannot
return an unbounded response.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import OperationNotPageableError

from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.security.guardrails import assert_read_only_operation

DEFAULT_MAX_ITEMS = 1000


def paginate(
    client: Any,
    operation_name: str,
    result_key: str,
    *,
    max_items: int = DEFAULT_MAX_ITEMS,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Return up to ``max_items`` results from ``result_key`` across all pages."""
    assert_read_only_operation(operation_name)

    try:
        paginator = client.get_paginator(operation_name)
    except OperationNotPageableError:
        response = call_readonly(client, operation_name, **kwargs)
        return list(response.get(result_key, []))[:max_items]

    items: list[dict[str, Any]] = []
    pagination_config = {"MaxItems": max_items}
    for page in paginator.paginate(PaginationConfig=pagination_config, **kwargs):
        items.extend(page.get(result_key, []))
        if len(items) >= max_items:
            break
    return items[:max_items]
