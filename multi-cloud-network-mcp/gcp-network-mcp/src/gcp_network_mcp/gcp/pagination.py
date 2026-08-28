"""Reusable pagination handling for GCP Compute Engine ``list``/
``aggregated_list`` operations.

Both ``ListPager`` and ``AggregatedListPager`` fetch additional pages
lazily as they're iterated (one underlying HTTP request per page); a tool
that doesn't cap consumption can trigger an unbounded number of requests
against a project with many resources. ``paginate``/``paginate_aggregated``
walk pages via ``.pages`` (one request per page, for call-counting) and
apply a safety cap so a single tool invocation cannot return an unbounded
response.

``paginate_aggregated`` additionally surfaces two distinct signals GCP's
aggregated-list responses carry that a naive flatten-and-return would
lose: each page's ``unreachables`` (scopes -- regions/zones -- that could
not be queried) and each per-scope ``ScopedList.warning`` (e.g. a scope
temporarily degraded). ``NO_RESULTS_ON_PAGE`` is GCP's own "this scope
genuinely has zero resources" signal and is filtered out as benign;
every other warning code is surfaced as a ``CollectionWarning`` so a
caller never mistakes a degraded/unreachable scope for an empty one.
"""

from __future__ import annotations

from typing import Any

from google.api_core import exceptions as gax

from gcp_network_mcp.gcp.collection import record_call
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.security.guardrails import assert_read_only_operation

DEFAULT_MAX_ITEMS = 1000

_BENIGN_WARNING_CODES = frozenset({"NO_RESULTS_ON_PAGE"})


def paginate(
    operation_group: Any,
    method_name: str,
    *,
    resource_type: str,
    project_id: str | None = None,
    max_items: int = DEFAULT_MAX_ITEMS,
    items_field: str = "items",
    **kwargs: Any,
) -> list[Any]:
    """Call ``operation_group.<method_name>(**kwargs)`` (asserted
    read-only) and return up to ``max_items`` results, flattened across
    pages. Raises a translated ``GcpNetworkMCPError`` (never a raw
    ``google.api_core`` exception) on failure.

    ``items_field`` defaults to ``"items"`` (the field name on every
    standard ``List*`` response) but is overridable for the handful of
    list-shaped calls that use a different field name (e.g.
    ``ProjectsClient.get_xpn_resources``, whose response uses
    ``"resources"``)."""
    assert_read_only_operation(method_name)
    try:
        pager = call_readonly(operation_group, method_name, **kwargs)
        items: list[Any] = []
        for page in pager.pages:
            record_call()  # each page is one real GCP API request
            for item in getattr(page, items_field):
                items.append(item)
                if len(items) >= max_items:
                    return items
        return items
    except gax.GoogleAPICallError as exc:
        raise translate_gcp_error(exc, resource_type=resource_type, project_id=project_id) from exc


def paginate_aggregated(
    operation_group: Any,
    method_name: str,
    *,
    items_field: str,
    resource_type: str,
    project_id: str | None = None,
    max_items: int = DEFAULT_MAX_ITEMS,
    **kwargs: Any,
) -> tuple[list[Any], list[CollectionWarning]]:
    """Call ``operation_group.<method_name>(**kwargs)`` (an
    ``aggregated_list``-shaped, asserted read-only call) and return up to
    ``max_items`` results flattened across every region/zone scope,
    alongside any non-benign per-scope warnings and unreachable scopes.

    ``items_field`` names the field on each scope's ``*ScopedList``
    message holding that scope's resources (e.g. ``"subnetworks"``,
    ``"instances"``, ``"routers"``) -- this varies per resource type, so
    callers pass it explicitly rather than this function guessing it.
    """
    assert_read_only_operation(method_name)
    items: list[Any] = []
    warnings: list[CollectionWarning] = []
    try:
        pager = call_readonly(operation_group, method_name, **kwargs)
        for page in pager.pages:
            record_call()  # each page is one real GCP API request
            for scope_key, scoped_list in page.items.items():
                warning_code = scoped_list.warning.code
                if warning_code and warning_code not in _BENIGN_WARNING_CODES:
                    warnings.append(
                        CollectionWarning(
                            resource_type=resource_type,
                            code=warning_code,
                            message=scoped_list.warning.message or warning_code,
                            project_id=project_id,
                            scope=scope_key,
                        )
                    )
                for item in getattr(scoped_list, items_field):
                    items.append(item)
                    if len(items) >= max_items:
                        return items, warnings
            for unreachable_scope in page.unreachables:
                warnings.append(
                    CollectionWarning(
                        resource_type=resource_type,
                        code="UNREACHABLE",
                        message=(
                            f"Scope '{unreachable_scope}' was unreachable "
                            f"while listing {resource_type}."
                        ),
                        project_id=project_id,
                        scope=unreachable_scope,
                    )
                )
        return items, warnings
    except gax.GoogleAPICallError as exc:
        raise translate_gcp_error(exc, resource_type=resource_type, project_id=project_id) from exc


__all__ = ["DEFAULT_MAX_ITEMS", "paginate", "paginate_aggregated"]
