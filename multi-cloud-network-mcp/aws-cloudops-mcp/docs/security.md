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
`describe_`, `get_`, `list_`, `search_` (added in Milestone 3 for
`ec2:SearchTransitGatewayRoutes`), or `lookup_` (added in Milestone 4 for
`cloudtrail:LookupEvents`) — each addition beyond the original three is a
narrow, explicitly-reviewed exception for one genuinely read-only AWS
action that doesn't follow the describe/get/list naming convention, not a
loosening of the rule itself.

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

## Redaction and size limits

Milestone 2 adds two resource types whose raw AWS API responses can carry
large or sensitive-shaped content: security group rule descriptions (free
text, but attacker-influenceable if descriptions come from an untrusted
source) and VPC endpoint policy documents (IAM JSON, potentially large).

- **VPC endpoint policies** (`aws_list_vpc_endpoints`): omitted entirely
  unless the caller passes `include_policies: true`. Even then, any
  document over `MAX_POLICY_DOCUMENT_CHARS` (8000) is truncated, with
  `policy_document_truncated: true` on the record so a client can tell the
  document was cut rather than assume it's complete. This is a size guard
  against an oversized policy blowing up a tool response, not a claim that
  policy contents are secret — the account already has direct IAM/console
  visibility into any policy it owns.
- **Managed prefix list entries** and **target health** are similarly
  opt-in (`include_entries`/`include_target_health`) and bounded by
  `Settings.max_fanout_calls`, since each requires one AWS API call per
  item with no batch equivalent — see
  [docs/architecture.md](architecture.md#bounded-fan-out).
- Nothing in Milestone 2 retrieves credentials, pre-shared keys,
  passwords, or private key material — no AWS API surfaced by this
  milestone's tools returns any (VPN tunnel pre-shared keys, if a future
  hybrid-connectivity milestone adds VPN visibility, will need the same
  redaction treatment before being surfaced).

Milestone 3 adds exactly the hybrid-connectivity visibility anticipated
above, and with it two fields that must never reach an MCP client:

- **VPN pre-shared keys** (`aws_list_vpn_connections`): AWS's
  `ec2:DescribeVpnConnections` response embeds the tunnels' pre-shared
  keys inside the `CustomerGatewayConfiguration` XML field. `aws/vpn.py`
  never reads that field at all — not a regex scrub, not a
  post-processing strip, but simply never parsed out of the raw response
  in the first place. This is **redaction by omission**, chosen
  deliberately over redaction by scrubbing: a scrub can miss an encoding
  variant or a future AWS response-format change; a field that is never
  read cannot leak regardless of what the raw response contains. Every
  `VpnConnection` record is stamped `redacted: true` so a client can tell
  the record is intentionally incomplete rather than assume it saw
  everything. `tests/unit/test_vpn.py::test_vpn_connection_never_leaks_pre_shared_key`
  creates a real VPN connection via moto (which generates and embeds a
  real PSK in its response, exactly like AWS), then asserts the literal
  secret string does not appear anywhere in the serialized model output.
- **Direct Connect BGP authentication keys**
  (`aws_list_direct_connect_virtual_interfaces`): the same omission
  pattern applies to `directconnect:DescribeVirtualInterfaces`'s
  `authKey` field (present both at the top level and per BGP peer) and
  `customerRouterConfig` (which embeds the same key inside generated
  router-config text). Neither is ever read from the raw response. Every
  `VirtualInterface` record is stamped `redacted: true`, the same
  convention `VpnConnection` uses.
  `tests/unit/test_directconnect.py::test_direct_connect_virtual_interface_never_leaks_auth_key`
  stubs a response containing both secrets (moto does not implement this
  operation) and asserts neither appears in serialized output.
- **VPC Flow Logs** (`aws_list_flow_logs`): returns configuration and
  delivery metadata only — log group/destination ARN, traffic type,
  aggregation interval, format, status. There is no field anywhere in
  `FlowLogConfig` that could hold a log record, and no code path in
  `aws/flowlogs.py` calls a CloudWatch Logs or S3 read API to fetch one;
  this is a scope boundary (the milestone explicitly excludes log
  contents), not a filtered field.
  `tests/unit/test_flowlogs.py::test_list_flow_logs_never_exposes_log_contents`
  asserts this at the schema level — no field name containing "content"
  or "record" — rather than only checking one fixture's data, since a
  future field addition could otherwise silently reintroduce the gap.
- **Route 53 Resolver query logs** (`aws_list_resolver_query_log_configs`):
  same principle as flow logs — returns the log configuration
  (destination ARN, association count, status) only, never queried DNS
  record contents. Route 53 Resolver has no API that would even return
  per-query records to this tool; the boundary here is "never add a tool
  that would."
- **DNS Firewall** (`aws_list_dns_firewall_rule_groups`,
  `aws_list_dns_firewall_rule_group_associations`): a separately
  permissioned capability within the Resolver API — the milestone asks
  for it "where allowed." A denied call degrades to an empty list plus an
  `ACCESS_DENIED` `CollectionWarning` rather than failing the tool call
  outright, the same best-effort pattern Milestone 2 established for
  optional per-item enrichments.
- **CloudTrail lookup** (used internally by `aws_get_network_health`'s
  `include_recent_changes`): never returns the raw `CloudTrailEvent` JSON
  blob CloudTrail includes per event (full request parameters, which can
  be more detail than a bounded recent-activity check should surface) —
  only summary fields (event ID/name/time/username/resource names).
  Bounded to `MAX_LOOKBACK_DAYS` (7) regardless of what a caller requests
  and `MAX_RESULTS_CAP` (50), since this is a bounded recent-activity
  check, not a general-purpose audit log query.
