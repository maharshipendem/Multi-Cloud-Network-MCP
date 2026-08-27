# Security Model

## Read-only-first philosophy

Milestone 1 of aws-cloudops-mcp is **read-only by design**. No tool, code
path, or configuration in this milestone can cause an AWS mutation. This is
enforced at multiple independent layers so that a bug or bypass in any one
layer does not, by itself, allow a mutation:

```
AI Client
    |
    v
MCP Tool Allowlist       -- only 5 tools exist; none accept "create/delete/..." semantics
    |
    v
Application Guardrails   -- aws_cloudops_mcp.security.guardrails rejects any
    |                        non-Describe*/Get*/List* boto3 operation before
    |                        it reaches botocore
    v
IAM Read-Only Role       -- the authoritative boundary (see below)
    |
    v
AWS API
```

If a client attempts to request something like "delete this VPC", "create a
subnet", "attach a Transit Gateway", or "modify a route" via the MCP
connection, there is **no tool for that** — the MCP tool allowlist itself is
the first rejection. Even if a future milestone accidentally added such a
tool, `aws.readonly.call_readonly()` and `aws.pagination.paginate()` funnel
every single boto3 call through
`security.guardrails.assert_read_only_operation()`, which rejects any
operation name containing a mutating keyword (`create`, `delete`, `modify`,
`update`, `attach`, `detach`, `associate`, `disassociate`, `start`, `stop`,
`reboot`, `terminate`, `put`, `authorize`, `revoke`, and others — see
`READ_ONLY_PREFIXES` / `BLOCKED_KEYWORDS` in
`src/aws_cloudops_mcp/security/guardrails.py`) or that doesn't start with
`describe_`, `get_`, or `list_`.

**This is a defense-in-depth control, not the authoritative security
boundary.** Keyword/prefix matching on an operation name is a useful
tripwire, not a proof of safety — it does not (and cannot) reason about what
an operation *does*. The authoritative boundary is IAM.

## IAM least privilege

The AWS identity aws-cloudops-mcp runs as should be a dedicated,
purpose-built role — e.g. `AWSCloudOpsMCPReadOnlyRole` — scoped to exactly
the actions Milestone 1's tools need:

- `sts:GetCallerIdentity`
- `ec2:DescribeRegions`
- `ec2:DescribeVpcs`
- `ec2:DescribeSubnets`
- `ec2:DescribeRouteTables`

