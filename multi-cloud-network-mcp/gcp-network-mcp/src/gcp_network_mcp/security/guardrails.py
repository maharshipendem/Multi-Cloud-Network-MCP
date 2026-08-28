"""Read-only security guardrails.

This module is the single choke point through which every GCP client
library call must pass. Its job is to make it structurally hard for a
future tool to "accidentally" call a mutating GCP operation -- not to be
the sole line of defense.

IMPORTANT: this is a defense-in-depth control, not the authoritative
security boundary. The authoritative boundary is IAM: the identity this
server runs as should hold only a read-only role (a custom role scoped
to exactly the `*.get`/`*.list` permissions this milestone's tools need
-- see docs/security.md and gcp-custom-role.yaml). Even if this module
were bypassed or had a bug, a correctly scoped IAM role still prevents
any mutation at the GCP API layer itself.

Unlike Azure's SDK (where a long-running mutation and a long-running
*read* computation can share the same ``begin_`` prefix, requiring
explicit per-method exceptions), the Google Cloud client libraries
generated from Google's API definitions follow a clean, consistent
convention: every read operation is named ``get``, ``list``, or
``aggregated_list``; every mutating operation is named ``insert``,
``delete``, ``patch``, ``update``, or a verb-prefixed action
(``set_*``, ``add_*``, ``remove_*``, ``enable_*``, ``disable_*``,
``request_*``, ``cancel_*``, ``resize_*``, ``start_*``, ``stop_*``,
``reset_*``, ``attach_*``, ``detach_*``, ``move_*``, ``expand_*``,
``suspend_*``, ``resume_*``, ``simulate_*``, ``switch_*``,
``bulk_insert``). No method in the resource types this milestone's tools
call needs an exception to that rule -- every genuinely read-only
computed view this server uses (``get_health``, ``get_effective_firewalls``,
``list_peering_routes``, ``list_usable``, ``get_xpn_host``,
``get_xpn_resources``, ``list_xpn_hosts``, ``list_associations``,
``get_nat_ip_info``, ``get_nat_mapping_info``, ``get_router_status``,
``list_bgp_routes``) already starts with ``get_``/``list_`` and needs no
special-casing.
"""

from __future__ import annotations

from gcp_network_mcp.exceptions import GuardrailViolationError

# The only prefixes a tool is allowed to invoke through the GCP service
# layer. "aggregated_list" is its own entry because it doesn't literally
# start with "list" (it starts with "aggregated").
READ_ONLY_PREFIXES: tuple[str, ...] = ("get", "list", "aggregated_list", "search")

# Keywords that indicate a mutating or state-changing GCP operation.
# Matched as a whole "word" segment of the snake_case method name so that
# a hypothetical "list_updated_resources" wouldn't be blocked by a
# substring match on "update" hiding inside an unrelated word.
BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {
        "insert",
        "delete",
        "patch",
        "update",
        "set",
        "add",
        "remove",
        "enable",
        "disable",
        "request",
        "cancel",
        "resize",
        "start",
        "stop",
        "reset",
        "attach",
        "detach",
        "move",
        "expand",
        "suspend",
        "resume",
        "simulate",
        "switch",
        "bulk",
    }
)

# Example explicit denylist of full method names known to be destructive.
# Kept for documentation/testing; BLOCKED_KEYWORDS already rejects these.
BLOCKED_ACTIONS: frozenset[str] = frozenset(
    {
        "insert",
        "delete",
        "patch",
        "update",
        "add_peering",
        "remove_peering",
        "update_peering",
        "enable_xpn_host",
        "enable_xpn_resource",
        "disable_xpn_host",
        "disable_xpn_resource",
        "set_target",
        "set_iam_policy",
        "set_labels",
        "set_tags",
        "set_metadata",
    }
)


def assert_read_only_operation(method_name: str) -> None:
    """Raise ``GuardrailViolationError`` unless ``method_name`` is read-only.

    ``method_name`` is the Python method name on a GCP client library
    service client (e.g. ``"list"``, ``"aggregated_list"``, ``"get"``),
    not a full GCP IAM permission name.
    """
    name = method_name.lower().strip()

    words = set(name.split("_"))
    if words & BLOCKED_KEYWORDS:
        raise GuardrailViolationError(
            f"Operation '{method_name}' is blocked by read-only guardrails: "
            "gcp-network-mcp only permits read-only GCP operations."
        )

    if not name.startswith(READ_ONLY_PREFIXES):
        raise GuardrailViolationError(
            f"Operation '{method_name}' is not recognized as read-only "
            f"(must start with one of {READ_ONLY_PREFIXES}) and was rejected."
        )