- **CloudWatch metrics** (used internally by `aws_get_network_health`'s
  `include_metrics`): queries only a small, fixed catalog of known
  network-relevant metrics per resource type
  (`aws/network_metrics.py::KNOWN_NETWORK_METRICS`), not open-ended
  metric discovery, and each query is bounded to `MAX_LOOKBACK_HOURS`
  (24) and `MAX_DATAPOINTS` (288).
- **Reachability Analyzer / Network Access Analyzer findings**
  (`aws_get_network_insights_access_scope_analysis_findings`): a
  finding's `finding_components` are a bounded summary (component
  ID/ARN), not AWS's full per-component explanation payload, and findings
  retrieval is capped by `max_results`. Nothing in this milestone creates
  a path, analysis, scope, or scope analysis — `ec2:CreateNetworkInsightsPath`,
  `StartNetworkInsightsAnalysis`, `CreateNetworkInsightsAccessScope`, and
  `StartNetworkInsightsAccessScopeAnalysis` are all mutating operations,
  explicitly out of scope; only the corresponding `Describe*`/`Get*` reads
  of results an operator already produced are exposed.
- **Cloud WAN core network policies** (`aws_list_core_networks` with
  `include_policy: true`): reuses Milestone 2's VPC-endpoint-policy size
  guard (`MAX_POLICY_DOCUMENT_CHARS`, `policy_document_truncated`) — a
  size limit, not a secrecy claim, since the account already has direct
  visibility into policies it owns via the Cloud WAN console/API. When
  the account/SDK doesn't support `GetCoreNetworkPolicy` at all, the
  affected core network's `collection_completeness` is set to
  `"partial"` with an explicit `UNSUPPORTED_CAPABILITY` warning instead
  of silently returning an empty policy that could be mistaken for "this
  core network has no policy."

## No reachability claims

`aws_get_hybrid_topology` (and `aws_get_vpc_topology` before it) returns a
**configuration and attachment graph**, never a reachability analysis.
Every edge carries `evidence` — a specific AWS API field observation
(a route table entry, an attachment's resource ID, a hosted zone's linked
VPC) — and nothing in this codebase evaluates route table contents,
security group rules, NACLs, or VPN/DX tunnel state to determine whether
traffic can actually flow between two nodes. A VPC attachment on a
Transit Gateway proves the attachment exists; it does not prove packets
can cross it — that also depends on route table propagation, security
group and NACL rules, and (for VPN/DX) tunnel/BGP state, none of which
this tool inspects together to produce a reachability verdict. A client
consuming this graph must not present it as "X can reach Y" without
independently verifying the routing, security, and tunnel state that
would actually determine that. This mirrors AWS's own
[Reachability Analyzer](https://docs.aws.amazon.com/vpc/latest/reachability/)
positioning: reachability analysis is a distinct capability from topology
visibility, and this server does not claim to provide it.

**Milestone 4's `aws_explain_network_path` is the deliberate, narrower
exception to "topology alone."** It does not infer reachability from a
graph — it actually evaluates route resolution, security group rules, and
NACL rules together, and only claims `allowed`/`blocked` when it had
enough evidence to evaluate every applicable layer. When a layer can't
be evaluated (no source ENI resolvable for security groups; the path
leaves the analyzed VPC before reaching a known destination subnet for
NACLs), the result is `partially_evaluated`, with an explicit limitation
naming what was skipped — never silently upgraded to `allowed`. See
[Deterministic, evidence-bound diagnostics](#deterministic-evidence-bound-diagnostics)
below for the full guarantee this rests on.

## Deterministic, evidence-bound diagnostics

Milestone 4's diagnostic engine (`aws_cloudops_mcp.diagnostics`) carries
three guarantees beyond "read-only," each directly answering a guardrail
in the milestone's own spec:

- **Never claims certainty with incomplete data.** Every diagnostic
  conclusion is a `Finding` with an explicit `confidence` field, and
  `"indeterminate"` is a first-class value, not an error state or a
  silently-dropped result. A rule that cannot conclusively evaluate
  something it needs (a security group missing from the collected
  snapshot, a peered VPC outside its scope, a route target this engine
  doesn't resolve) says so via `confidence: "indeterminate"` plus
  `limitations` naming exactly what was missing. The alternative —
  omitting the finding — would look identical to "checked, found
  nothing," which is the one thing this guardrail exists to prevent.
- **The core result is always deterministic Python logic, never an LLM
  judgment call.** Every function under `diagnostics.*` is a pure
  function of its `NetworkSnapshot` input: longest-prefix-match route
  resolution, security group/NACL rule matching, CIDR overlap detection,
  and every other check is ordinary, golden-testable code with no model
  call anywhere in the decision path. An AI client consuming a `Finding`
  may summarize or explain it in natural language, but the `severity`,
  `confidence`, and `summary` it's explaining were decided before that
  client ever saw the data.
- **`remediation` is advisory text only, never executed.** No code path
  anywhere in this repository takes a `Finding.remediation` string and
  acts on it — there is no "apply this fix" tool, and Milestone 4 adds
  none. A client presenting a finding to a user must not describe a
  remediation suggestion as something that has been done.

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
| Invalid tool input (e.g. `aws_find_network_risks`'s `min_severity` not one of the valid values) | `TOOL_EXECUTION_ERROR` |
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
