# Architecture

## Layered design

```
AI / MCP Client
       |
       v
AWS CloudOps MCP
       |
       +--- MCP Tool Layer
       |
       +--- Security Guardrails
       |
       +--- AWS Service Layer
       |
       +--- AWS Client Factory
       |
       +--- Authentication
       |
       v
AWS APIs
```

Each layer has one job and depends only on the layer(s) beneath it:

| Layer | Package | Responsibility |
|---|---|---|
| MCP Tool Layer | `aws_cloudops_mcp.tools` | Defines MCP tool schemas (name, inputs, description); translates a tool call into a service-layer call; never touches boto3 directly |
| Security Guardrails | `aws_cloudops_mcp.security` | Rejects any AWS operation that isn't recognizably read-only, regardless of which tool tried to call it |
| AWS Service Layer | `aws_cloudops_mcp.aws` (`accounts.py`, `regions.py`, `networking.py`) | Calls specific AWS APIs, applies pagination, normalizes responses into `aws_cloudops_mcp.models` |
| AWS Client Factory | `aws_cloudops_mcp.aws.client_factory` | The **only** place a boto3 client is constructed; owns region selection, retry/timeout config |
| Authentication | `aws_cloudops_mcp.auth` (`credentials.py`, `session.py`) | Resolves boto3 credentials/sessions, including STS AssumeRole and session caching |

The MCP transport (`aws_cloudops_mcp.server`) only wires these layers
together and starts the stdio transport — it contains no AWS logic.

### Why this separation matters

Milestone 1 ships 5 tools. Later milestones are expected to add dozens more
(Transit Gateway, Direct Connect, VPN, Route 53, CloudWatch, CloudTrail,
Reachability Analyzer, topology generation, ...). Without a layered design,
AWS SDK calls end up duplicated across every tool function, and each new
tool becomes an opportunity to accidentally bypass the guardrails, retry
configuration, or logging conventions established here. By construction:

- A new tool can only reach AWS through the service layer, which can only
  reach AWS through the client factory, which enforces consistent
  region/timeout/retry handling.
- Every AWS API call — paginated or not — is funneled through
  `security.guardrails`, so a new tool cannot introduce a mutating call
  without an explicit, auditable change to the guardrail allowlist logic.
- The tool layer is a thin adapter. It can be tested, replaced, or extended
  (e.g. to support a different transport) without touching AWS logic.

## Request flow (example: `aws_list_vpcs`)

```
MCP Client
     |
     v
aws_list_vpcs(region="us-east-1")          [tools/inventory.py]
     |
     v
execute_tool(...)                          [tools/_shared.py]
     |  - generates a correlation/request ID
     |  - resolves account_id (cached)
     v
networking.list_vpcs(client_factory, ...)  [aws/networking.py]
     |  - validates region format
     |  - paginates ec2:DescribeVpcs
     |  - normalizes tags, builds Vpc models
     v
client_factory.get_client("ec2", region=...)  [aws/client_factory.py]
     |  - resolves session (base or assumed role)
     |  - applies retry/timeout config
     v
boto3 / botocore -> AWS EC2 API
     |
     v
Normalized ToolResponse envelope returned to the MCP Client
```

## Multi-account and multi-region readiness

Milestone 1 intentionally supports only a single configured identity
(base credentials, optionally with one `AWS_ROLE_ARN`) and requires callers
to pass an explicit `region` per tool call. The architecture is already
shaped for more:

- **Multi-account:** `ClientFactory.get_client()` and `get_account_id()`
  already accept a per-call `role_arn` parameter (defaulting to the
  server-wide `AWS_ROLE_ARN`). `SessionManager` caches assumed-role sessions
  **per role ARN**, so a future `aws_list_accounts`/cross-account tool can
  pass a different `role_arn` per call — e.g. iterating over a set of
  member-account roles discovered from AWS Organizations — without any
  change to the caching or authentication layers. `tools/accounts.py` is
  reserved for that future tool.
- **Multi-region:** every AWS service-layer function takes an explicit
  `region` argument and the client factory builds a fresh, correctly-scoped
  client per call; there is no global/default client to accidentally reuse
  across regions. A future "query all regions" tool can simply call the
  same service-layer functions in a loop (or concurrently) with different
  region arguments.

```
Management Account
       |
       +---- AssumeRole ---- Account A  (ClientFactory.get_client(..., role_arn=A))
       |
       +---- AssumeRole ---- Account B  (ClientFactory.get_client(..., role_arn=B))
       |
       +---- AssumeRole ---- Account C  (ClientFactory.get_client(..., role_arn=C))
```

AWS Organizations-based account discovery is explicitly out of scope for
Milestone 1.

## Deviations from the suggested repository structure

The originally suggested `src/aws_cloudops_mcp/aws/` package listed only
`client_factory.py`, `accounts.py`, and `regions.py`. Two additional modules
were added, documented here per the "improve the structure if there's a
strong engineering reason" allowance:

- **`aws/networking.py`** — VPC/Subnet/RouteTable service-layer logic
  (`aws_list_vpcs`, `aws_list_subnets`, `aws_list_route_tables`). These three
  tools share normalization helpers (tags, route targets) and are naturally
  read/tested together; splitting them into three files would fragment that
  shared logic for no benefit at this scale.
- **`aws/pagination.py`** and **`aws/readonly.py`** — the reusable
  pagination helper and the single call-site (`call_readonly`) that funnels
  every AWS API call through the read-only guardrail check. Both are used
  by every service-layer module and are AWS-client-specific (they operate
  on a boto3 client object), so they belong in `aws/` rather than
  `security/` (which stays framework-agnostic) or duplicated per module.
- **`aws/tags.py`** — the tag normalizer. Placed under `aws/` rather than
  `models/` because it is a transformation of AWS's wire format, not a data
  model; `models/common.py` imports and uses it.
- **`tools/_shared.py`** — the shared `execute_tool()` wrapper that gives
  every tool consistent logging, correlation IDs, and error-envelope
  construction. Without it, this logic would be copy-pasted into (and drift
  across) every tool module as the tool count grows in later milestones.

No other changes were made to the suggested structure.

## Multi-cloud compatibility

This repository contains AWS-specific logic only. Its output models
(`aws_cloudops_mcp.models`) and response envelope
(`aws_cloudops_mcp.models.responses.ToolResponse`) are cloud-agnostic in
shape (`success`, `tool`, `account_id`, `region`, `data`, `metadata`,
`error`) so that a future multi-cloud orchestration layer can consume AWS,
Azure, and GCP MCP server output consistently, without needing AWS-specific
parsing logic. No orchestration, federation, or cross-cloud logic lives in
this repository.