See the full example policy in [docs/tools.md](tools.md#example-iam-policy).
**Never** attach `AdministratorAccess`, `PowerUserAccess`, or a broad
`ec2:*`/`*:*` policy to this role. Even with a bug in this codebase, an IAM
policy scoped to `Describe*`/`Get*` actions makes a mutation impossible at
the AWS API layer itself — this is the control that actually matters in
production.

Production deployments should also consider:

- A permissions boundary on the role, in addition to the attached policy.
- `aws:SourceIdentity` / session tags on `sts:AssumeRole` calls for
  auditability.
- Restricting which principals can assume `AWSCloudOpsMCPReadOnlyRole` via
  its trust policy.

## Credential handling

- Credentials are **never** hard-coded, accepted as tool input, or stored by
  this application. They are resolved exclusively through boto3's standard
  credential chain (environment variables, `~/.aws/credentials`,
  `~/.aws/config` including SSO profiles, or an IAM role attached to the
  compute environment).
- Access keys, secret keys, and session tokens are **never logged**, at any
  log level, including in exception messages surfaced back to the MCP
  client (see [Logging](#logging) below).
- Nothing in `.env.example` (or any file in this repository) contains real
  credentials, account IDs, or ARNs.
- Assumed-role credentials are cached in memory only, refreshed
  proactively ~60 seconds before expiry, and never written to disk. See
  `auth/session.py`.

## AssumeRole

If `AWS_ROLE_ARN` is configured, the server calls `sts:AssumeRole` using the
base credentials to obtain temporary credentials for the target role,
optionally passing `AWS_EXTERNAL_ID` (required by many cross-account trust
policies to mitigate the "confused deputy" problem) and a fixed
`AWS_SESSION_NAME` for auditability in CloudTrail.

`sts:AssumeRole` is treated as an **authentication** operation, not a
resource-mutating one, and is therefore *not* routed through
`security.guardrails` — those guardrails govern which AWS *resource* APIs
(EC2, etc.) a tool may call once a session exists, not how that session is
obtained. The role being assumed should itself carry only the read-only
permissions described above; AssumeRole does not grant any permission by
itself.

## Logging

Every tool invocation produces exactly one structured JSON log line (see
`logging/setup.py`) containing: `timestamp`, `request_id`, `tool_name`,
`account_id`, `region`, `duration_ms`, and `status`. Logs are written to
**stderr** (stdout is reserved for the MCP stdio protocol) and are safe to
ship as-is to CloudWatch Logs, Splunk, Datadog, or an ELK stack.

What is explicitly **never** logged:

- Credentials of any kind (access keys, secret keys, session tokens).
- Full AWS API request/response payloads — only normalized, already-public
  identifiers (VPC IDs, region names, counts) appear in log fields.
- Raw internal stack traces in the MCP response sent back to a client (see
  [Error handling](#error-handling)). Full tracebacks are logged
  server-side only, via `logger.exception(...)`, for operator debugging.

## Secrets

This repository ships no secrets. `.env.example` documents variable names
only, with empty values. `.gitignore` excludes `.env` and any local
credential files. CI/deployment pipelines should inject credentials via
their platform's secret manager (or, preferably, IAM roles / OIDC federation
requiring no static secret at all) rather than environment files.

## Error handling

AWS/botocore errors are translated into a stable, client-safe error type
before being returned over MCP (see `tools/_shared.py`):

| Condition | `error.type` |
|---|---|
| Missing/invalid/expired credentials | `AUTHENTICATION_ERROR` |
| IAM denies the call (`AccessDenied`, `UnauthorizedOperation`, ...) | `AUTHORIZATION_ERROR` |
| Guardrail rejected the operation before it reached AWS | `GUARDRAIL_VIOLATION` |
| Malformed / unreachable region | `INVALID_REGION` |
| Any other AWS API error | `AWS_SERVICE_ERROR` |
| Unexpected internal error | `INTERNAL_ERROR` |

The client-facing `message` is a short, generic description — never a raw
`botocore.exceptions.ClientError` string, stack trace, or internal file
path. Full exception details (including type and message from AWS) are
logged server-side for operator troubleshooting.

## Threat boundaries

In scope for aws-cloudops-mcp's own controls:

- Preventing the *server itself* from issuing a mutating AWS API call.
- Preventing credential material from leaking via logs or MCP responses.
- Bounding response size (pagination safety limits) to avoid resource
  exhaustion from a single tool call.

Explicitly **out of scope** for this application layer (owned by IAM /
infrastructure instead):

- Enforcing which AWS resources a given identity can *read*. If the
  configured role has `ec2:DescribeVpcs` on all VPCs, this server will
  return all VPCs it is asked about — resource-level read scoping is an IAM
  policy concern, not something this codebase second-guesses.
- Network-layer access control to AWS APIs (VPC endpoints, IP allowlisting)
  — a deployment concern, documented but not implemented here.
- Protecting the machine/container the server runs on.

## Future approval gates

Milestone 1 has no mutating capability, so there is no approval flow to
design yet. When a future milestone introduces any AWS API call that isn't
`Describe*`/`Get*`/`List*` (there are none planned in the near-term
roadmap, which stays read-only through network troubleshooting and
topology/path analysis), it must not simply be added to
`READ_ONLY_PREFIXES`. Instead it will require:

1. A dedicated, explicitly-named tool (never a generic "run any AWS API"
   tool).
2. An explicit, human-in-the-loop confirmation step before execution.
3. Its own least-privilege IAM action added to a *separate* role — never
   folded into `AWSCloudOpsMCPReadOnlyRole`.
4. A dry-run/preview mode where the AWS API supports one.

This is a design commitment for future milestones, not something
implemented in Milestone 1.
