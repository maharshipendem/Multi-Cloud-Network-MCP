# ADR 0001: No runtime coupling between cloud repos or with this package

## Status

Accepted — Milestone 9.

## Context

`multicloud-network-mcp` defines shapes (JSON Schema + typed Pydantic
models) that `aws-cloudops-mcp`, `azure-network-mcp`, and
`gcp-network-mcp` can normalize their own data into. There are several
ways this could have been wired up:

1. Cloud repos import `multicloud_network_mcp` at runtime, constructing
   its Pydantic models directly inside their own tool code.
2. Cloud repos vendor/copy the contract's models into their own source
   tree, keeping them manually in sync.
3. A shared monorepo with relative-path imports across all four
   packages, so "the contract" and "the adapters" are really one
   deployable unit.
4. Cloud repos stay entirely independent, read-only MCP servers exactly
   as they are today; a separate normalized-export tool (or a
   capability-declared mapping) in each repo emits data *shaped like*
   this contract, validated against it only in that repo's own test
   suite (using this package as a `dev`-only test dependency, or not at
   all — see "adapter dependency direction" below) — never as a runtime
   dependency of the deployed MCP server.

## Decision

**Option 4.** No cloud repo depends on `multicloud_network_mcp` at
runtime, and no cloud repo depends on another cloud repo, at runtime or
otherwise. This package is never imported by a running MCP server
process. `multicloud-network-mcp` itself never imports a cloud SDK
(`boto3`, `azure-mgmt-*`, `google-cloud-*`) and never imports from
`aws-cloudops-mcp`/`azure-network-mcp`/`gcp-network-mcp`.

A cloud repo's adapter change (Milestone 9's "narrowly scoped,
backward-compatible adapter additions") is limited to:

- A new MCP tool (e.g. `gcp_get_contract_capabilities`,
  `gcp_export_normalized_topology`) whose *output shape* matches this
  contract's schemas, verified by that repo's own tests copying this
  package's golden contract tests (see
  `tests/contracts/test_golden_examples.py`'s docstring for exactly
  what "copyable" means here) — but the tool's implementation
  constructs plain dicts/its own lightweight mapping code, not
  `multicloud_network_mcp.contracts.models.*` instances.
- Optionally, `multicloud-network-mcp` as a `dev`/test-only dependency
  (never a runtime one) purely so a cloud repo's own CI can validate its
  adapter's output against the published JSON Schema files directly,
  without hand-copying schema text into that repo.

Every existing cloud-native tool remains available and completely
unchanged in behavior, wire shape, and IAM/RBAC requirements. The
normalized-export tool is additive.

## Why

- **Independent deployability.** Each cloud repo already ships as its
  own installable package with its own version, its own container
  image, its own release cadence (`gcp-network-mcp` is at `0.2.0`,
  `azure-network-mcp` at `0.2.0`, `aws-cloudops-mcp` at `0.4.0` — three
  genuinely independent timelines). A runtime dependency on this
  contracts package would force all three onto a shared release
  schedule for *this* package too, defeating the reason they're
  separate repos in the first place.
- **Blast radius.** A bug in `multicloud_network_mcp`'s model validation
  (a too-strict field, a bad default) should never be able to take down
  a live, deployed `gcp-network-mcp` server that has nothing to do with
  cross-cloud federation. If the dependency is test-only, the worst case
  is a broken CI check, not a broken production tool.
- **No accidental orchestration creep.** A shared runtime import is the
  first step toward a shared runtime *process* — a temptation this
  milestone's own guardrails explicitly forbid ("do not add
  orchestration behavior... do not build aggregation yet"). Keeping the
  coupling at "shape agreement, checked by tests" rather than "shared
  code path at request time" makes it structurally impossible for this
  package to accidentally grow into a federation runtime by accretion.
- **Matches how the three cloud repos already relate to each other.**
  Each already explicitly asserts, in its own test suite
  (`test_no_mutation_calls.py`-adjacent independence checks), that it
  imports nothing from either sibling repo. This ADR extends that same
  discipline to the new fourth repo rather than making it the one
  exception.
- **A contract doesn't need a shared runtime to be useful.** JSON Schema
  is deliberately a *data* format, not a code dependency — validating
  against it requires only a JSON Schema validator (any language, not
  just Python) and the schema file itself. Requiring Python +
  `multicloud_network_mcp` at runtime to consume the contract would
  quietly narrow "vendor-neutral" to "Python-only," which this milestone
  never asked for.

## Consequences

- A cloud repo's normalized-export tool duplicates a small amount of
  shape knowledge (field names, nesting) that already exists once in
  this package's Pydantic models — an intentional, small, and
  test-caught cost, not an oversight. `tests/contracts/test_golden_examples.py`'s
  copyable pattern is what keeps that duplication from silently drifting.
- This package cannot validate a cloud repo's *live* output at request
  time — only offline, via that repo's own test suite or a manually
  fetched fixture run through `contracts validate`. Runtime schema
  enforcement, if ever wanted, would be a deliberate, separately-decided
  future capability, not a side effect of this decision.
- Aggregation/federation (actually calling all three MCP servers and
  merging results into one cross-cloud view) is explicitly out of scope
  for this milestone and this ADR — see `MILESTONE9_STATUS.md`'s scope
  boundary. When that milestone happens, it will need its own decision
  about how much runtime coupling (if any) is acceptable for
  *aggregation specifically* — this ADR does not pre-decide that, it
  only settles that *this contracts package* stays decoupled.
