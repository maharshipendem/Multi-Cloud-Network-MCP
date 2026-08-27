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

No other changes were made to the suggested structure for Milestone 1.

**Milestone 2 additions** — one `aws/*.py` service module per new resource
family (`gateways.py`, `nat.py`, `security.py`, `nacls.py`, `enis.py`,
`peering.py`, `prefix_lists.py`, `endpoints.py`, `loadbalancers.py`,
`topology.py`), following the same one-module-per-resource-family pattern
already established. Three shared modules were added alongside them:
`aws/filters.py` (the `vpc_filter`/`ids_filter` builders, factored out of
`aws/networking.py` once four more modules needed the same `Filters`
shape), `aws/collection.py` (`observed_at` timestamps, the opt-in AWS-call
counter, and `CollectionResult` — the wrapper a service function returns
when it may produce partial-result warnings), and `models/network_resources.py`
+ `models/topology.py` (kept separate from `models/common.py` purely for
file size, still part of the same normalized-response contract).
`tools/capabilities.py` adds the `meta=` dict attached to every tool
(Milestone 1's included) so a future federation layer can discover
resource types and confirm read-only status via `list_tools()` alone,
without importing this codebase.

**Milestone 3 additions** — one `aws/*.py` service module per new
resource family again: `transit_gateway.py`, `vpn.py`, `directconnect.py`,
`dns.py` (Route 53 + Route 53 Resolver + DNS Firewall share one module
since they share the Resolver API and the split-horizon DNS join between
them), `networkmanager.py` (classic Network Manager + Cloud WAN, which
share the `networkmanager` boto3 client), `flowlogs.py`, and
`hybrid_topology.py`. `READ_ONLY_PREFIXES` in `security/guardrails.py`
gained a `search_` prefix (with `ec2:SearchTransitGatewayRoutes`
explicitly added to `READ_ONLY_ACTIONS`) because that operation is
genuinely read-only but doesn't follow the `describe_`/`get_`/`list_`
naming convention every other AWS read API in this codebase uses — this
is the guardrail correctly rejecting an unrecognized operation name by
default until the exception was reviewed and added explicitly, not a
guardrail bug. `models/common.py`'s `AwsResource` base gained four
additive optional fields used across Milestone 3's models: `scope`
(`"regional"` by default; Route 53 hosted zones, DX gateways, and Network
Manager/Cloud WAN resources set `"global"`), `source_api` (which AWS
operation produced this record, for traceability),
`collection_completeness` (`"complete"` unless a bounded enrichment call
degraded, in which case `"partial"`), and `redacted` (`true` on any
record from which a field was deliberately withheld — see
[docs/security.md](security.md)).

## Topology construction

`aws_get_vpc_topology` (Milestone 2) is the one tool that doesn't map to a
single AWS API family — it's a composition layer that calls every other
Milestone 2 service-layer function for one VPC and shapes their already-
normalized output into a graph. `aws/topology.py` never calls boto3
directly; it only imports and calls the other `aws.*` service functions,
keeping "raw collection" (each `list_*` function), "normalization" (each
service module's own dataclasses/models), and "graph assembly" (this
module) in three cleanly separated layers, per the milestone's
architecture requirement:

```
aws_get_vpc_topology(region, vpc_id)
         |
         v
  aws.topology.get_vpc_topology()
         |
         +--> aws.networking.list_vpcs/list_subnets/list_route_tables
         +--> aws.gateways.list_internet_gateways / list_egress_only_internet_gateways
         +--> aws.nat.list_nat_gateways
         +--> aws.security.list_security_groups   (+ rules)
         +--> aws.nacls.list_network_acls
         +--> aws.enis.list_network_interfaces
         +--> aws.peering.list_vpc_peering_connections
         +--> aws.endpoints.list_vpc_endpoints
         +--> aws.loadbalancers.list_load_balancers (+ listeners, target groups)
         +--> aws.prefix_lists.list_managed_prefix_lists   (only for referenced pl-*)
         |
         v
  For each result: build a TopologyNode (id, type, label, tags) and
  TopologyEdge(s) (source_id, target_id, relationship, evidence) --
  evidence is always a specific field observation (e.g. "route in
  rtb-123: 0.0.0.0/0 -> gateway:igw-abc"), never an inference.
         |
         v
  Sort nodes by (node_type, node_id), edges by (source_id, target_id,
  relationship) for deterministic output; collect CollectionWarnings
  from every sub-call plus any out-of-scope route/peering targets.
         |
         v
  VpcTopology { vpc_id, region, nodes[], edges[], warnings[], api_call_count }
```

**Orphan references.** A route can target a resource type this milestone
doesn't collect (a virtual private gateway, in advance of hybrid-
connectivity milestones) and a peering connection's other side is, by
definition, outside a single-VPC topology's scope. Both cases still
produce a real edge (AWS reported the relationship; dropping it would
hide true topology) with a `target_id` that has no matching node, plus a
`CollectionWarning` explaining why. A missing node is never treated as "no
relationship exists" — see [docs/security.md](security.md) for why
silently-fabricated emptiness is explicitly disallowed.

