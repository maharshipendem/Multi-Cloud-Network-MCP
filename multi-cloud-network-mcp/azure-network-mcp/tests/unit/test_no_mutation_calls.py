"""Static regression guard: no ARM service-layer module may spell out a
mutating Azure SDK method name as a string literal call target.

This complements ``test_guardrails.py`` (which tests the guardrail
function's logic in isolation): this test scans the actual source of every
``arm/*.py`` module for a hardcoded mutating method name, so a future
service-layer function that bypasses ``call_readonly``/``paginate``
entirely (and therefore never reaches the guardrail check at runtime)
still gets caught in CI rather than only in a live Azure account.
"""

from __future__ import annotations

import ast
from pathlib import Path

ARM_DIR = Path(__file__).parent.parent.parent / "src" / "azure_network_mcp" / "arm"

_MUTATING_KEYWORDS = (
    "create",
    "delete",
    "update_tags",
    "put",
    "patch",
    "swap",
    "reserve",
    "migrate",
    "restart",
    "reset",
    "generate",
    "rotate",
    "purge",
    "failover",
)

# The two explicitly allowlisted read-only "begin_" computations -- not mutations.
_ALLOWED_BEGIN_METHODS = {
    "begin_get_effective_route_table",
    "begin_list_effective_network_security_groups",
}


def _string_literals_in_module(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_no_arm_module_references_a_mutating_method_name_literal() -> None:
    violations: list[str] = []
    for path in sorted(ARM_DIR.glob("*.py")):
        for literal in _string_literals_in_module(path):
            name = literal.lower()
            if name.startswith("begin_") and name not in _ALLOWED_BEGIN_METHODS:
                violations.append(f"{path.name}: {literal!r}")
                continue
            if any(keyword in name.split("_") for keyword in _MUTATING_KEYWORDS):
                violations.append(f"{path.name}: {literal!r}")
    assert violations == [], f"Mutating method names referenced in arm/: {violations}"


def test_no_tools_module_references_a_mutating_method_name_literal() -> None:
    tools_dir = ARM_DIR.parent / "tools"
    violations: list[str] = []
    for path in sorted(tools_dir.glob("*.py")):
        for literal in _string_literals_in_module(path):
            name = literal.lower()
            if name.startswith("begin_") and name not in _ALLOWED_BEGIN_METHODS:
                violations.append(f"{path.name}: {literal!r}")
    assert violations == [], f"Mutating method names referenced in tools/: {violations}"
