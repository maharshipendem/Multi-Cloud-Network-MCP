"""Read-only security guardrails.

Milestone 1 of aws-cloudops-mcp is READ-ONLY. This module is the single
choke point through which every AWS API call must pass. Its job is to make
it structurally hard for a future tool to "accidentally" call a mutating
AWS operation -- not to be the sole line of defense.

IMPORTANT: this is a defense-in-depth control, not the authoritative
security boundary. The authoritative boundary is IAM: the credentials this
server runs with should belong to a role/user that only has
``Describe*``/``Get*``/``List*`` permissions (see docs/security.md and the
example IAM policy in docs/tools.md). Even if this module were bypassed or
had a bug, a correctly scoped IAM policy still prevents any mutation.
"""

from __future__ import annotations

from aws_cloudops_mcp.exceptions import GuardrailViolationError

# botocore/boto3 client methods are snake_case (e.g. "describe_vpcs",
# "get_caller_identity", "list_subnets"). These are the only prefixes a
# tool is allowed to invoke through the AWS service layer.
READ_ONLY_PREFIXES: tuple[str, ...] = ("describe_", "get_", "list_")

# Explicit example of operations Milestone 1 tools are known to use. This is
# not exhaustive -- new read-only operations are permitted automatically as
# long as they match READ_ONLY_PREFIXES and no BLOCKED_KEYWORDS. It exists
# for documentation and unit-test clarity.
READ_ONLY_ACTIONS: frozenset[str] = frozenset(
    {
        "get_caller_identity",
        "describe_regions",
        "describe_vpcs",
        "describe_subnets",
        "describe_route_tables",
    }
)

# Keywords that indicate a mutating or state-changing AWS operation. Matched
# as a whole "word" segment of the snake_case operation name so that, e.g.,
# "describe_vpc_attribute" is not blocked by a substring match on "put"
# hiding inside an unrelated word.
BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {
        "create",
        "delete",
        "modify",
        "update",
        "attach",
        "detach",
        "associate",
        "disassociate",
        "start",
        "stop",
        "reboot",
        "terminate",
        "put",
        "authorize",
        "revoke",
        "run",
        "register",
        "deregister",
        "cancel",
        "reset",
        "enable",
        "disable",
        "replace",
        "reject",
        "accept",
        "allocate",
        "release",
        "import",
        "export",
        "copy",
        "restore",
        "apply",
        "set",
        "purchase",
        "monitor",
        "unmonitor",
        "move",
        "transfer",
        "assign",
        "unassign",
        "provision",
        "deprovision",
        "send",
        "write",
        "add",
        "remove",
    }
)

# Example explicit denylist of full operation names known to be destructive.
# Kept for documentation/testing; BLOCKED_KEYWORDS already rejects these.
BLOCKED_ACTIONS: frozenset[str] = frozenset(
    {
        "create_vpc",
        "delete_vpc",
        "modify_vpc_attribute",
        "create_subnet",
        "delete_subnet",
        "create_route",
        "delete_route",
        "replace_route",
        "attach_internet_gateway",
        "detach_internet_gateway",
        "terminate_instances",
        "stop_instances",
        "authorize_security_group_ingress",
        "revoke_security_group_ingress",
    }
)


def assert_read_only_operation(operation_name: str) -> None:
    """Raise ``GuardrailViolationError`` unless ``operation_name`` is read-only.

    ``operation_name`` is the snake_case boto3 client method name (e.g.
    ``"describe_vpcs"``), not the AWS API action name.
    """
    op = operation_name.lower().strip()
    words = set(op.split("_"))

    if words & BLOCKED_KEYWORDS:
        raise GuardrailViolationError(
            f"Operation '{operation_name}' is blocked by read-only guardrails: "
            "aws-cloudops-mcp (Milestone 1) only permits read-only AWS operations."
        )

    if not op.startswith(READ_ONLY_PREFIXES):
        raise GuardrailViolationError(
            f"Operation '{operation_name}' is not recognized as read-only "
            f"(must start with one of {READ_ONLY_PREFIXES}) and was rejected."
        )
