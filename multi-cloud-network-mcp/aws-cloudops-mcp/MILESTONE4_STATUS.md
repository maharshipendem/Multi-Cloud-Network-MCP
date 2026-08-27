# Milestone 4 Status Report — AWS Network Diagnostics and Explainable Analysis

```
Milestone: 4 — AWS Network Diagnostics and Explainable Analysis
Status: PASS
Date: 2026-08-27
```

## Prerequisite Check

Milestones 1-3 were re-validated before starting: `ruff check`, `ruff
format --check`, `mypy src`, and `pytest` (290 tests) all pass cleanly
with no defects found beyond the two genuine, disclosed bugs fixed as
part of this milestone's own work (see "Fixes to earlier milestones"
below).

## Implemented

A deterministic, boto3/MCP-transport-independent diagnostic engine
(`aws_cloudops_mcp.diagnostics`), a single AWS-facing seam that feeds it
(`aws/snapshot.py`), and eight new MCP tools built on it.

### Rule catalog

| Rule ID | Module | Title | Default severity |
|---|---|---|---|
| `ROUTE-001` | `diagnostics.routing` | Route resolution | info |
| `SEC-001` | `diagnostics.security` | Security group evaluation | info |
| `SEC-002` | `diagnostics.security` | Network ACL evaluation | info |
| `EXPOSE-001` | `diagnostics.exposure` | ENI internet exposure | medium |
| `EXPOSE-002` | `diagnostics.exposure` | Load balancer internet exposure | medium |
| `CONSIST-001` | `diagnostics.consistency` | CIDR overlap | high |
| `CONSIST-002` | `diagnostics.consistency` | Orphaned Transit Gateway attachment | medium |
| `CONSIST-003` | `diagnostics.consistency` | Missing Transit Gateway route propagation | low |
| `CONSIST-004` | `diagnostics.consistency` | Asymmetric VPC peering route | high |
| `CONSIST-005` | `diagnostics.consistency` | Degraded or failed resource state | high |

`ROUTE-001`/`SEC-001`/`SEC-002` run inside `aws_explain_network_path`
(one source/destination question at a time); `EXPOSE-*`/`CONSIST-*` run
inside `aws_find_network_risks` (whole-snapshot scans) and, for
`CONSIST-005`, also inside `aws_get_network_health`. Every rule is
registered exactly once, at import time, via
`diagnostics.models.register_rule()` — the catalog can never silently
drift from what actually runs.

### Tools, AWS APIs, IAM actions

