# Milestone 2 Status Report — AWS Core Network Inventory and Topology

```
Milestone: 2 — AWS Core Network Inventory and Topology
Status: PASS
Date: 2026-08-27
```

## Prerequisite Check

Milestone 1 was re-validated before starting: `ruff check`, `ruff format
--check`, `mypy src`, and `pytest` (78 tests) all passed cleanly with no
defects found. No prerequisite fixes were required.

## Implemented

Twelve new read-only MCP tools, one AWS service module each, joined by a
new topology-composition module:

| Tool | AWS service module | AWS API(s) |
|---|---|---|
| `aws_list_internet_gateways` | `aws/gateways.py` | `ec2:DescribeInternetGateways` |
| `aws_list_egress_only_internet_gateways` | `aws/gateways.py` | `ec2:DescribeEgressOnlyInternetGateways` |
| `aws_list_nat_gateways` | `aws/nat.py` | `ec2:DescribeNatGateways` |
| `aws_list_security_groups` | `aws/security.py` | `ec2:DescribeSecurityGroups`, `ec2:DescribeSecurityGroupRules` |
| `aws_list_network_acls` | `aws/nacls.py` | `ec2:DescribeNetworkAcls` |
| `aws_list_network_interfaces` | `aws/enis.py` | `ec2:DescribeNetworkInterfaces` |
| `aws_list_vpc_peering_connections` | `aws/peering.py` | `ec2:DescribeVpcPeeringConnections` |
| `aws_list_managed_prefix_lists` | `aws/prefix_lists.py` | `ec2:DescribeManagedPrefixLists`, `ec2:GetManagedPrefixListEntries` |
| `aws_list_vpc_endpoints` | `aws/endpoints.py` | `ec2:DescribeVpcEndpoints` |
| `aws_list_vpc_endpoint_services` | `aws/endpoints.py` | `ec2:DescribeVpcEndpointServices` |
| `aws_list_load_balancers` | `aws/loadbalancers.py` | `elasticloadbalancing:DescribeLoadBalancers/DescribeListeners/DescribeTargetGroups/DescribeTargetHealth/DescribeTags` |
| `aws_get_vpc_topology` | `aws/topology.py` | all of the above, scoped to one VPC |

Milestone 1's three inventory tools were also enriched (additive fields
and optional parameters only — see "Schema Compatibility" below):
`aws_list_vpcs` gained CIDR associations, tenancy, and opt-in DNS
attributes; `aws_list_subnets` gained IPv6/AZ-ID fields; `aws_list_route_tables`
gained propagated-route detection and propagating-VGW IDs.

Full I/O schemas, IAM permissions, and example request/responses for
every tool are in [docs/tools.md](docs/tools.md). Full example IAM policy
(EC2 + ELBv2 + STS) is at the bottom of that file.

### Architecture

