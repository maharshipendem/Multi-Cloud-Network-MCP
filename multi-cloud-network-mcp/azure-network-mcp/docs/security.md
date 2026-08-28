# Security Model

## Read-only-first philosophy

azure-network-mcp is **read-only by design**. No tool, code path, or
configuration in this repository can cause an Azure Resource Manager
mutation. This is enforced at multiple independent layers so that a bug
or bypass in any one layer does not, by itself, allow a mutation:

```
AI Client
    |
    v
MCP Tool Allowlist       -- only 67 tools exist; none accept
    |                        create/update/delete semantics
    v
Application Guardrails   -- azure_network_mcp.security.guardrails rejects
    |                        any operation whose method name isn't
    |                        recognizably read-only before it reaches the
    |                        Azure SDK
    v
Azure RBAC Role          -- the authoritative boundary (see below)
    |
    v
Azure Resource Manager API
```

If a client attempts to request something like "create this VNet",
"delete this NSG rule", "update this route table", or "attach a NAT
gateway" via the MCP connection, there is **no tool for that** — the MCP
tool allowlist itself is the first rejection. Even if a future change
accidentally added such a tool, `arm.readonly.call_readonly()` and
`arm.pagination.paginate()` funnel every single Azure SDK call through
`security.guardrails.assert_read_only_operation()`, which:

1. Allows five explicitly named exceptions —
   `begin_get_effective_route_table`,
   `begin_list_effective_network_security_groups`,
   `begin_get_bgp_peer_status`, `begin_list_advertised_routes`, and
   `begin_list_learned_routes` — genuinely read-only long-running
   *computations* that happen to use the SDK's `begin_` prefix (see
   below).
2. Rejects any other method name containing a mutating keyword (`begin`,
   `create`, `update`, `delete`, `put`, `patch`, `move`, `swap`,
   `reserve`, `migrate`, `restart`, `reset`, `generate`, `rotate`,
   `purge`, `failover`, and others — see `BLOCKED_KEYWORDS` in
   `src/azure_network_mcp/security/guardrails.py`).
3. Rejects any method name that doesn't start with `get` or `list`.

**This is a defense-in-depth control, not the authoritative security
boundary.** Keyword/prefix matching on a method name is a useful
tripwire, not a proof of safety — it does not (and cannot) reason about
what an operation *does*. The authoritative boundary is Azure RBAC.

### Why `begin_*` needs five narrow exceptions

Azure's SDK convention differs from AWS's boto3 (which this project's AWS
sibling, `aws-cloudops-mcp`, guards): a read operation is
`get(...)`/`list(...)`/`list_all(...)`; a mutating, typically
long-running operation is `begin_create_or_update(...)` or
`begin_delete(...)`. The `begin_` prefix signals "long-running
operation," which is *usually* but not *always* a mutation — Azure also
uses it for a small number of genuinely read-only computations that
simply take longer than a normal request:

- **`begin_get_effective_route_table`** (`NetworkInterfacesOperations`):
  computes the route table Azure actually applies to a network interface
  by merging system routes, user-defined routes, and BGP-propagated
  routes. Read-only — it evaluates existing configuration and returns a
  result, changing nothing.
- **`begin_list_effective_network_security_groups`**
  (`NetworkInterfacesOperations`): the NSG analog — computes which rules
  actually apply to a NIC across subnet- and NIC-level associations, with
  Application Security Group references expanded into concrete IP
  prefixes.
- **`begin_get_bgp_peer_status`** (`VirtualNetworkGatewaysOperations`,
  Milestone 6): returns the current BGP session state for a classic
  (non-vWAN) VPN/ExpressRoute gateway's configured peers — a live status
  read, not a configuration change.
- **`begin_list_advertised_routes`** / **`begin_list_learned_routes`**
  (`VirtualHubBgpConnectionsOperations`, Milestone 6): the vWAN-hub/Route
  Server analog of the above — the routes a hub BGP connection has
  advertised to, or learned from, its peer.

All five are rejected by the guardrail's general `begin_` rule by default,
then explicitly allowlisted — the same pattern this project's AWS sibling
uses for `ec2:SearchTransitGatewayRoutes`/`cloudtrail:LookupEvents`, each
a narrow, explicitly-reviewed exception for one genuinely read-only
action that doesn't follow the get/list naming convention, not a
loosening of the rule itself. See the full justification in
`security/guardrails.py`'s module docstring.

## Azure RBAC least privilege