| Tool | Purpose | New IAM actions |
|---|---|---|
| `aws_explain_network_path` | Route + SG + NACL evaluation for one source/destination pair | none (reuses Milestones 1-3's policy) |
| `aws_find_network_risks` | Whole-snapshot risk scan (consistency + exposure) | none |
| `aws_get_network_health` | Degraded resources, Flow Log coverage, opt-in metrics/analyses/changes | `cloudtrail:LookupEvents`, `cloudwatch:GetMetricStatistics`, `ec2:DescribeNetworkInsights*` (opt-in only) |
| `aws_list_network_insights_paths` | Reachability Analyzer paths (read-only) | `ec2:DescribeNetworkInsightsPaths` |
| `aws_list_network_insights_analyses` | Reachability Analyzer analyses (read-only) | `ec2:DescribeNetworkInsightsAnalyses` |
| `aws_list_network_insights_access_scopes` | Network Access Analyzer scopes (read-only) | `ec2:DescribeNetworkInsightsAccessScopes` |
| `aws_list_network_insights_access_scope_analyses` | Network Access Analyzer scope analyses (read-only) | `ec2:DescribeNetworkInsightsAccessScopeAnalyses` |
| `aws_get_network_insights_access_scope_analysis_findings` | Bounded scope-analysis finding retrieval | `ec2:GetNetworkInsightsAccessScopeAnalysisFindings` |

Full I/O schemas, example request/responses, and the complete updated
IAM policy are in [docs/tools.md](docs/tools.md). Total tool count: **53**
(5 + 12 + 28 + 8).

### Architecture

- `diagnostics/` imports neither boto3/botocore nor the MCP transport —
  verified by inspection (no such imports anywhere under
  `src/aws_cloudops_mcp/diagnostics/`) and by construction (the offline
  tests in `test_diagnostics_offline.py` run the full engine with no
  `mock_aws()`, no `client_factory`, nothing AWS-related touched at all).
- `aws/snapshot.py::collect_network_snapshot()` is the only AWS-facing
  seam; it adds zero new AWS API calls beyond what Milestones 1-3's
  `aws/networking.py`, `gateways.py`, `nat.py`, `security.py`,
  `nacls.py`, `enis.py`, `peering.py`, `endpoints.py`,
  `prefix_lists.py`, `loadbalancers.py`, `transit_gateway.py`, and
  `vpn.py` already provide — every VPC-scoped resource type is fetched
  region-wide in one call sequence (not once per VPC), filtered
  client-side when `vpc_ids` narrows scope, keeping the AWS call count
  constant regardless of how many VPCs are analyzed.
- **Deterministic, non-LLM core.** Every function under `diagnostics.*`
  is a pure function of its `NetworkSnapshot` input; the same snapshot
  always produces the same findings. Golden-tested reasoning/evidence
  (not just final labels) across `tests/unit/test_diagnostics_*.py`.
- **`confidence: "indeterminate"` is first-class**, never an omission —
  see [docs/architecture.md](docs/architecture.md#diagnostic-engine-milestone-4)
  and [docs/security.md](docs/security.md#deterministic-evidence-bound-diagnostics)
  for the full guarantee and why it exists.
- **Offline dry-run mode** (`diagnostics/offline.py`): `load_snapshot()`/
  `save_snapshot()` round-trip a `NetworkSnapshot` through JSON. A saved
  fixture and a live snapshot are interchangeable inputs to the same
  engine — there is no separate offline code path to drift out of sync.
  `fixtures/demo_network_snapshot.json` is a sanitized, hand-built
  snapshot (RFC 5737 documentation IPs, the standard fake AWS example
  account ID `123456789012`) that reproduces an accidental-SSH-exposure
  finding and a CIDR-overlap finding when analyzed, plus a working NAT-
  egress path resolution — proven by
  `tests/unit/test_diagnostics_offline.py`.
- `security.guardrails.READ_ONLY_PREFIXES` gained a `lookup_` prefix
  (`cloudtrail:LookupEvents` added to `READ_ONLY_ACTIONS`) — the one
  genuinely read-only operation this milestone calls that doesn't follow
  the describe/get/list/search convention, the same narrow-exception
  pattern `search_` used in Milestone 3.

## Fixes to Earlier Milestones

Found and fixed while building the routing engine's endpoint resolution
(the M4 spec's own guardrail against undocumented heuristics required
verifying this before relying on it):

**Route-target misclassification for Gateway VPC endpoints**
(`aws/networking.py`, present since Milestone 2). AWS reuses the
`GatewayId` route field a third way — for a Gateway-type VPC endpoint
(S3/DynamoDB), paired with a `DestinationPrefixListId` — previously
silently classified as a plain `"gateway"` (implying an internet
gateway) since only `"local"` and `vgw-*` were disambiguated. Verified
against moto's `DescribeRouteTables` output for a real Gateway endpoint
before fixing. Fixed to classify `vpce-*` as `"vpc_endpoint"`;
`aws/topology.py`'s `_IN_SCOPE_ROUTE_TARGET_TYPES` updated to match (the
endpoint node itself already existed independently of this
classification, so `aws_get_vpc_topology`'s node/edge output is
unchanged for accounts using Gateway endpoints — only the route evidence
string and the absence of a previously-incorrect `OUT_OF_SCOPE_TARGET`
warning change). Tests added in `test_networking.py` and
`test_topology.py`, documented in
[CHANGELOG.md](CHANGELOG.md#040---milestone-4---network-diagnostics-and-explainable-analysis)
under "Changed," not "Added," since it doesn't change what data this
server exposes — only route target classification and evidence-string
correctness.

(A second fix — stamping `redacted: true` on Direct Connect virtual
interfaces — was found and corrected during Milestone 3's own completion
work, before this milestone began, and is already part of the merged
Milestone 3 PR; it is not part of this milestone's diff and is not
re-claimed here.)

## Scenario Coverage

All 13 scenarios named in the milestone spec, each with a dedicated test:

| Scenario | Test |
|---|---|
| Allowed same-VPC traffic | `test_diagnostics_routing.py::test_same_vpc_allowed_traffic_resolves_to_local_route` |
| Blocked same-VPC traffic | `test_diagnostics_routing.py::test_blocked_same_vpc_traffic_no_route_to_destination` |
| Peering without return route | `test_diagnostics_routing.py::test_peering_without_return_route_leaves_analyzed_scope` (path-resolution view) + `test_diagnostics_consistency.py::test_peering_without_return_route_flagged` (proactive scan) |
| TGW propagation gaps | `test_diagnostics_consistency.py::test_orphaned_attachment_no_association_flagged` + `test_associated_but_not_propagated_attachment_flagged` |
| NAT egress | `test_diagnostics_routing.py::test_nat_egress_walks_from_private_subnet_through_nat_to_internet` |
| Public ALB | `test_diagnostics_exposure.py::test_public_alb_with_open_ingress_flagged` |
| Accidental SSH exposure | `test_diagnostics_exposure.py::test_accidental_ssh_exposure_is_proven_reachable` + `test_diagnostics_security.py::test_accidental_ssh_exposure_sg_allows_from_anywhere` |
| NACL ephemeral-port failure | `test_diagnostics_security.py::test_nacl_ephemeral_port_failure_breaks_return_leg` |
| IPv6 egress | `test_diagnostics_routing.py::test_ipv6_egress_via_egress_only_internet_gateway` |
| Overlapping CIDRs | `test_diagnostics_consistency.py::test_overlapping_vpc_cidrs_flagged` |
| Blackhole routes | `test_diagnostics_routing.py::test_blackhole_route_is_deterministically_blocked` |
| Partial permissions | `test_aws_snapshot.py::test_collect_network_snapshot_propagates_partial_result_warnings` |
| Unknown target types | `test_diagnostics_routing.py::test_unknown_target_type_is_indeterminate_not_silently_allowed_or_blocked` |

**Stale data**: not a separate scenario test — every `Finding.freshness`
carries the snapshot's `collected_at` timestamp (proven by
`test_diagnostics_routing.py::test_finding_freshness_matches_snapshot_collected_at`),
which is the mechanism a caller uses to judge staleness. The milestone
does not ask this engine to invent a staleness *threshold* (which would
be exactly the kind of undocumented heuristic its own guardrails
disallow) — only to expose freshness so staleness can be judged, which
it does on every single finding.

## False-Positive Safeguards

- Every rule that depends on data outside what's in the snapshot
  (an unresolved security-group reference, a prefix list without
  fetched entries, a peered/TGW-attached VPC outside collected scope)
  degrades to `confidence: "indeterminate"` plus an explicit
  `limitations` entry rather than guessing allow or deny — tested in
  `test_diagnostics_security.py::test_unresolvable_security_group_reference_is_indeterminate`,
  `test_diagnostics_routing.py::test_prefix_list_route_unresolved_downgrades_confidence`,
  and the `left_analyzed_scope`/`unresolved_target` routing tests.
- `aws_find_network_risks` reports informational "checked, nothing
  found" findings alongside real risks (never silently omitting a
  clean check, which would be indistinguishable from "not checked") —
  tested in `test_diagnostics_risks.py::test_find_network_risks_min_severity_filters_info_findings`.
- Exposure findings never claim reachability from a permissive rule
  alone — `test_diagnostics_exposure.py::test_permissive_sg_without_public_ip_is_latent_not_reachable`
  proves a wide-open security group without a public IP/route is
  reported as `low` severity ("latent"), not `critical`
  ("reachable"), which requires all of public IP + public route + SG +
  NACL to align.
- `aws_explain_network_path` never upgrades a skipped sub-evaluation to
  "passed" — `test_diagnostics_explain.py::test_no_eni_info_is_partially_evaluated_not_silently_allowed`
  and the MCP-level equivalent in `test_diagnostics_tools.py`.

## Test Results

```
$ ruff check .
All checks passed!

$ ruff format --check .
150 files already formatted

$ mypy src
Success: no issues found in 95 source files

$ pytest -m "not integration" --cov=src --cov-report=term-missing
290 passed, 5 deselected (integration, not run -- see below)
TOTAL coverage: 94% (3629 statements, 219 missed)

$ python -m build
Successfully built aws_cloudops_mcp-0.4.0.tar.gz and aws_cloudops_mcp-0.4.0-py3-none-any.whl
```

New test files (13 new test files totaling 86 test functions, plus 3
new test functions added to existing files -- 89 new test functions in
total across the diagnostics package and its AWS-facing wiring):

- `test_diagnostics_models.py`-equivalent coverage folded into each
  rule-module's own test file (no separate file needed — the rule
  catalog/`Finding` contract is exercised implicitly by every test below)