- Raw collection (`list_*` functions), normalization (pydantic models in
  `models/network_resources.py` / `models/topology.py`), and graph
  assembly (`aws/topology.py`) are kept in three separate layers per the
  milestone's requirement — `aws/topology.py` never calls boto3 directly,
  only the other service-layer functions. See
  [docs/architecture.md](docs/architecture.md#topology-construction) for
  the full call graph and a worked example.
- Every AWS call — paginated or not — still funnels through
  `security.guardrails.assert_read_only_operation` (unchanged from
  Milestone 1); no new guardrail logic was needed since the same
  `describe_*`/`get_*`/`list_*` prefix rule already covers every new
  operation used.
- Every normalized record now carries `account_id`, `region`, `tags`, and
  `observed_at` via a shared `AwsResource` base model (additive to
  Milestone 1's `Vpc`/`Subnet`/`RouteTable`, required on all new models).
- **Bounded fan-out**: `Settings.max_fanout_calls` (default 50) caps the
  three per-item enrichments AWS has no batch API for — VPC DNS
  attributes, managed prefix list entries, and ELBv2 target health. Each
  is opt-in via an `include_*` tool parameter (default `false`); items
  beyond the cap, or any enrichment call that fails, are recorded as a
  `CollectionWarning` in `metadata.warnings` rather than silently omitted
  or misrepresented as "doesn't exist."
- **Capability metadata**: every tool (Milestone 1's included) now
  declares `meta={"cloud": "aws", "read_only": true, "resource_types":
  [...]}` on registration, so a future federation layer can discover
  supported resource types and confirm read-only status via
  `list_tools()` alone, with no Python import of this codebase.

## Schema Compatibility

**No breaking change.** Every new field on `Vpc`/`Subnet`/`RouteTable` is
additive with a sensible default (`None` for opt-in-only data,
empty list for association lists); every new tool input parameter is
optional and defaults to reproducing Milestone 1 behavior exactly when
omitted. A client reading known fields by name needs no changes. Full
migration note in [CHANGELOG.md](CHANGELOG.md#020---milestone-2---vpc-topology).

One classification fix worth flagging for anyone who inspected Milestone 1
route output closely: AWS's `GatewayId` route field is reused for three
different things (an internet gateway, a virtual private gateway, and the
literal string `"local"`). Milestone 1's `target_type` mapped all
`GatewayId` routes to `"gateway"` regardless of which; Milestone 2 adds a
prefix check so a `vgw-*` target now correctly reports `target_type:
"virtual_private_gateway"` instead. This is additive (a new possible
enum value), not a rename, but is called out explicitly since it changes
what one existing field can contain for a route type that Milestone 1
technically already emitted (any deployment with a VPN gateway attached).

## Redactions and Partial-Result Behavior

- **VPC endpoint policies**: omitted unless `include_policies: true`;
  even then, truncated past 8000 characters
  (`policy_document_truncated: true`). Verified in
  `tests/unit/test_endpoints.py::test_policy_document_truncated_past_size_cap`.
- **No credentials/secrets surfaced**: this milestone's resource types
  (gateways, SGs, NACLs, ENIs, peering, prefix lists, endpoints, load
  balancers) carry no credential material by nature. (VPN pre-shared
  keys are explicitly out of scope for this milestone and would need the
  same redaction treatment if a future hybrid-connectivity milestone adds
  them — noted in docs/security.md.)
- **Partial results never masquerade as empty results**: every bounded-
  fan-out path and every topology-assembly sub-call appends a
  `CollectionWarning` (`FANOUT_CAP_REACHED`, `ENRICHMENT_FAILED`, or
  `OUT_OF_SCOPE_TARGET`) rather than silently returning less data. Tested
  in `test_prefix_lists.py::test_list_managed_prefix_lists_respects_fanout_cap`,
  `test_loadbalancers.py::test_list_load_balancers_target_health_respects_fanout_cap`,
  and `test_topology.py::test_topology_orphan_reference_to_out_of_scope_vgw`
  / `test_topology_orphan_reference_to_peer_vpc_outside_scope`.

## Test Results

```
$ ruff check .
All checks passed!

$ ruff format --check .
86 files already formatted

$ mypy src
Success: no issues found in 53 source files

$ pytest --cov=aws_cloudops_mcp --cov-report=term-missing
136 passed, 5 deselected (integration, not run -- see below)
TOTAL coverage: 95% (1370 statements, 70 missed)

$ python -m build --wheel
Successfully built aws_cloudops_mcp-0.2.0-py3-none-any.whl
```

New/updated test files (58 new test functions across 9 new files, plus
9 new tests added to `test_networking.py` and `test_server.py`):

- `test_gateways.py`, `test_nat.py`, `test_security.py`, `test_nacls.py`,
  `test_enis.py`, `test_peering.py`, `test_prefix_lists.py`,
  `test_endpoints.py`, `test_loadbalancers.py`, `test_topology.py`
  (12 tests — full-fixture join, orphan references x2, determinism,
  call-budget, zero-resources, `ResourceNotFoundError`, local-route and
  member-of edges), `test_no_mutation_calls.py` (behavioral proof: hooks
  botocore's event system during a full topology run and asserts every
  observed operation name is `describe_*`/`get_*`/`list_*` with no
  blocked keyword)
- `test_networking.py`: added DNS-attribute enrichment, VPC-ID filtering,
  and three pure-function tests against `_normalize_route` for blackhole
  state, propagated routes, and prefix-list destinations (moto does not
  simulate blackhole-state transitions or propagated-route creation, so
  these exercise the normalizer directly with synthetic AWS-shaped input)
- `test_server.py`: rewritten to assert the full 17-tool catalog and that
  every tool declares read-only capability metadata

Fixture coverage against the milestone's required scenarios: default and
custom VPCs, IPv6 CIDR associations, blackhole routes (synthetic, see
above), managed prefix lists (with/without entries, fan-out cap), VPC
peering (both directions), VPC endpoints (Gateway + Interface, with
policy redaction), NAT gateways, SG references (a security-group-to-
security-group rule), NACL ordering, ENIs, load balancers (with
listeners/target groups/target health), pagination, filters, partial
permission/enrichment failures, output caps, deterministic topology,
orphan references (two distinct cases), zero/empty resources, and no
mutation calls.

**Moto fidelity gaps encountered** (not product defects — documented so a
future reader doesn't mistake a missing test for missing coverage):
moto does not transition routes to `State: "blackhole"` when their
target is deleted; it does not add AWS's implicit rule-32767 deny-all
entry to custom NACLs; and it does not enforce the
`requester-vpc-info.vpc-id`/`accepter-vpc-info.vpc-id` filters on
`DescribeVpcPeeringConnections` (returns all connections regardless).
Where a behavioral test wasn't possible against moto, the underlying
normalization logic was tested directly against a synthetic AWS-shaped
response instead (see `test_networking.py`'s three `_normalize_route`
tests), and the affected assumption is called out inline in each test's
docstring.

## Observed Call Budget / Performance

`aws_get_vpc_topology`'s `api_call_count` was observed at 18 AWS API
requests for a rich single-VPC fixture (VPC, subnet, route table, IGW,
EIGW, NAT gateway, security group + rules, NACL, ENI, peering connection
[2 calls — requester + accepter side], VPC endpoint, load balancer +
target group + listener). This scales with the number of load balancers
(1 extra `DescribeListeners` call each) and, if `include_target_health`
is set, target groups (1 extra call each, bounded by
`max_fanout_calls`) — everything else is a fixed small number of batch
calls per resource type regardless of how many resources of that type
exist, since pagination handles volume within a single call sequence.
`test_topology.py::test_topology_tracks_api_call_count` asserts this
stays within a generous, non-brittle bound (5–40 calls) rather than
pinning an exact number that would break on every unrelated collector
change.

## Manual Validation

Real AWS credentials were not available in this environment (same
constraint as Milestone 1). A manual script drove the actual
`MCPServer.call_tool()` path end-to-end against moto-mocked AWS,
covering at least one call per new service plus the topology tool, per
the milestone's "offline MCP smoke calls" requirement. **All 14
scenarios passed:**

| Scenario | Result |
|---|---|
| `aws_list_internet_gateways` | PASS |
| `aws_list_egress_only_internet_gateways` | PASS |
| `aws_list_nat_gateways` | PASS |
| `aws_list_security_groups` | PASS |
| `aws_list_network_acls` | PASS |
| `aws_list_network_interfaces` | PASS |
| `aws_list_vpc_peering_connections` | PASS |
| `aws_list_managed_prefix_lists` | PASS |
| `aws_list_vpc_endpoints` | PASS |
| `aws_list_vpc_endpoint_services` | PASS (256 AWS-managed services visible) |
| `aws_list_load_balancers` | PASS |
| `aws_get_vpc_topology` (full join) | PASS — 17 nodes, 21 edges, 18 API calls |
| `aws_get_vpc_topology` (unknown VPC) | PASS → `RESOURCE_NOT_FOUND` envelope |
| `aws_list_vpc_endpoints` (policy redaction) | PASS → `policy_document: null` by default |

**Not performed** (same reasons as Milestone 1): running against a real
AWS account or Docker image build (Docker daemon not running in this
sandbox — Dockerfile unchanged from Milestone 1 and was not re-validated
by build here, though no dependency or entrypoint changes were made that
would affect it).

## Limitations

- Route target classification only distinguishes internet gateways from
  virtual private gateways by ID prefix (`igw-`/`vgw-`); this is AWS's
  own convention and has been stable for over a decade, but is not a
  documented API contract.
- `aws_list_vpc_peering_connections`'s requester/accepter-side filter
  behavior could not be behaviorally verified against moto (see "Moto
  fidelity gaps" above); the implementation follows AWS's documented
  filter names for `DescribeVpcPeeringConnections`, and the
  merge-without-duplicates logic itself is covered by
  `test_peering.py::test_list_vpc_peering_connections_visible_from_accepter_side`
  (which happens to also pass under moto's more permissive behavior).
- `aws_get_vpc_topology` requires both `region` and `vpc_id` — there is
  no "topology for every VPC in a region" mode. Deliberate: an unbounded
  multi-VPC topology call would defeat the bounded-fan-out design: a
  caller who wants that should call per-VPC and compose client-side, or
  wait for that fan-out control to be added deliberately in a future
  milestone.
- Cloud WAN, Network Manager, Transit Gateway, VPN, Direct Connect,
  Route 53/DNS, and flow logs are explicitly out of scope for this
  milestone (per its own guardrails) and are Milestone 3's stated scope.

## Files Created / Changed

```
New:
  src/aws_cloudops_mcp/aws/{collection,filters,gateways,nat,security,
    nacls,enis,peering,prefix_lists,endpoints,loadbalancers,topology}.py
  src/aws_cloudops_mcp/models/{network_resources,topology}.py
  src/aws_cloudops_mcp/tools/{capabilities,gateways,nat,security,nacls,
    enis,peering,prefix_lists,endpoints,loadbalancers,topology}.py
  tests/unit/test_{gateways,nat,security,nacls,enis,peering,
    prefix_lists,endpoints,loadbalancers,topology,no_mutation_calls}.py
  MILESTONE2_STATUS.md

Changed:
  src/aws_cloudops_mcp/aws/{networking,pagination,readonly}.py
  src/aws_cloudops_mcp/{config,exceptions,server}.py
  src/aws_cloudops_mcp/models/common.py
  src/aws_cloudops_mcp/tools/{_shared,identity,inventory,regions}.py
  tests/unit/test_{networking,server}.py
  README.md, CHANGELOG.md, docs/{architecture,security,tools}.md,
  pyproject.toml, src/aws_cloudops_mcp/__init__.py (version bump 0.1.0 -> 0.2.0)
```

## Technical Decisions

- **Config from `client_factory.settings`, not a global singleton.**
  Every new service module was written against
  `client_factory.settings` rather than Milestone 1's
  `config.get_settings()` module-level cache, and Milestone 1's
  `aws/networking.py` was refactored to match. This was necessary for
  the fan-out-cap tests (each constructs its own `Settings` with
  `max_fanout_calls=0`) and is a strict improvement in testability with
  no behavioral change in production (both resolve to the same
  configuration in practice).
- **Security group rules via `DescribeSecurityGroupRules`, not the
  legacy nested `IpPermissions` blocks.** Only the newer rule-level API
  gives each rule a stable `SecurityGroupRuleId`, which the tool
  contract explicitly requires. Costs one extra API call per
  `aws_list_security_groups` invocation (fetched once for all groups
  returned, not per-group) in exchange for that stability.
- **`aws_get_vpc_topology` scoped to one VPC, not "all VPCs in a
  region."** Keeps the bounded-fan-out guarantees meaningful (a
  region-wide topology call would need its own, larger fan-out budget)
  and keeps the tool's call cost predictable and testable.
- **Orphan references are edges, never fabricated nodes.** A route to an
  out-of-scope resource type, or a peering connection's far-side VPC,
  produces a real edge with a `target_id` that has no matching node —
  never a synthetic placeholder node standing in for something not
  actually collected. `CollectionWarning`s explain every such edge.

## Deferred Items

- Real-AWS validation and Docker build/run (same environment constraint
  as Milestone 1 — no AWS credentials, no running Docker daemon in this
  sandbox).
- `aws_list_vpc_peering_connections`'s filter behavior against real AWS
  (moto does not enforce the filter, so this is unverified end-to-end,
  though the underlying merge logic is unit-tested).
- Everything explicitly out of scope per this milestone's own
  guardrails: Transit Gateway, VPN, Direct Connect, Cloud WAN, Network
  Manager, Route 53/DNS, flow logs — all now Milestone 3's stated scope.

## Milestone 3 Handoff

Milestone 3 ("AWS Transit, Hybrid Connectivity, and DNS") can build
directly on this milestone's patterns without rework:

- The service-layer/normalization/tool-registration pattern established
  here (one `aws/*.py` module per resource family, one `tools/*.py`
  module registering its MCP tool(s), `CollectionResult` for anything
  with partial-result potential) extends cleanly to TGW/VPN/DX/Route 53.
- `Settings.max_fanout_calls` and `aws/collection.py`'s `track_calls()`
  are ready to reuse for Milestone 3's own bounded fan-out needs (e.g.
  per-TGW-route-table searches, per-hosted-zone record-set retrieval).
- `aws_get_vpc_topology`'s orphan-reference pattern (a `virtual_private_gateway`
  route target with a warning, no node) is the exact shape Milestone 3
  should resolve into a real node once VPN Gateway visibility exists —
  worth revisiting `_IN_SCOPE_ROUTE_TARGET_TYPES` in `aws/topology.py`
  once that lands, so VPN-connected VPCs stop producing orphan warnings
  for a target type Milestone 3 now covers.
- `aws_get_hybrid_topology` (Milestone 3's own topology tool) should
  follow `aws/topology.py`'s pattern exactly: raw collection stays
  separate from graph assembly, nodes/edges sorted deterministically,
  every edge backed by a specific evidence string, `api_call_count`
  tracked via the same `track_calls()` context manager.
- Milestone 3's spec explicitly calls for "Model operational state
  separately from configuration state" and "source API, collection
  completeness, and redaction indicators" on every record — richer than
  this milestone's `AwsResource` base (`account_id`/`region`/`tags`/
  `observed_at`). Recommend extending `AwsResource` itself (additively)
  rather than introducing a parallel base model, so Milestone 2's
  records inherit the same provenance fields for free.

Ready for Milestone 3: **YES**, once the deferred real-AWS/Docker
validation items above are picked up when an environment with
credentials and a running Docker daemon is available — nothing in this
milestone's own scope is unresolved.

---

## Recommended Git Commit

```
feat: complete milestone 2 AWS VPC topology resources
```
