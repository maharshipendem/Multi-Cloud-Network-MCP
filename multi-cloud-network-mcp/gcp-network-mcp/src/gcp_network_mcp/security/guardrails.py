"""Read-only security guardrails.

This module is the single choke point through which every GCP client
library call must pass -- not just ``compute_v1``, but every provider
library this server uses (``networkconnectivity_v1``, ``network_management_v1``,
``google.cloud.dns``, ``logging_v2``, ``monitoring_v3``). Its job is to
make it structurally hard for a future tool to "accidentally" call a
mutating GCP operation -- not to be the sole line of defense.

IMPORTANT: this is a defense-in-depth control, not the authoritative
security boundary. The authoritative boundary is IAM: the identity this
server runs as should hold only a read-only role (a custom role scoped
to exactly the `*.get`/`*.list` permissions this milestone's tools need
-- see docs/security.md and gcp-custom-role.yaml). Even if this module
were bypassed or had a bug, a correctly scoped IAM role still prevents
any mutation at the GCP API layer itself.

Every Google Cloud client library generated from Google's API definitions
follows the same clean, consistent read-operation convention: a read is
always named ``get``, ``list``, ``aggregated_list``, or ``search``; a
handful of genuinely read-only *computed views* additionally use
``query_*`` (e.g. ``query_hub_status``) or ``show_*`` (e.g.
``show_effective_flow_logs_configs``) -- verified by enumerating every
method on every client class across ``compute_v1``,
``networkconnectivity_v1``, ``network_management_v1``, ``monitoring_v3``,
and ``logging_v2``'s ``LoggingServiceV2Client``: every method matching
this prefix set is a real, non-mutating read, and no mutating method
anywhere in that surface happens to start with one of these prefixes.
Mutating operations use ``insert``, ``delete``, ``patch``, ``update``, or
a verb-prefixed action (``set_*``, ``add_*``, ``remove_*``, ``enable_*``,
``disable_*``, ``request_*``, ``cancel_*``, ``resize_*``, ``start_*``,
``stop_*``, ``reset_*``, ``attach_*``, ``detach_*``, ``move_*``,
``expand_*``, ``suspend_*``, ``resume_*``, ``simulate_*``, ``switch_*``,
``bulk_insert``, ``accept_*``, ``reject_*``, ``rerun_*``, ``write_*``,
and more -- see ``BLOCKED_KEYWORDS``).
"""

from __future__ import annotations

from gcp_network_mcp.exceptions import GuardrailViolationError

# The only prefixes a tool is allowed to invoke through any GCP client
# library used in this codebase. "aggregated_list" is its own entry
# because it doesn't literally start with "list" (it starts with
# "aggregated"). "query"/"show" cover exactly three genuinely read-only
# computed-view methods this server calls (query_hub_status,
# query_org_vpc_flow_logs_configs, show_effective_flow_logs_configs) --
# verified by enumerating every "query_*"/"show_*" method across every
# client class this server touches; none of them mutate anything.
READ_ONLY_PREFIXES: tuple[str, ...] = (
    "get",
    "list",
    "aggregated_list",
    "search",
    "query",
    "show",
)

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
        # Added for Milestone 8's new provider libraries (Network
        # Connectivity Center, Network Management, Cloud Logging):
        "accept",
        "reject",
        "rerun",
        "write",
        "abandon",
        "announce",
        "apply",
        "clone",
        "copy",
        "deprecate",
        "invalidate",
        "pause",
        "perform",
        "preview",
        "recreate",
        "send",
        "validate",
        "withdraw",
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
        # Network Connectivity Center
        "create_hub",
        "create_spoke",
        "delete_hub",
        "delete_spoke",
        "update_hub",
        "update_spoke",
        "update_group",
        "accept_hub_spoke",
        "accept_spoke_update",
        "reject_hub_spoke",
        "reject_spoke_update",
        # Network Management
        "create_connectivity_test",
        "update_connectivity_test",
        "delete_connectivity_test",
        "rerun_connectivity_test",
        "create_vpc_flow_logs_config",
        "update_vpc_flow_logs_config",
        "delete_vpc_flow_logs_config",
        # Cloud Logging
        "write_log_entries",
        "delete_log",
        "tail_log_entries",
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