**Bounded fan-out.** AWS has no batch API for a handful of per-item
enrichments this milestone supports: DNS attributes per VPC, prefix list
entries per prefix list, and target health per target group. Each is
opt-in (an `include_*` tool parameter, default `false`) and, when
requested, capped at `Settings.max_fanout_calls` (default 50) — items
beyond the cap are skipped with a `CollectionWarning` rather than making
an unbounded number of AWS calls or silently truncating without
explanation. `aws/collection.py`'s `track_calls()` context manager counts
every underlying AWS request made during topology assembly (each page of
a paginated call counts separately) and surfaces it as
`VpcTopology.api_call_count`, so a caller can reason about the cost of one
`aws_get_vpc_topology` invocation.

## Hybrid topology construction

`aws_get_hybrid_topology` (Milestone 3) is the transit/hybrid-connectivity
analog of `aws_get_vpc_topology`: a composition layer, not a single AWS
API family. `aws/hybrid_topology.py` never calls boto3 directly; like
`aws/topology.py`, it only calls other already-normalizing `aws.*`
service functions and shapes their output into a graph, reusing the same
`TopologyNode`/`TopologyEdge` shapes from `models/topology.py`
(`models/hybrid_topology.py` adds only the `HybridTopology` container
around them).

**Why anchor on a Transit Gateway, not a VPC or "all resources."** A TGW
is the one resource type the milestone's scope (VPC, TGW, VPN, DX, Cloud
WAN, DNS) naturally hangs off of — every attachment type this milestone
covers (`vpc`, `vpn`, `direct-connect-gateway`) is, definitionally, a TGW
attachment. Scoping the tool to one `transit_gateway_id` keeps the graph
bounded and the AWS call count predictable, the same reasoning that scoped
`aws_get_vpc_topology` to one `vpc_id`.

```
aws_get_hybrid_topology(region, transit_gateway_id)
         |
         v
  aws.hybrid_topology.get_hybrid_topology()
         |
         +--> aws.transit_gateway.list_transit_gateways        (anchor lookup;
         |                                                       ResourceNotFoundError if absent)
         +--> aws.transit_gateway.list_transit_gateway_attachments
         |
         |    for each attachment, by resource_type:
         |      vpc                    --> aws.networking.list_vpcs
         |                                 --> aws.dns.list_hosted_zones      (linked_vpc_ids match)
         |                                 --> aws.dns.list_resolver_endpoints (host_vpc_id match)
         |      vpn                    --> aws.vpn.list_vpn_connections
         |                                 --> aws.vpn.list_customer_gateways
         |                                 --> external_endpoint node (customer gateway public IP)
         |      direct-connect-gateway --> aws.directconnect.list_direct_connect_gateways
         |      (anything else, e.g. peering, connect, tgw-peering)
         |                             --> attachment node only; OUT_OF_SCOPE_TARGET warning
         |
         v
  Same node/edge/evidence shape as aws_get_vpc_topology; nodes sorted by
  (node_type, node_id), edges by (source_id, target_id, relationship) for
  deterministic output; api_call_count tracked the same way.
         |
         v
  HybridTopology { transit_gateway_id, region, nodes[], edges[], warnings[], api_call_count }
```

**`external_endpoint` nodes vs. orphan references.** Milestone 2
established the orphan-reference pattern: an edge whose `target_id` has
no matching node, always paired with a `CollectionWarning`, used when the
missing resource is still an AWS resource just outside this milestone's
collection scope (e.g. an out-of-scope attachment type above). Milestone
3 adds a second, deliberately distinct pattern for a case orphan
references don't fit: a customer gateway's public IP is not an AWS
resource at all — it is the genuine on-premises network boundary the spec
asks to have "labeled." Modeling it as an orphan reference would
misrepresent it as an AWS resource this milestone simply didn't collect.
Instead it gets its own `external_endpoint` node (`node_id` = the public
IP, `label` = the same), joined to the customer gateway node by a
`represents` edge — an explicit, correctly-typed graph entry rather than
a bare dangling reference.

**Deliberate exclusion of classic Network Manager from the join.** The
milestone's topology sentence names "VPC, TGW, VPN, DX, Cloud WAN, and
DNS" — it does not mention Network Manager sites, devices, links, or
connections. Those have their own granular `aws_list_network_manager_*`
tools (documented in [docs/tools.md](tools.md)) but are not joined into
`aws_get_hybrid_topology`'s graph: a classic Network Manager site/device
doesn't have a deterministic, evidence-backed edge into a TGW attachment
graph the way a VPC or VPN connection does (the on-ramp is a physical/
logical construct Network Manager tracks separately, not an AWS API
relationship this tool can cite as evidence), so joining them would
require inference rather than observation — which
[docs/security.md](security.md) explicitly disallows for this tool.

**No reachability claims.** Every edge here, like `aws_get_vpc_topology`'s,
carries `evidence` — a specific AWS API field observation, never an
inference. The tool's output is a configuration/attachment graph, not a
reachability analysis: it does not evaluate route table contents, security
group rules, NACLs, or tunnel state to determine whether traffic can
actually flow between two nodes. See
[docs/security.md](security.md#no-reachability-claims).

## Multi-cloud compatibility

This repository contains AWS-specific logic only. Its output models
(`aws_cloudops_mcp.models`) and response envelope
(`aws_cloudops_mcp.models.responses.ToolResponse`) are cloud-agnostic in
shape (`success`, `tool`, `account_id`, `region`, `data`, `metadata`,
`error`) so that a future multi-cloud orchestration layer can consume AWS,
Azure, and GCP MCP server output consistently, without needing AWS-specific
parsing logic. No orchestration, federation, or cross-cloud logic lives in
this repository.
