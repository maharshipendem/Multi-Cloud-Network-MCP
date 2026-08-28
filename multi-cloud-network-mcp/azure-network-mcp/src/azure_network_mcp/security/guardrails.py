"""Read-only security guardrails.

This module is the single choke point through which every Azure ARM SDK
call must pass. Its job is to make it structurally hard for a future tool
to "accidentally" call a mutating Azure operation -- not to be the sole
line of defense.

IMPORTANT: this is a defense-in-depth control, not the authoritative
security boundary. The authoritative boundary is Azure RBAC: the identity
this server runs as should hold only a read-only role (``Reader``, or a
narrower custom role -- see docs/security.md and the example role JSON in
docs/tools.md). Even if this module were bypassed or had a bug, a
correctly scoped RBAC role assignment still prevents any mutation at the
Azure Resource Manager layer itself.

Azure SDK operation-group methods follow a different naming convention
than AWS's boto3 (which this server's AWS sibling guards): a read
operation is ``get(...)``/``list(...)``/``list_all(...)``; a mutating,
typically long-running operation is ``begin_create_or_update(...)``,
``begin_delete(...)``, or ``update_tags(...)``. ``begin_`` signals "long-
running operation," which is *usually* but not *always* a mutation --
Azure also uses it for a small number of genuinely read-only
computations that simply take longer than a normal request (e.g.
computing a NIC's effective route table by evaluating every route source
that applies to it). Those are treated exactly like this server's AWS
sibling treats ``ec2:SearchTransitGatewayRoutes``/``cloudtrail:LookupEvents``:
rejected by the general prefix rule by default, then explicitly
allowlisted, one at a time, with the reason recorded here.
"""

from __future__ import annotations

from azure_network_mcp.exceptions import GuardrailViolationError

# The only prefixes a tool is allowed to invoke through the ARM service
# layer without an explicit READ_ONLY_ACTIONS entry.
READ_ONLY_PREFIXES: tuple[str, ...] = ("get", "list")

# Explicit, narrow exceptions: genuinely read-only Azure operations that
# don't follow the get_/list_ convention because they're long-running
# computations (begin_*), not mutations. Each entry needed real
# justification before being added -- this is the guardrail correctly
# rejecting an unrecognized method by default until reviewed, not a
# loosening of the rule.
#
# - begin_get_effective_route_table (NetworkInterfacesOperations): computes
#   the effective route table Azure actually applies to a NIC by merging
#   system routes, UDRs, and BGP-propagated routes -- explicitly requested
#   by this milestone ("effective route tables when supported for a
#   specified NIC"). Read-only: it evaluates existing configuration and
#   returns a result, changing nothing.
# - begin_list_effective_network_security_groups (NetworkInterfacesOperations):
#   the NSG analog of the above -- computes which NSG rules actually apply
#   to a NIC across subnet- and NIC-level associations. Read-only for the
#   same reason.
# - begin_get_bgp_peer_status (VirtualNetworkGatewaysOperations, Milestone 6):
#   returns the current BGP session state for a classic (non-vWAN) VPN/
#   ExpressRoute gateway's configured peers -- a live status read, not a
#   configuration change. Explicitly requested by Milestone 6's "BGP
#   settings and peer status" for Virtual Network Gateways.
# - begin_list_advertised_routes / begin_list_learned_routes
#   (VirtualHubBgpConnectionsOperations, Milestone 6): the vWAN-hub/Route
#   Server analog of the above -- the routes a hub BGP connection has
#   advertised to, or learned from, its peer. Explicitly requested by
#   Milestone 6's "Azure Route Server and BGP peers/routes."
READ_ONLY_ACTIONS: frozenset[str] = frozenset(
    {
        "begin_get_effective_route_table",
        "begin_list_effective_network_security_groups",
        "begin_get_bgp_peer_status",
        "begin_list_advertised_routes",
        "begin_list_learned_routes",
    }
)

# Keywords that indicate a mutating or state-changing Azure operation.
# Matched as a whole "word" segment of the snake_case method name so that,
# e.g., "list_updated_..." (hypothetical) wouldn't be blocked by a
# substring match on "update" hiding inside an unrelated word.
BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {
        "begin",  # long-running operation -- mutating by default, see module docstring
        "create",
        "update",
        "delete",
        "put",
        "patch",
        "move",
        "swap",
        "reserve",
        "prepare",
        "unprepare",
        "migrate",
        "cancel",
        "restart",
        "reset",
        "generate",
        "rotate",
        "purge",
        "failover",
    }
)

# Example explicit denylist of full method names known to be destructive.
# Kept for documentation/testing; BLOCKED_KEYWORDS already rejects these.
BLOCKED_ACTIONS: frozenset[str] = frozenset(
    {
        "begin_create_or_update",
        "begin_delete",
        "update_tags",
        "begin_move_ip_configurations",
    }
)


def assert_read_only_operation(method_name: str) -> None:
    """Raise ``GuardrailViolationError`` unless ``method_name`` is read-only.

    ``method_name`` is the Python method name on an Azure SDK operation
    group (e.g. ``"list_all"``, ``"get"``), not a full Azure REST API
    action name.
    """
    name = method_name.lower().strip()

    if name in READ_ONLY_ACTIONS:
        return

    words = set(name.split("_"))
    if words & BLOCKED_KEYWORDS:
        raise GuardrailViolationError(
            f"Operation '{method_name}' is blocked by read-only guardrails: "
            "azure-network-mcp only permits read-only Azure operations."
        )

    if not name.startswith(READ_ONLY_PREFIXES):
        raise GuardrailViolationError(
            f"Operation '{method_name}' is not recognized as read-only "
            f"(must start with one of {READ_ONLY_PREFIXES}) and was rejected."
        )