The identity azure-network-mcp runs as should be assigned a dedicated,
purpose-built role — either the built-in **Reader** role (simple,
slightly broader: grants read access to every resource type in scope,
not just networking), or the narrower custom role shipped in
[`azure-custom-role.json`](../azure-custom-role.json), scoped to exactly
the actions this milestone's tools need. See the per-tool action list in
[docs/tools.md](tools.md#rbac-actions-by-tool).

**Never** assign `Owner`, `Contributor`, or any role with write access to
network resources to this identity. Even with a bug in this codebase, an
RBAC role scoped to `*/read` and the two effective-computation `/action`
permissions makes a mutation impossible at the Azure Resource Manager
layer itself — this is the control that actually matters in production.

Production deployments should also consider:

- Assigning the role at the narrowest scope that covers what this server
  needs to read (a specific subscription or resource group, not the
  tenant root management group), even when using the custom role.
- Azure AD Conditional Access policies on the identity used, if it's a
  user-delegated credential rather than a managed identity or service
  principal.
- Reviewing role assignments periodically via Azure AD Privileged
  Identity Management (PIM) or a scheduled access review.

## Credential handling

- Credentials are **never** hard-coded, accepted as tool input, or stored
  by this application. They are resolved exclusively through
  `azure.identity.DefaultAzureCredential`'s standard resolution chain
  (environment variables for a service principal, workload identity
  federation, a managed identity, or an interactively-authenticated
  Azure CLI/PowerShell/Developer CLI session).
- `AZURE_TENANT_ID` and `AZURE_CLIENT_ID` (in `config.py`) are **non-secret
  identifiers** used only to narrow which identity/tenant
  `DefaultAzureCredential` resolves against. The actual secret material
  for a service principal (`AZURE_CLIENT_SECRET`, or
  `AZURE_CLIENT_CERTIFICATE_PATH` for certificate auth) is read by the
  Azure Identity SDK itself, directly from its own standard environment
  variables — this codebase never reads, stores, or logs either.
- `auth/credentials.py` never calls `credential.get_token()` directly and
  never surfaces a token, secret, or other credential material — see
  `tests/unit/test_credentials.py::test_credential_never_exposes_a_get_token_call_in_this_codebase`,
  a regression guard on that specific claim.
- `azure_get_caller_identity` reports the credential type and tenant/
  subscription context in use, and explicitly nothing else — see
  `models/identity.py::CallerIdentity`.
- Nothing in `.env.example` (or any file in this repository) contains
  real credentials, subscription IDs, or tenant IDs.

## Subscription and tenant allowlists

`AZURE_SUBSCRIPTION_ALLOWLIST` and `AZURE_TENANT_ALLOWLIST` (both
optional, comma-separated) are an *additional* restriction this server
enforces itself, independent of RBAC — every tool call that resolves a
subscription ID passes through `SubscriptionContext.resolve_subscription_id`
(`auth/session.py`) before any ARM client is built for it, so an
allowlist, once configured, is a real enforcement point rather than
merely documented intent. Leaving both unset means "whatever the
configured identity's RBAC role permits" — matching how this project's
AWS sibling defers resource-level scoping to IAM rather than
second-guessing it.

**Known limitation:** the `azure-mgmt-subscription` SDK's `Subscription`
model does not expose a `tenant_id` field, so a per-subscription tenant
check isn't possible via the API this server calls.
`ClientFactory.__init__` instead enforces the tenant allowlist once,
against the statically-configured `Settings.azure_tenant_id` — the
tenant the credential itself was explicitly configured against. This is
disclosed here rather than silently narrower than it appears.

## Logging

Every tool invocation produces exactly one structured JSON log line (see
`logging/setup.py`) containing: `timestamp`, `request_id`, `tool_name`,
`subscription_id`, `resource_group`, `duration_ms`, and `status`. Logs are
written to **stderr** (stdout is reserved for the MCP stdio protocol) and
are safe to ship as-is to Azure Monitor, Splunk, Datadog, or an ELK
stack.

What is explicitly **never** logged:

- Credentials of any kind (client secrets, certificates, access tokens).
- Full Azure API request/response payloads — only normalized,
  already-public identifiers (resource IDs, resource group names, counts)
  appear in log fields.
- Raw internal stack traces in the MCP response sent back to a client
  (see [Error handling](#error-handling)). Full tracebacks are logged
  server-side only, via `logger.exception(...)`, for operator debugging.

## Secrets

This repository ships no secrets. `.env.example` documents variable names
only, with empty values. `.gitignore` excludes `.env` and any local
credential files. CI/deployment pipelines should inject credentials via
their platform's secret manager (or, preferably, workload identity
federation / managed identity requiring no static secret at all) rather
than environment files.

## Redaction

Milestone 6 adds several Azure SDK models whose flattened attributes
carry secret-shaped fields directly, unlike this project's AWS sibling's
VPN pre-shared key (buried in an XML blob requiring explicit parsing to
reach) — here `shared_key`, `site_key`, `authorization_key`, and
`service_key` are plain object attributes on the very same response a
`list`/`get` call already returns:

| Field | Carried by | Never read in |
|---|---|---|
| `shared_key` | `VpnConnection`, `VpnSiteLinkConnection`, `ExpressRouteCircuitPeering`, `VirtualNetworkGatewayConnection` | `arm/vpn.py`, `arm/expressroute.py` |
| `site_key` | `VpnSite` | `arm/vpn.py` |
| `authorization_key` | `ExpressRouteCircuit`, `ExpressRouteCircuitConnection`, `ExpressRouteConnection`, `VirtualNetworkGatewayConnection` | `arm/vpn.py`, `arm/expressroute.py` |
| `service_key` | `ExpressRouteCircuit` | `arm/expressroute.py` |

This is redaction **by omission**, the same principle this project's AWS
sibling established for VPN pre-shared keys and Direct Connect BGP
authentication keys: a field that is never read cannot leak regardless of
what the raw SDK response contains — not a post-processing scrub, which
can miss an encoding variant or a future SDK response-shape change. Every
model carrying one of these fields is stamped `redacted: bool = True` so
a client can tell the record is intentionally incomplete rather than
assume it saw everything.

`ExpressRouteCircuitAuthorizationsOperations` (the operation group that
manages circuit authorizations, whose responses embed the actual
authorization key) is never called by any collector at all — there is
simply no `arm/` function for it.

**Statically enforced**, not just documented:
`tests/unit/test_no_mutation_calls.py::test_no_arm_module_ever_reads_a_secret_shaped_field`
scans every `arm/*.py` module's abstract syntax tree for an attribute
access or `getattr(...)` call matching one of these names — a future
collector that accidentally reads one of these fields fails this test
before it fails in a real Azure account. `tests/unit/test_hybrid_connectivity.py`
additionally asserts, per resource type, that a raw SDK mock carrying a
deliberately obvious sentinel secret value never appears anywhere in that
resource's normalized model output.

## No reachability claims

`azure_get_vnet_topology` returns a **configuration and attachment
graph**, never a reachability analysis. Every edge carries `evidence` — a
specific Azure API field observation (a subnet's `networkSecurityGroup`
reference, a peering's `remoteVirtualNetwork` ID, a NIC's IP
configuration) — and nothing in this codebase evaluates route table
contents, NSG rules, or peering connection state together to determine
whether traffic can actually flow between two nodes. A subnet-to-NSG
association proves the association exists; it does not prove which
packets that NSG actually permits — that requires evaluating the NSG's
rule set (which `azure_list_network_security_groups`/
`azure_get_effective_network_security_groups` expose, but this milestone
does not itself evaluate). A client consuming this graph must not present
it as "X can reach Y" without independently evaluating the routing and
security state that would actually determine that.

`azure_get_effective_route_table` and
`azure_get_effective_network_security_groups` report what Azure computed
as *currently applied* to one network interface — a precise, single-NIC
answer, not a path-level reachability verdict between two arbitrary
endpoints.

## Deterministic, evidence-bound diagnostics

Milestone 6's diagnostics engine (`azure_network_mcp.diagnostics`) carries
three guarantees, each directly answering a guardrail in the milestone's
own spec — see [docs/rule_catalog.md](rule_catalog.md) for the full rule
catalog these guarantees apply to:

- **Never claims certainty with incomplete data.** Every diagnostic
  conclusion is a `Finding` with an explicit `confidence` field, and
  `"indeterminate"` is a first-class value, not an error state or a
  silently-dropped result. A rule that cannot conclusively evaluate
  something it needs (an NSG missing from the collected snapshot, a
  route whose next hop leaves this tool's visibility, a route resolvable
  only via a resource outside the analyzed resource group) says so via
  `confidence: "indeterminate"` plus `limitations` naming exactly what
  was missing.
- **The core result is always deterministic Python logic, never an LLM
  judgment call.** Every function under `diagnostics.*` is a pure
  function of its `HybridNetworkSnapshot` (or, for
  `azure_explain_network_path`, per-NIC effective route/NSG data) input:
  CIDR longest-prefix-match route resolution, NSG rule priority
  evaluation, and every other check is ordinary, golden-testable code
  with no model call anywhere in the decision path. An AI client
  consuming a `Finding` may summarize or explain it in natural language,
  but the `severity`, `confidence`, and `summary` it's explaining were
  decided before that client ever saw the data.
- **`remediation` is advisory text only, never executed.** No code path
  anywhere in this repository takes a `Finding.remediation` string and
  acts on it — there is no "apply this fix" tool, and this milestone adds
  none. A client presenting a finding to a user must not describe a
  remediation suggestion as something that has been done.

`azure_get_hybrid_topology`, like `azure_get_vnet_topology` before it,
returns a configuration and attachment graph — see
[No reachability claims](#no-reachability-claims) below.
`azure_explain_network_path` is the deliberate, narrower exception to
"topology alone": it actually evaluates effective route resolution and
NSG rules together, and only claims `"allowed"` when it had enough
evidence to evaluate both layers — see `overall_verdict` in
[docs/rule_catalog.md](rule_catalog.md).

## Guardrails: Network Watcher and diagnostic tooling

This milestone never creates, starts, or stops a Network Watcher,
connection monitor, troubleshooter, or packet capture — every function
under `arm/network_watcher.py` calls only `get`/`list` operations (plus
`get_topology`, a POST-shaped read that takes a request body scoping the
query, not creating anything) against resources that already exist.
`begin_get_troubleshooting` (starts a new troubleshooting run) and every
`begin_*_packet_capture*` method are never called and are not in
`READ_ONLY_ACTIONS` — they are rejected by the guardrail's default
`begin_` rule like any other unreviewed method. See
[docs/limitations.md](limitations.md) for what this excludes.

## Error handling

Azure SDK/ARM errors are translated into a stable, client-safe error type
before being returned over MCP (see `tools/_shared.py`):

| Condition | `error.type` |
|---|---|
| Missing/unavailable Azure credential (`CredentialUnavailableError`) | `AUTHENTICATION_ERROR` |
| Invalid/expired credential, or ARM returns HTTP 401 | `AUTHENTICATION_ERROR` |
| RBAC denies the call, or ARM returns HTTP 403 | `AUTHORIZATION_ERROR` |
| Guardrail rejected the operation before it reached Azure | `GUARDRAIL_VIOLATION` |
| Requested resource does not exist, or ARM returns HTTP 404 | `RESOURCE_NOT_FOUND` |
| Subscription/tenant outside the configured allowlist | `SUBSCRIPTION_NOT_ALLOWED` |
| No `subscription_id` given and no default configured | `INVALID_CONFIGURATION` |
| Could not reach the Azure Resource Manager endpoint | `AZURE_SERVICE_ERROR` |
| Any other Azure API error | `AZURE_SERVICE_ERROR` |
| Unexpected internal error | `INTERNAL_ERROR` |

The client-facing `message` is a short, generic description — never a raw
Azure SDK exception string, stack trace, or internal file path. Full
exception details are logged server-side for operator troubleshooting.

## Threat boundaries

In scope for azure-network-mcp's own controls:

- Preventing the *server itself* from issuing a mutating Azure API call.
- Preventing credential material from leaking via logs or MCP responses.
- Bounding response size (pagination safety limits, bounded fan-out) to
  avoid resource exhaustion from a single tool call.
- Enforcing the configured subscription/tenant allowlists before any ARM
  client is built for a disallowed scope.

Explicitly **out of scope** for this application layer (owned by Azure
RBAC / infrastructure instead):

- Enforcing which Azure resources a given identity can *read*. If the
  configured role has `Microsoft.Network/virtualNetworks/read` on all
  VNets in scope, this server will return all VNets it is asked about —
  resource-level read scoping is an RBAC concern, not something this
  codebase second-guesses.
- Network-layer access control to Azure APIs (private endpoints, IP
  allowlisting on Azure AD Conditional Access) — a deployment concern,
  documented but not implemented here.
- Protecting the machine/container the server runs on.

## Future approval gates

This milestone has no mutating capability, so there is no approval flow
to design yet. If a future change introduces any Azure API call that
isn't `get`/`list` (or one of the two explicitly allowlisted effective-*
computations), it must not simply be added to `READ_ONLY_PREFIXES`.
Instead it will require:

1. A dedicated, explicitly-named tool (never a generic "run any Azure API"
   tool).
2. An explicit, human-in-the-loop confirmation step before execution.
3. Its own least-privilege RBAC action added to a *separate* role — never
   folded into the reader role this milestone documents.
4. A dry-run/preview mode where the Azure API supports one.

This is a design commitment, not something implemented in this milestone.
