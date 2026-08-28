"""Static regression guard: no ``gcp/*.py`` service-layer module may spell
out a mutating GCP client library method name as a string literal call
target.

This complements ``test_guardrails_and_errors.py`` (which tests the
guardrail function's logic in isolation): this test scans the actual
source of every ``gcp/*.py`` module for a hardcoded mutating method name,
so a future service-layer function that bypasses
``call_readonly``/``paginate``/``paginate_aggregated`` entirely (and
therefore never reaches the guardrail check at runtime) still gets caught
here rather than only in a live GCP project.
"""

from __future__ import annotations

import ast
from pathlib import Path

from gcp_network_mcp.security.guardrails import BLOCKED_ACTIONS, BLOCKED_KEYWORDS

GCP_DIR = Path(__file__).parent.parent.parent / "src" / "gcp_network_mcp" / "gcp"


_DISPATCH_FUNCTIONS = {"call_readonly", "paginate", "paginate_aggregated"}


def _method_name_arguments_in_module(path: Path) -> list[str]:
    """Every string literal passed as the ``method_name`` argument to a
    guardrail-dispatching call (``call_readonly``/``paginate``/
    ``paginate_aggregated``'s second positional argument) -- not every
    string literal in the module, since GCP field names like
    ``"enable_flow_logs"`` legitimately contain guardrail keywords
    without being a method-name argument at all.
    """
    tree = ast.parse(path.read_text())
    literals: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DISPATCH_FUNCTIONS
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            literals.append(node.args[1].value)
    return literals


def test_no_gcp_module_references_a_mutating_method_name_literal() -> None:
    violations: list[str] = []
    for path in sorted(GCP_DIR.glob("*.py")):
        for literal in _method_name_arguments_in_module(path):
            name = literal.lower()
            words = set(name.split("_"))
            if words & BLOCKED_KEYWORDS or literal in BLOCKED_ACTIONS:
                violations.append(f"{path.name}: {literal!r}")
    assert not violations, f"Found mutating method-name literals: {violations}"


def test_no_gcp_module_calls_a_client_method_that_bypasses_readonly_or_pagination() -> None:
    """Every attribute-call on something named like a GCP client
    (``*_client``, ``client``, or a ``client_factory.<method>()`` result)
    must be routed through ``call_readonly``/``paginate``/
    ``paginate_aggregated`` -- never called directly as
    ``some_client.list(...)``. This catches a hypothetical future
    shortcut that would skip the guardrail check entirely.
    """
    allowed_direct_call_names = {
        "call_readonly",
        "paginate",
        "paginate_aggregated",
        "record_call",
        "track_calls",
        "translate_gcp_error",
    }
    violations: list[str] = []
    for path in sorted(GCP_DIR.glob("*.py")):
        if path.name in {
            "readonly.py",
            "pagination.py",
            "collection.py",
            "errors.py",
            "__init__.py",
        }:
            continue  # these modules implement the choke point itself
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method_name = node.func.attr
            if method_name in allowed_direct_call_names:
                continue
            # Only flag calls that look like they're on a *_client()-shaped
            # receiver and use a name matching the read-only/mutating
            # vocabulary -- avoids false positives on unrelated `.append()`,
            # `.extend()`, pydantic `.model_dump()`, etc.
            receiver = node.func.value
            looks_like_client_call = isinstance(receiver, ast.Call) and isinstance(
                receiver.func, ast.Attribute
            )
            if looks_like_client_call and method_name in {
                "list",
                "aggregated_list",
                "get",
                "search_projects",
                "get_xpn_host",
                "get_xpn_resources",
                "list_xpn_hosts",
                "get_health",
                "insert",
                "delete",
                "patch",
                "update",
            }:
                violations.append(
                    f"{path.name}: direct .{method_name}() call bypassing call_readonly"
                )
    assert not violations, violations