- `test_diagnostics_routing.py` (20 tests) — every named routing
  scenario plus source-by-IP resolution, prefix-list matching
  (resolved/unresolved), static-over-propagated tie-break, full
  within-snapshot peering and TGW resolution, IPv6
- `test_diagnostics_security.py` (7 tests) — SG stateful evaluation,
  unresolvable SG-reference indeterminate handling, all-four-legs NACL
  evaluation including the ephemeral-port failure scenario
- `test_diagnostics_exposure.py` (6 tests) — proven-reachable vs.
  latent-exposure distinction, public ALB, unknown-ENI indeterminate
- `test_diagnostics_consistency.py` (10 tests) — every whole-snapshot
  check, positive and negative cases
- `test_diagnostics_explain.py` (4 tests) — the routing+SG+NACL
  orchestration, including the partially-evaluated case
- `test_diagnostics_risks.py` (4 tests) — aggregation, `min_severity`
  filtering, deterministic ordering, zero-resources
- `test_diagnostics_offline.py` (5 tests) — the demo fixture and the
  save/load round trip, entirely without AWS
- `test_aws_snapshot.py` (6 tests) — the collector, including the
  partial-permissions/warning-propagation scenario
- `test_network_insights.py` (5 tests), `test_cloudtrail.py` (6 tests),
  `test_network_metrics.py` (5 tests), `test_network_health.py`
  (3 tests) — all Stubber-based where moto doesn't implement the
  operation (Reachability/Network Access Analyzer, CloudTrail), moto-
  based with real seeded data where it does (CloudWatch)
