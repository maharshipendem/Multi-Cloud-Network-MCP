# Milestone 3 Status Report — AWS Transit, Hybrid Connectivity, and DNS

```
Milestone: 3 — AWS Transit, Hybrid Connectivity, and DNS
Status: PASS
Date: 2026-08-27
```

## Prerequisite Check

Milestones 1 and 2 were re-validated before starting: `ruff check`, `ruff
format --check`, `mypy src`, and `pytest` (136 tests) all passed cleanly
with no defects found. No prerequisite fixes were required.

## Implemented

Twenty-eight new read-only MCP tools, organized into seven new AWS
service modules, joined by a new hybrid-topology composition module:

| Tool | AWS service module | AWS API(s) |
|---|---|---|
| `aws_list_transit_gateways` | `aws/transit_gateway.py` | `ec2:DescribeTransitGateways` |
| `aws_list_transit_gateway_attachments` | `aws/transit_gateway.py` | `ec2:DescribeTransitGatewayAttachments` |
| `aws_list_transit_gateway_route_tables` | `aws/transit_gateway.py` | `ec2:DescribeTransitGatewayRouteTables`, `ec2:GetTransitGatewayRouteTableAssociations`, `ec2:GetTransitGatewayRouteTablePropagations` |
| `aws_search_transit_gateway_routes` | `aws/transit_gateway.py` | `ec2:SearchTransitGatewayRoutes` |
| `aws_list_vpn_connections` | `aws/vpn.py` | `ec2:DescribeVpnConnections` |
| `aws_list_customer_gateways` | `aws/vpn.py` | `ec2:DescribeCustomerGateways` |
| `aws_list_vpn_gateways` | `aws/vpn.py` | `ec2:DescribeVpnGateways` |
| `aws_list_direct_connect_connections` | `aws/directconnect.py` | `directconnect:DescribeConnections` |
| `aws_list_direct_connect_lags` | `aws/directconnect.py` | `directconnect:DescribeLags` |
| `aws_list_direct_connect_virtual_interfaces` | `aws/directconnect.py` | `directconnect:DescribeVirtualInterfaces` |
| `aws_list_direct_connect_gateways` | `aws/directconnect.py` | `directconnect:DescribeDirectConnectGateways`, `directconnect:DescribeDirectConnectGatewayAssociations` |
| `aws_list_hosted_zones` | `aws/dns.py` | `route53:ListHostedZones`, `route53:GetHostedZone` |
| `aws_list_resource_record_sets` | `aws/dns.py` | `route53:ListResourceRecordSets` |
| `aws_list_resolver_endpoints` | `aws/dns.py` | `route53resolver:ListResolverEndpoints`, `route53resolver:ListResolverEndpointIpAddresses` |
| `aws_list_resolver_rules` | `aws/dns.py` | `route53resolver:ListResolverRules`, `route53resolver:ListResolverRuleAssociations` |
| `aws_list_resolver_rule_associations` | `aws/dns.py` | `route53resolver:ListResolverRuleAssociations` |
| `aws_list_resolver_query_log_configs` | `aws/dns.py` | `route53resolver:ListResolverQueryLogConfigs` |
| `aws_list_dns_firewall_rule_groups` | `aws/dns.py` | `route53resolver:ListFirewallRuleGroups` |
| `aws_list_dns_firewall_rule_group_associations` | `aws/dns.py` | `route53resolver:ListFirewallRuleGroupAssociations` |
| `aws_list_core_networks` | `aws/networkmanager.py` | `networkmanager:ListCoreNetworks`, `networkmanager:GetCoreNetwork`, `networkmanager:GetCoreNetworkPolicy` |
| `aws_list_global_networks` | `aws/networkmanager.py` | `networkmanager:DescribeGlobalNetworks` |
| `aws_list_network_manager_sites` | `aws/networkmanager.py` | `networkmanager:GetSites` |
| `aws_list_network_manager_devices` | `aws/networkmanager.py` | `networkmanager:GetDevices` |
| `aws_list_network_manager_links` | `aws/networkmanager.py` | `networkmanager:GetLinks` |
| `aws_list_network_manager_connections` | `aws/networkmanager.py` | `networkmanager:GetConnections` |
| `aws_list_transit_gateway_registrations` | `aws/networkmanager.py` | `networkmanager:GetTransitGatewayRegistrations` |
| `aws_list_flow_logs` | `aws/flowlogs.py` | `ec2:DescribeFlowLogs` |
| `aws_get_hybrid_topology` | `aws/hybrid_topology.py` | all of the above (VPC/VPN/DX/DNS branches), scoped to one Transit Gateway |

