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

# Explicitly allowlisted read-only "begin_" computations -- not mutations.
# Must stay in sync with security/guardrails.py::READ_ONLY_ACTIONS.
_ALLOWED_BEGIN_METHODS = {
    "begin_get_effective_route_table",
    "begin_list_effective_network_security_groups",
    "begin_get_bgp_peer_status",
    "begin_list_advertised_routes",
    "begin_list_learned_routes",
}

# Attribute names that carry secret material on the underlying Azure SDK
# models (VPN pre-shared keys, ExpressRoute authorization/service keys) --
# see models/hybrid_connectivity.py's module docstring. No arm/ module may
# ever read one of these off an SDK response object.
_SECRET_ATTRIBUTE_NAMES = {
    "shared_key",
    "site_key",
    "authorization_key",
    "service_key",
    "get_shared_key",
    "get_default_shared_key",
    "get_all_shared_keys",
    "list_default_shared_key",
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


def _attribute_and_getattr_accesses(path: Path) -> set[str]:
    """Names actually *accessed* as an attribute (``obj.x`` or
    ``getattr(obj, "x", ...)``) -- deliberately not a scan of every string
    literal in the file, since this module's own docstrings and this very
    test's messages name these fields in prose to explain why they're
    never read; a plain-text mention is not an access."""
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value.lower())
    return names


def test_no_arm_module_ever_reads_a_secret_shaped_field() -> None:
    """Redaction-by-omission guarantee: no arm/ module may access
    ``.shared_key``, ``.site_key``, ``.authorization_key``,
    ``.service_key``, or call one of the shared-key retrieval methods --
    the whole point of never reading these off an SDK response is that a
    field/method that is never touched cannot leak regardless of what the
    raw response contains. See models/hybrid_connectivity.py."""
    violations: list[str] = []
    for path in sorted(ARM_DIR.glob("*.py")):
        touched = _attribute_and_getattr_accesses(path) & _SECRET_ATTRIBUTE_NAMES
        for name in sorted(touched):
            violations.append(f"{path.name}: {name!r}")
    assert violations == [], f"Secret-shaped field/method referenced in arm/: {violations}"