- `test_diagnostics_tools.py` (5 tests) — MCP-level `server.call_tool()`
  proofs for all three diagnostic tools, including the `min_severity`
  input-validation error path
- `test_no_mutation_calls.py`: added a third behavioral proof
  (`test_full_diagnostics_run_issues_only_read_only_operations`)
  spanning EC2 and exercising route resolution, risk scanning, and the
  health report together
- `test_guardrails.py`, `test_server.py`: extended for the `lookup_`
  prefix and the 8 new tool names

**Moto fidelity gaps encountered** (documented so a missing test isn't
mistaken for missing coverage): `SearchTransitGatewayRoutes` still
crashes on any non-null `MaxResults` (the same moto bug documented in
Milestone 3 — patched out in the collector's own tests, not re-tested
here); Reachability Analyzer and Network Access Analyzer operations
(`DescribeNetworkInsights*`, `GetNetworkInsightsAccessScopeAnalysisFindings`)
and `cloudtrail:LookupEvents` are not implemented in moto at all
(Python `NotImplementedError`) — all tested via `Stubber` against the
real service model instead. `cloudwatch:GetMetricStatistics` with a
300-second `Period` (this codebase's default) silently drops seeded
datapoints in moto even though the identical data returns correctly at
`Period=60` — a genuine moto aggregation-bucket bug; the one test that
needed to prove a real datapoint round-trips is Stubber-based, the
others (which only assert catalog/shape behavior, not aggregation
correctness) use moto directly.

## Observed Call Budget / Performance

`aws_explain_network_path`'s underlying `collect_network_snapshot()`
issues one call sequence per resource type region-wide regardless of VPC
count (proven by `test_aws_snapshot.py`'s deterministic collector tests);
route/security/NACL evaluation itself makes zero further AWS calls once
the snapshot is collected — the entire diagnostic reasoning step is
in-memory. `aws_get_network_health` with all three opt-in flags enabled
adds a bounded number of calls: up to 2 CloudWatch metrics per NAT
gateway (capped by `max_fanout_calls`), one `DescribeNetworkInsightsAnalyses`
call, and one capped `LookupEvents` call (≤50 results, ≤7-day window).

## Manual Validation

Real AWS credentials were not available in this environment (same
constraint as Milestones 1-3). A manual script drove the actual
`MCPServer.call_tool()` path end-to-end against moto-mocked AWS for all
three core diagnostic tools plus one network-insights tool, matching the
milestone's "offline MCP smoke calls" requirement. **All 4 scenarios
passed** (a 5th, `aws_list_network_insights_paths` against raw moto with
no Stubber, correctly returned a clean `INTERNAL_ERROR` envelope rather
than crashing — moto's `NotImplementedError` for that operation, exactly
the expected/documented gap, not a defect):

| Scenario | Result |
|---|---|
| `aws_explain_network_path` (same-VPC, no ENI info) | PASS — routable, partially_evaluated |
| `aws_find_network_risks` (accidentally-open SSH SG) | PASS — EXPOSE-001 finding returned |
| `aws_get_network_health` (default VPC, no flow logs) | PASS — vpcs_without_flow_logs populated |
| `aws_list_network_insights_paths` (Stubber-backed, separately in the persisted test suite) | PASS |

This is in addition to (not instead of) the 5 persisted `test_diagnostics_tools.py`
tests, which cover the same ground plus the `min_severity` validation
error path, as part of the regular `pytest` run above.

**Not performed** (same reasons as Milestones 1-3): running against a
real AWS account, or a Docker image build (Docker daemon not running in
this sandbox — Dockerfile unchanged from Milestone 1 and was not
re-validated by build here, though no dependency or entrypoint changes
were made that would affect it).

## Limitations

- `aws_explain_network_path`'s Transit Gateway hop resolution assumes
  the destination's TGW route table is included in the collected
  `transit_gateway_routes` — a snapshot collected without
  `include_transit_gateway: true` (the default) cannot resolve through a
  TGW hop and correctly reports `left_analyzed_scope` rather than
  guessing.
- The NACL evaluation's ephemeral-port assumption (1024-65535, the full
  IANA range) is disclosed on every relevant `Finding.assumptions` but
  is necessarily a generalization — actual client OS ephemeral ranges
  vary (e.g. Linux commonly uses 32768-60999).
- CloudWatch metric coverage in `aws_get_network_health` is a fixed,
  documented catalog (NAT gateway, Transit Gateway, VPN tunnel metrics)
  rather than open-ended metric discovery — deliberate, to keep the
  health check bounded and deterministic rather than an unbounded
  `ListMetrics` scan.
- CloudTrail lookup filters by `EventSource=ec2.amazonaws.com` (the
  AWS API's only practical single-attribute filter for this milestone's
  event set) then applies a client-side allowlist — a network-relevant
  event issued through a different `EventSource` (there are none in
  practice for the resource types this milestone covers) would not be
  found.
- Reachability Analyzer / Network Access Analyzer support is read-only
  result retrieval only, exactly as scoped — an account with no existing
  analyses will see empty lists from these tools, which is the correct,
  non-error result, not a sign the feature is broken.

## Files Created / Changed

```
New:
  src/aws_cloudops_mcp/diagnostics/{__init__,models,snapshot,routing,
    security,exposure,consistency,explain,risks,offline}.py
  src/aws_cloudops_mcp/aws/{snapshot,network_insights,cloudtrail,
    network_metrics,network_health}.py
  src/aws_cloudops_mcp/models/{network_insights,cloudtrail,
    network_metrics,network_health}.py
  src/aws_cloudops_mcp/tools/{diagnostics,network_insights}.py
  tests/unit/test_diagnostics_{routing,security,exposure,consistency,
    explain,risks,offline,tools}.py
  tests/unit/test_{aws_snapshot,network_insights,cloudtrail,
    network_metrics,network_health}.py
  fixtures/demo_network_snapshot.json
  MILESTONE4_STATUS.md

Changed:
  src/aws_cloudops_mcp/aws/networking.py (Gateway VPC endpoint route
    classification fix)
  src/aws_cloudops_mcp/aws/topology.py (in-scope route target types
    updated to match)
  src/aws_cloudops_mcp/security/guardrails.py (lookup_ prefix)
  src/aws_cloudops_mcp/server.py (register 2 new tool modules)
  tests/unit/test_{networking,topology,guardrails,server,
    no_mutation_calls}.py
  README.md, CHANGELOG.md, docs/{architecture,security,tools}.md,
  pyproject.toml (version bump 0.3.0 -> 0.4.0)
```

## Technical Decisions

- **`diagnostics/` as a genuinely separate package, not a submodule of
  `aws/`.** The milestone's own architecture requirement ("Implement
  graph/query modules independent of MCP transport and boto3") is
  enforced structurally: nothing under `diagnostics/` can import boto3
  without an explicit, reviewable new import statement, and the offline
  tests prove it by running the full engine with no AWS mocking
  whatsoever.
- **A single `NetworkSnapshot` bundle, not per-call live AWS reads
  scattered through the diagnostic logic.** Every rule reasons over one
  already-collected, immutable snapshot — this is what makes "the same
  input always produces the same output" true, what makes offline mode
  free (no separate code path), and what bounds the AWS call count to
  "one snapshot collection," regardless of how many rules subsequently
  run against it.
- **`confidence: "indeterminate"` as a value, not a separate return
  type.** Considered a distinct `Verdict` enum (allow/deny/indeterminate)
  separate from `Finding.confidence`, but collapsing indeterminate into
  the confidence field keeps every diagnostic output — "answer one
  question" and "scan everything" alike — the same shape, and makes "was
  this evaluated conclusively" a single field a caller always checks,
  rather than a type-shape distinction between tools.
- **Stateful/stateless asymmetry made structurally impossible to blur.**
  `evaluate_security_groups()` and `evaluate_network_acls()` are
  separate functions with deliberately different signatures (one
  direction-pair vs. four legs) rather than one parameterized function —
  a shared implementation would have made it easy to accidentally add a
  "return path" check to the stateful side by copy-paste.
- **`aws_find_network_risks` returns informational findings by default,
  filtered by an explicit `min_severity` rather than an implicit
  "risks only" default.** A caller who wants "what's wrong" passes
  `min_severity: "low"`; the default preserves the guardrail's own
  wording — a check that ran and found nothing must be visible, not
  indistinguishable from a check that never ran.

## Deferred Items

- Real-AWS validation and Docker build/run (same environment constraint
  as Milestones 1-3).
- CloudWatch metric catalog expansion beyond NAT Gateway/Transit
  Gateway/VPN (e.g. ELB-specific health metrics) — deliberately narrow
  for this milestone; extending it is additive and low-risk for a
  future milestone.
- Deeper Transit Gateway route resolution when the destination requires
  crossing more than one TGW route table (multi-TGW peering) — the
  current engine resolves one TGW hop per continuable step, which
  covers the common single-hub topology this milestone's scenarios
  exercise, but a TGW-peering-of-TGWs topology is not separately tested.

## Milestone 09 Handoff

(No Milestones 5-8 exist yet in this repository — those are separate,
independent per-cloud/service foundations per the overall program's
numbering; this repository's own roadmap continues from Milestone 4.)

- The `diagnostics.*` / `NetworkSnapshot` separation is the pattern any
  future analysis capability in this repository should follow: pure
  logic over a plain data bundle, with exactly one AWS-facing seam.
- `diagnostics.models.register_rule()`'s catalog is ready to grow —
  a future rule (e.g. a Network Firewall policy check, once that service
  is in scope) registers once and is automatically included in
  `rule_catalog()` without any other code needing to know about it.
- The offline fixture pattern (`diagnostics/offline.py` +
  `fixtures/demo_network_snapshot.json`) generalizes directly to a
  future common-schema/federation milestone: a `NetworkSnapshot` (or its
  eventual cross-cloud equivalent) is already a serializable, versionable
  artifact independent of any live API.
- `aws_get_network_health`'s bounded-metrics-catalog pattern
  (`KNOWN_NETWORK_METRICS`) is the template for adding CloudWatch-backed
  health signals for any future resource type without turning the tool
  into an unbounded metrics browser.

Ready for the next milestone: **YES**, once the deferred real-AWS/Docker
validation items above are picked up when an environment with
credentials and a running Docker daemon is available — nothing in this
milestone's own scope is unresolved.

---

## Recommended Git Commit

```
feat: complete milestone 4 AWS network diagnostics and explainable analysis
```