Full I/O schemas, IAM permissions, and example request/responses for
every tool are in [docs/tools.md](docs/tools.md). Full example IAM policy
(EC2 + ELBv2 + Direct Connect + Route 53 + Route 53 Resolver + Network
Manager + STS) is at the bottom of that file.

### Architecture

- Raw collection, normalization, and graph assembly remain in three
  separate layers, matching Milestone 2's precedent — `aws/hybrid_topology.py`
  never calls boto3 directly, only the other service-layer functions. See
  [docs/architecture.md](docs/architecture.md#hybrid-topology-construction)
  for the full call graph.
- `security.guardrails.READ_ONLY_PREFIXES` gained a `search_` prefix
  (`ec2:SearchTransitGatewayRoutes` added to `READ_ONLY_ACTIONS`) — the
  one genuinely read-only operation in this milestone's scope that
  doesn't follow the `describe_`/`get_`/`list_` convention. This was the
  guardrail correctly rejecting an unrecognized operation by default
  until reviewed, not a defect.
- `AwsResource` (the shared base every model extends) gained four
  additive optional fields per the milestone's request to "model
  operational state separately from configuration state" and expose
  "source API, collection completeness, and redaction indicators":
  `scope` (`"regional"`/`"global"`), `source_api`,
  `collection_completeness` (`"complete"`/`"partial"`), `redacted`.
- **Bounded fan-out** (same pattern as Milestone 2's
  `Settings.max_fanout_calls`): TGW route table associations/propagations
  (opt-in on `aws_list_transit_gateway_route_tables`), DNS resolver rule
  VPC associations (opt-in on `aws_list_resolver_rules`), Direct Connect
  gateway associations (opt-in on `aws_list_direct_connect_gateways`),
  and Cloud WAN core network details/policy (opt-in on
  `aws_list_core_networks`). Each degrades to a `CollectionWarning`
  (`FANOUT_CAP_REACHED`) rather than an unbounded call count.
- **Unsupported-capability degradation**: per the milestone's explicit
  instruction to "return the account and SDK support them; return
  explicit unsupported-capability metadata otherwise," `aws_list_core_networks`'s
  `include_details`/`include_policy` enrichments set
  `collection_completeness: "partial"` and append an
  `UNSUPPORTED_CAPABILITY` warning per-item on a `ClientError`, rather
  than failing the whole call or fabricating empty data. Similarly,
  `aws_list_dns_firewall_rule_groups`/`_associations` degrade to an empty
  list plus `ACCESS_DENIED`/`UNAVAILABLE` warnings when DNS Firewall's
  separate permission set is denied ("where allowed").

## Schema Compatibility

**No breaking change.** Every field added to `AwsResource` is additive
with a default (`scope="regional"`, `source_api=None`,
`collection_completeness="complete"`, `redacted=False`) — existing
Milestone 1/2 models and consumers are unaffected. Every new tool is
new; no Milestone 1/2 tool input or output contract changed. Full
migration note in
[CHANGELOG.md](CHANGELOG.md#030---milestone-3---transit-hybrid-connectivity-and-dns).

## Redactions and Partial-Result Behavior

- **VPN pre-shared keys** (`aws_list_vpn_connections`): never read from
  `ec2:DescribeVpnConnections`'s `CustomerGatewayConfiguration` field —
  redaction by omission, not scrubbing. Every record stamped
  `redacted: true`. Verified in
  `tests/unit/test_vpn.py::test_vpn_connection_never_leaks_pre_shared_key`
  against a real moto-generated PSK.
- **Direct Connect BGP authentication keys**
  (`aws_list_direct_connect_virtual_interfaces`): never read from
  `authKey` (top-level or per BGP peer) or `customerRouterConfig`.
  Verified in
  `tests/unit/test_directconnect.py::test_direct_connect_virtual_interface_never_leaks_auth_key`
  against a `Stubber` response containing both secrets (moto does not
  implement this operation). Caught during documentation review: the
  normalizer omitted the fields correctly but did not stamp
  `redacted: true` on the record (unlike `VpnConnection`, which does).
  Fixed in `aws/directconnect.py` to match the established convention;
  the test above now also asserts `redacted is True`.
- **VPC Flow Logs** (`aws_list_flow_logs`): configuration/delivery
  metadata only — no field in `FlowLogConfig` can hold log record
  contents, verified at the schema level (field-name inspection, not
  just one fixture's data) in
  `tests/unit/test_flowlogs.py::test_list_flow_logs_never_exposes_log_contents`.
- **DNS query logs** (`aws_list_resolver_query_log_configs`): same
  principle — configuration metadata only, no query-record retrieval
  path exists anywhere in this codebase.
- **Cloud WAN policy documents** (`aws_list_core_networks` with
  `include_policy: true`): reuses Milestone 2's `MAX_POLICY_DOCUMENT_CHARS`
  size guard and `policy_document_truncated` flag.
- **Partial results never masquerade as empty results**: every bounded
  fan-out path and unsupported-capability path appends a
  `CollectionWarning` rather than silently returning less data. Tested
  across `test_dns.py`, `test_networkmanager.py`, `test_directconnect.py`,
  `test_transit_gateway.py`.
- **No reachability claims**: `aws_get_hybrid_topology` returns a
  configuration/attachment graph with per-edge `evidence`, never a
  reachability verdict — route table contents, security group/NACL
  rules, and VPN/DX tunnel state are not evaluated together to determine
  whether traffic can actually flow. See
  [docs/security.md](docs/security.md#no-reachability-claims).

## Test Results

```
$ ruff check .
All checks passed!

$ ruff format --check .
115 files already formatted

$ mypy src
Success: no issues found in 74 source files

$ pytest --cov=src --cov-report=term-missing
200 passed, 5 deselected (integration, not run -- see below)
TOTAL coverage: 95% (2441 statements, 118 missed)

$ python -m build
Successfully built aws_cloudops_mcp-0.3.0.tar.gz and aws_cloudops_mcp-0.3.0-py3-none-any.whl
```

New test files (64 new test functions across 7 new files, plus updates
to `test_guardrails.py`, `test_server.py`, and `test_no_mutation_calls.py`):

- `test_transit_gateway.py` (10 tests — basic listing, attachment
  resource-type filtering, route table association/propagation
  enrichment on/off, fanout cap, 3 `Stubber`-based route-search tests
  since moto crashes on realistic `MaxResults` values)
- `test_vpn.py` (6 tests, including the PSK-never-leaks proof)
- `test_directconnect.py` (5 tests, including the BGP-auth-key-never-leaks
  proof via `Stubber`)
- `test_dns.py` (16 tests — hosted zones with linked VPCs, record-set
  output cap, resolver endpoints, resolver rules with/without
  associations including a split-horizon DNS scenario, fanout cap,
  resolver rule associations, query log configs, DNS Firewall
  groups/associations happy-path and access-denied degradation via
  `Stubber`, hosted-zone best-effort degradation when the per-zone VPC
  lookup is denied, and a direct unit test of the `_routing_policy`
  classifier covering all six AWS routing-policy shapes)
- `test_networkmanager.py` (13 tests — global networks/sites/devices/
  links, core networks with/without detail and policy enrichment,
  the `GetCoreNetwork`-denied degradation path, policy happy-path with
  truncation, policy fanout-cap path, zero-resources, 2 `Stubber`-based
  tests for connections/registrations)
- `test_flowlogs.py` (4 tests, including the schema-level
  never-exposes-log-contents proof)
- `test_hybrid_topology.py` (8 tests — full VPC/VPN/DNS join, the
  `external_endpoint` label for a customer gateway's public IP, edge
  evidence/relationship presence, deterministic ordering across repeated
  calls, `api_call_count` bounds, `ResourceNotFoundError` for an unknown
  TGW, zero-attachments, and a synthetic-attachment-list test covering
  cross-account attachment warnings, out-of-scope attachment types, and
  Direct Connect gateway attachment resolution — all three scenarios moto
  cannot produce)
- `test_guardrails.py`: `search_transit_gateway_routes` added to the
  read-only operations list
- `test_server.py`: rewritten to assert the full 45-tool catalog
- `test_no_mutation_calls.py`: added a second behavioral proof
  (`test_full_hybrid_topology_run_issues_only_read_only_operations`)
  spanning EC2 (TGW/VPN/CGW), Route 53, and Route 53 Resolver

**Moto fidelity gaps encountered** (not product defects — documented so
a future reader doesn't mistake a missing test for missing coverage):
`SearchTransitGatewayRoutes` crashes with any non-null `MaxResults`
(`KeyError: slice(...)`, a genuine moto bug); `DescribeVirtualInterfaces`
and `DescribeDirectConnectGateways`/`DescribeDirectConnectGatewayAssociations`
are not implemented; `ListFirewallRuleGroups` and
`ListFirewallRuleGroupAssociations` are not implemented (and would raise
a Python `NotImplementedError`, not the `ClientError` real AWS returns for
a permission gap — tests are stubbed against a real `AccessDeniedException`
instead); `GetConnections`/`GetTransitGatewayRegistrations` (Network
Manager) return "Not yet implemented" `ClientError`s; `GetCoreNetworkPolicy`
is not implemented; `hasLogicalRedundancy` (Direct Connect) is returned
as a Python bool instead of AWS's documented string enum (defensive
`_stringify()` coercion added, matching the model's already-correct
`str | None` type). Where a behavioral test wasn't possible against
moto, either the underlying normalizer was tested directly against
synthetic AWS-shaped input, or `botocore.stub.Stubber` was used against
the real service model instead — never by relaxing product code to match
moto's incorrect behavior.

One test-writing note worth flagging: an initial `Stubber`-based test for
`aws_list_dns_firewall_rule_groups`'s happy path used a synthetic response
including `RuleCount`/`Status` fields. `Stubber`'s real-service-model
validation rejected it — `route53resolver:ListFirewallRuleGroups`'s actual
response shape (per botocore's service model) never includes those
fields at all; they are `GetFirewallRuleGroup`-only. This was caught
before it could hide a latent assumption: the product code's `.get()`
calls for those fields were already correct (they naturally return
`None` against a real response), but the original synthetic test data
would have made the test pass without proving anything real. Fixed by
correcting the test fixture, not the product code.

## Observed Call Budget / Performance

`aws_get_hybrid_topology`'s `api_call_count` was observed within a
5–30-call range for a fixture spanning one Transit Gateway with a VPC
attachment (plus a linked private hosted zone and a resolver endpoint in
that VPC) and a VPN attachment (plus its customer gateway). This scales
with the number of resolvable attachments (each VPC/VPN/DX-gateway
attachment adds a small, fixed number of enrichment calls) rather than
with total resource volume, since pagination handles volume within a
single call sequence — the same shape as Milestone 2's
`aws_get_vpc_topology` budget.
`test_hybrid_topology.py::test_hybrid_topology_tracks_api_call_count`
asserts a generous, non-brittle bound (3–30 calls) rather than pinning an
exact number that would break on every unrelated collector change.

## Manual Validation

Real AWS credentials were not available in this environment (same
constraint as Milestones 1 and 2). A manual script drove the actual
`MCPServer.call_tool()` path end-to-end against moto-mocked AWS
(distinct from the unit suite, which calls the service layer directly,
not the MCP tool-registration/envelope layer), covering at least one
call per new service plus the hybrid topology tool, per the milestone's
"offline MCP smoke calls" requirement. **All 11 scenarios passed:**

| Scenario | Result |
|---|---|
| `aws_list_transit_gateways` | PASS |
| `aws_list_transit_gateway_attachments` | PASS |
| `aws_list_vpn_connections` | PASS |
| `aws_list_customer_gateways` | PASS |
| `aws_list_direct_connect_connections` | PASS |
| `aws_list_hosted_zones` | PASS |
| `aws_list_resolver_endpoints` | PASS |
| `aws_list_global_networks` | PASS |
| `aws_list_flow_logs` | PASS |
| `aws_get_hybrid_topology` (full join) | PASS — 9 nodes, 8 edges, 8 API calls |
| `aws_get_hybrid_topology` (unknown TGW) | PASS → `RESOURCE_NOT_FOUND` envelope |

**Not performed** (same reasons as Milestones 1 and 2): running against
a real AWS account, or a Docker image build (Docker daemon not running
in this sandbox — Dockerfile unchanged from Milestone 1/2 and was not
re-validated by build here, though no dependency or entrypoint changes
were made that would affect it).

## Limitations

- `aws_get_hybrid_topology` requires `transit_gateway_id` — there is no
  "topology for every TGW in a region" mode, for the same
  bounded-fan-out reasoning `aws_get_vpc_topology` already documents.
- Classic Network Manager (sites/devices/links/connections) is
  deliberately not joined into `aws_get_hybrid_topology`'s graph — see
  [docs/architecture.md](docs/architecture.md#hybrid-topology-construction)
  for why. Its resources remain reachable via their own granular
  `aws_list_network_manager_*` tools.
- `aws_list_dns_firewall_rule_groups`'s `rule_count`/`status` fields are
  always `None` from this tool today — `ListFirewallRuleGroups` itself
  never returns them (confirmed against the real service model); only
  `GetFirewallRuleGroup` (a future opt-in per-item enrichment, not
  implemented in this milestone) would populate them.
- Route target classification in `aws_get_vpc_topology` (Milestone 2)
  still reports out-of-scope `vgw-*` targets as orphan references rather
  than resolving them into real `virtual_private_gateway` nodes now that
  Milestone 3 adds VPN Gateway visibility (`aws_list_vpn_gateways`) —
  Milestone 2's own handoff note flagged this as a natural follow-up once
  VPN visibility landed, but it is out of this milestone's stated scope
  (which added `aws_get_hybrid_topology` as a new tool rather than
  modifying `aws_get_vpc_topology`) and was not picked up here. Deferred
  to Milestone 4 — see below.
- Reachability is explicitly not claimed anywhere in this milestone's
  output, per its own guardrails; a future Reachability Analyzer
  integration is out of scope here by design.

## Files Created / Changed

```
New:
  src/aws_cloudops_mcp/aws/{transit_gateway,vpn,directconnect,dns,
    networkmanager,flowlogs,hybrid_topology}.py
  src/aws_cloudops_mcp/models/{transit_gateway,vpn,directconnect,dns,
    networkmanager,flowlogs,hybrid_topology}.py
  src/aws_cloudops_mcp/tools/{transit_gateway,vpn,directconnect,dns,
    networkmanager,flowlogs,hybrid_topology}.py
  tests/unit/test_{transit_gateway,vpn,directconnect,dns,networkmanager,
    flowlogs,hybrid_topology}.py
  MILESTONE3_STATUS.md

Changed:
  src/aws_cloudops_mcp/models/common.py (AwsResource: scope, source_api,
    collection_completeness, redacted)
  src/aws_cloudops_mcp/security/guardrails.py (search_ prefix,
    search_transit_gateway_routes)
  src/aws_cloudops_mcp/server.py (register 7 new tool modules)
  tests/unit/test_{guardrails,server,no_mutation_calls}.py
  README.md, CHANGELOG.md, docs/{architecture,security,tools}.md,
  pyproject.toml (version bump 0.2.0 -> 0.3.0)
```

## Technical Decisions

- **`aws_get_hybrid_topology` scoped to one Transit Gateway, not "all
  hybrid resources" or a VPC.** A TGW is the resource every attachment
  type in this milestone's scope (VPC, VPN, Direct Connect gateway)
  naturally hangs off of, keeping the graph bounded and predictable —
  the same reasoning that scoped Milestone 2's topology tool to one VPC.
- **`external_endpoint` as a distinct node type from orphan references.**
  A customer gateway's public IP is a genuine non-AWS entity (the
  on-premises boundary), not an AWS resource this milestone simply
  didn't collect. Modeling it as an orphan reference would misrepresent
  it as an in-scope-but-uncollected AWS resource. It gets its own typed
  node instead, explicitly labeled, joined by a `represents` edge.
- **TGW route table associations/propagations as inline opt-in fields,
  not separate tools.** Mirrors Milestone 2's `RouteTable.associations`
  pattern; keeps the 45-tool count from growing further while staying
  granular at the data-model level (`include_associations`/
  `include_propagations` on `aws_list_transit_gateway_route_tables`).
- **Redaction by omission, never by scrubbing, for both secrets this
  milestone touches (VPN PSK, DX BGP auth key).** A field never read
  from the raw AWS response cannot leak regardless of encoding or a
  future AWS response-format change; a regex scrub can miss a variant.
  This was a deliberate, discussed design choice, not an incidental
  implementation detail — see [docs/security.md](docs/security.md).
- **`search_` added to `READ_ONLY_PREFIXES` explicitly, not a looser
  prefix match.** `SearchTransitGatewayRoutes` is the only AWS operation
  in this milestone's scope that needed it; the guardrail change is
  narrowly scoped (one new prefix, one new explicit allowlist entry) so
  it doesn't inadvertently widen what future milestones can slip through
  unreviewed.

## Deferred Items

- Real-AWS validation and Docker build/run (same environment constraint
  as Milestones 1 and 2).
- Resolving `aws_get_vpc_topology`'s `vgw-*` orphan references into real
  `virtual_private_gateway` nodes now that `aws_list_vpn_gateways` exists
  (flagged by Milestone 2's own handoff note; out of this milestone's
  stated scope, recommended for Milestone 4).
- `aws_list_dns_firewall_rule_groups`'s `rule_count`/`status` enrichment
  via a future opt-in `GetFirewallRuleGroup` per-item call (currently
  always `None` from the list call alone, correctly, per the real AWS
  response shape).
- Everything explicitly out of scope per this milestone's own guardrails:
  route/tunnel/DNS/Network-Manager mutations, log-content retrieval,
  secret/config download, cross-cloud correlation, and any reachability
  claim from topology data.

## Milestone 4 Handoff

- The service-layer/normalization/tool-registration pattern holds for a
  fourth consecutive milestone without rework — expect it to keep
  holding for CloudWatch/CloudTrail/Config/Reachability Analyzer.
- `AwsResource`'s `scope`/`source_api`/`collection_completeness`/
  `redacted` fields are now available to every future model for free;
  no further base-model changes should be needed for provenance/
  redaction metadata.
- The `Stubber`-over-moto pattern established here (pre-warm
  `client_factory._account_id_cache["__base__"]` before patching
  `get_client`, since the patch makes `get_client` return the same
  client regardless of requested service) is worth carrying forward —
  moto's coverage gaps are more common, not less, in less-used AWS APIs
  like the ones a fourth milestone is likely to touch.
- Revisit the deferred `vgw-*` orphan-reference resolution in
  `aws/topology.py` early in Milestone 4, before it's forgotten a second
  time.

Ready for Milestone 4: **YES**, once the deferred real-AWS/Docker
validation items above are picked up when an environment with
credentials and a running Docker daemon is available — nothing in this
milestone's own scope is unresolved.

---

## Recommended Git Commit

```
feat: complete milestone 3 AWS transit, hybrid connectivity, and DNS
```
