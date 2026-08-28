# Milestone 9 — Versioned Multi-Cloud Network Contracts: Status Report

**Overall: PASS**

A new, independent repository, `multicloud-network-mcp`, defines
stable, vendor-neutral JSON Schema 2020-12 + typed Pydantic v2 contracts
that `aws-cloudops-mcp`, `azure-network-mcp`, and `gcp-network-mcp` can
normalize their own data into — with zero runtime coupling between any
of the four repos (see [ADR 0001](docs/adr/0001-no-runtime-coupling.md)).
Each of the three cloud repos received a narrowly-scoped, purely
additive adapter (two new MCP tools each); every existing tool in all
three repos is unchanged in behavior, wire shape, and IAM/RBAC
requirements. **Aggregation/federation is explicitly out of scope and
was not built** — see [Scope boundary](#scope-boundary).

## Files delivered

```
multicloud-network-mcp/
├── pyproject.toml (1.0.0), README.md, LICENSE, CHANGELOG.md, MILESTONE9_STATUS.md
├── scripts/
│   └── generate_schemas.py
├── docs/
│   ├── architecture.md, urn_grammar.md, normalization.md, versioning.md,
│   │   tools.md, development.md
│   └── adr/0001-no-runtime-coupling.md
├── contracts/examples/
│   ├── aws/     27 example files + NOTES.md
│   ├── azure/   26 example files + NOTES.md
│   └── gcp/     24 example files + NOTES.md
├── src/multicloud_network_mcp/
│   ├── __init__.py
│   └── contracts/
│       ├── version.py, urn.py, validate.py, __main__.py
│       ├── models/          enums.py, common.py, envelope.py, capability.py,
│       │                    resources.py (21 canonical types), topology.py,
│       │                    diagnostics.py, __init__.py (stable public API)
│       ├── normalization/    cidr.py, protocol.py, port_range.py, route.py,
│       │                    severity.py
│       └── schemas/v1/       27 generated JSON Schema 2020-12 files + index.json
└── tests/contracts/  12 test files, 132 tests

aws-cloudops-mcp/     + src/aws_cloudops_mcp/tools/contracts.py (new)
                      + tests/unit/test_contracts.py (new, 6 tests)
                      ~ src/aws_cloudops_mcp/server.py (registration only)
                      ~ tests/unit/test_server.py (tool-name-list/prefix additions)

azure-network-mcp/    + src/azure_network_mcp/tools/contracts.py (new)
                      + tests/unit/test_contracts.py (new, 12 tests)
                      ~ src/azure_network_mcp/server.py (registration only)

gcp-network-mcp/      + src/gcp_network_mcp/tools/contracts.py (new)
                      + tests/unit/test_contracts.py (new, 7 tests)
                      ~ src/gcp_network_mcp/server.py (registration only)
```

## Contract surface (21 resource types + 6 cross-cutting shapes)

`Network`, `Subnet`, `NetworkInterface`, `Address`, `RouteTable`,
`Route`, `FirewallRule`, `Gateway`, `TransitHub`, `Attachment`,
`Peering`, `VpnGateway`, `VpnTunnel`, `Interconnect`,
`InterconnectAttachment`, `DnsZone`, `DnsResolver`, `DnsRule`,
`LoadBalancer`, `Endpoint`, `ObservabilityReference`; plus
`TopologyGraph`/`TopologyNode`/`TopologyEdge`,
`Finding`/`PathExplanation`, `ResponseEnvelope`/`CollectionWarning`/
`PartialResultMetadata`/`PaginationMetadata`, and
`ProviderCapabilityManifest`. Full field-by-field design rationale in
each model's own docstring in `src/multicloud_network_mcp/contracts/models/resources.py`.

## URN grammar

`urn:mcnet:v1:<provider>:<scope>:<resource-type>:<native-id>` — stable,
deterministic, fully reversible percent-encoding. Full ABNF and three
real worked examples (one per provider) in
[docs/urn_grammar.md](docs/urn_grammar.md). Verified round-trip for
colons, percent signs, commas, equals signs, and non-ASCII characters
embedded in a native ID (`tests/contracts/test_urn.py`, 18 tests).

## Versioning and compatibility

`CONTRACT_VERSION="1.0.0"`, `URN_GRAMMAR_VERSION=1`,
`SCHEMA_ID_VERSION=1` — three independent axes, full policy in
[docs/versioning.md](docs/versioning.md). `models/capability.py::negotiate()`
implements the compatibility algorithm; `tests/contracts/test_compatibility_previous_minor.py`
proves a consumer built against a manifest's declared
`min_supported_contract_version` still negotiates successfully (7
tests, including the malformed-manifest and major-version-mismatch
cases).

## Normalization and documented semantic gaps

[docs/normalization.md](docs/normalization.md) is the single place
every unavoidable cross-provider difference this milestone found is
documented, each backed by a verified test against real golden example
data (`tests/contracts/test_provider_semantic_mappings.py`, 12 tests):

- **AWS is the only provider with two firewall mechanisms** (stateful
  Security Group rules, stateless NACL entries) — both map onto
  `FirewallRule`, distinguished by `stateful: bool`.
- **AWS has no first-class Elastic IP resource** — the `Address`
  example is synthesized from a `NatGatewayAddress`/`NetworkInterface.public_ip`,
  documented as such in `contracts/examples/aws/NOTES.md`.
- **GCP has no `Route.origin`/`Route.state` field at all** — the
  canonical fields normalize to `"unknown"` for GCP, never a guessed
  value; GCP's real strength (`priority`) is preserved instead.
- **GCP has no `DnsResolver`/`DnsRule`/`RouteTable`/`Gateway` equivalent** —
  zero examples for these on purpose, verified by test.
- **Azure has no generic `Gateway` resource** for the AWS/GCP-style
  implicit-internet-route concept — zero Azure `Gateway` examples,
  documented in `contracts/examples/azure/NOTES.md`.
- **Azure's `TransitHub` (Virtual Hub) is the one provider with its
  own hub-level CIDR** (`address_prefix`) — verified present in the
  Azure example.
- **`CloudScope.location` (Azure) vs. `region` (AWS/GCP)** are kept as
  distinct fields, never aliased onto one name — verified no Azure
  example ever populates `region`.
- **`VpnTunnel`/`Interconnect`/`InterconnectAttachment` never carry a
  secret-shaped field**, verified by a literal string-search across
  every golden example's full serialized JSON for
  `shared_secret`/`pre_shared_key`/`pairing_key`/`authorization_key`/
  `service_key` and every underscore/no-underscore/case variant. **This
  test caught and required a fix during this milestone's own final
  validation pass**: three example files' own explanatory `_note`/`notes`
  fields (documenting the redaction guarantee in prose) happened to
  contain the literal forbidden substrings themselves — not an actual
  leaked value, but close enough to the check's own trigger that the
  wording was tightened to avoid it, rather than weakening the test.

## Schemas

27 JSON Schema 2020-12 files (`src/multicloud_network_mcp/contracts/schemas/v1/`),
generated reproducibly by `scripts/generate_schemas.py` from the
Pydantic models — every file is marked `"$comment": "GENERATED --
do not hand-edit..."` and carries a stable `$id` rooted at
`SCHEMA_BASE_URI`. Verified structurally valid 2020-12 against the
`jsonschema` library's own `check_schema()` for all 27 files.

## Golden examples and conformance CLI

77 example files across all three providers (AWS 27, Azure 26, GCP
24), covering (of the 21 canonical resource types): **AWS 21/21**
(including both firewall-rule variants), **Azure 20/21** (only
`Gateway` genuinely has no Azure equivalent), **GCP 17/21** (missing
`route-table`, `gateway`, `dns-resolver`, `dns-rule` — all four genuine,
documented structural absences, not oversights) — plus one
`topology-graph`, `finding`, `path-explanation`, `response-envelope`,
and `provider-capability-manifest` example per provider.

```
python -m multicloud_network_mcp.contracts validate contracts/examples
-> 77/77 example(s) passed.
```

Every example validates against **both** its generated JSON Schema
**and** its typed Pydantic model — not just one — per
`contracts/validate.py`'s design (a file could pass one check and fail
the other if schema/model had drifted; both are required to pass).

## Cloud repo adapters — narrowly scoped, verified independently

Each cloud repo received exactly two new MCP tools
(`<provider>_get_contract_capabilities`,
`<provider>_export_normalized_topology`), built as plain dicts with
**zero runtime import of `multicloud_network_mcp`** (confirmed by grep
across all three `tools/contracts.py` files — every match is a
docstring/comment reference, never an actual `import` statement) and
zero cross-repo imports. Every existing tool in all three repos is
byte-for-byte unchanged.

| Repo | New tests | Full suite (before → after) | Tool count (before → after) |
|---|---|---|---|
| `aws-cloudops-mcp` | 6 | 296 passed (unchanged baseline + 6) | — |
| `azure-network-mcp` | 12 | 318 passed (unchanged baseline + 12) | — |
| `gcp-network-mcp` | 7 | 440 → 447 passed | 48 → 50 |

All three independently re-verified by direct `pytest`/`ruff`/`mypy`
invocation in this session (not just trusted from each build agent's
own report):

```
aws-cloudops-mcp:   ruff format --check . -> pass; ruff check . -> pass;
                    mypy src -> pass (96 files); pytest -> 296 passed, 5 deselected
azure-network-mcp:  pytest -> 318 passed, 5 deselected
gcp-network-mcp:    pytest -m "not integration" -> 447 passed, 2 deselected
```

Each adapter's `gcp_get_contract_capabilities`-equivalent tool is
honest, not aspirational: GCP's manifest explicitly marks most resource
types `exact_mapping=false` with a `notes` field explaining exactly
what's collected-but-not-yet-graph-joined, and omits `route-table`/
`dns-resolver`/`dns-rule` entirely since GCP has no such resource — no
adapter claims support it hasn't implemented.

## Tests and results — PASS

```
ruff format --check .   -> 45 files already formatted (PASS)
ruff check .             -> All checks passed (PASS)
mypy src                 -> Success: no issues found in 20 source files (PASS)
pytest tests/contracts   -> 132 passed (PASS)
python -m multicloud_network_mcp.contracts validate contracts/examples
                          -> 77/77 example(s) passed (PASS)
python -m build           -> multicloud_network_mcp-1.0.0.tar.gz and
                             multicloud_network_mcp-1.0.0-py3-none-any.whl built (PASS)
                          -> installed wheel independently verified in a fresh
                             Python 3.14 venv: imports, constructs a model,
                             and the schemas/v1/*.json files are bundled and
                             loadable via importlib.resources (PASS)
```

### Test coverage by required category (all present, per the milestone's
own list)

- **Every schema and example validated** — `test_golden_examples.py`.
- **Round-trip typed models** — `test_roundtrip.py` (29 tests, all 21
  resource types + topology/diagnostics/envelope/capability).
- **Stable URNs** — `test_urn.py` (18 tests).
- **IPv4/IPv6** — `test_ipv4_ipv6.py` (11 tests).
- **Extension preservation** — `test_extensions_preserved.py` (5 tests).
- **Unknown enum forward compatibility** — `test_unknown_enum_forward_compat.py`
  (8 tests, including a structural-vs-normalization-target contrast
  test and a schema-level `enum`-constraint-absence assertion).
- **Absent/null semantics** — `test_absent_null_semantics.py` (5 tests).
- **Path/finding evidence references** — `test_evidence_references.py`
  (6 tests, including the zero-evidence-rejected case).
- **Partial collections** — `test_partial_collections.py` (8 tests,
  including the `completeness`-vs-`warnings` construction-time
  enforcement this milestone added as a real `model_validator`, not
  just a documented convention).
- **Provider semantic mappings** — `test_provider_semantic_mappings.py`
  (12 tests).
- **Golden contract tests copyable into each repo** —
  `test_golden_examples.py` (its own module docstring documents exactly
  what to change to copy it into a cloud repo's CI).
- **Compatibility test proving the previous supported minor version
  still parses** — `test_compatibility_previous_minor.py` (7 tests).

## Real issues found and fixed during this milestone's own validation

1. **`PartialResultMetadata`/`TopologyGraph` claimed an enforcement that
   didn't exist.** Both models' docstrings originally stated
   `completeness` is `"partial"` whenever `warnings` is non-empty "never
   silently complete" — but no validator actually enforced this at
   first. Caught during my own re-read of the docstring against the
   code before writing tests for it. Fixed by adding a real
   `@model_validator(mode="after")` to both models that raises
   `ValueError` on the mismatch; `test_partial_collections.py`
   specifically tests the previously-silent "warnings set but
   completeness left at its default" mistake.
2. **Three golden example files' own explanatory notes tripped the
   secret-leak test.** `test_provider_semantic_mappings.py`'s
   literal-substring search across every VPN/Interconnect example's
   full serialized JSON (deliberately strict — checking for the
   *words*, not just structured field names, to catch a leak hiding
   anywhere) caught its own documentation: three `_note`/`notes` fields
   explaining the redaction guarantee in prose happened to contain the
   literal forbidden substrings. Not an actual secret — verified by
   reading each file — but real enough that the wording was tightened
   rather than the test loosened.

## Assumptions

- `google.cloud.dns`'s own lack of a visibility API means the GCP
  `DnsZone` example's `is_private`/`linked_network_urns` fields are
  documented best-effort defaults, not directly-observed facts — same
  honesty standard `gcp-network-mcp`'s own Milestone 8 established for
  this exact gap.
- Each adapter's `ResourceTypeSupport.export_tool` currently always
  points at `<provider>_export_normalized_topology` — no repo yet
  exposes a separate normalized-findings export tool (optional per this
  milestone's own spec; `supports_diagnostics=false` on all three
  manifests, honestly).
- The URN grammar's scope-key vocabulary (`tenant_id`/`account_id`/
  `subscription_id`/`project_id`/`region`/`location`/`zone`/
  `resource_group`) is closed by design — a fourth provider with a
  genuinely new scoping concept would need a URN grammar version bump,
  not a silent vocabulary extension.

## Scope boundary

**No aggregation/federation runtime was built, per this milestone's
explicit instruction not to.** `multicloud-network-mcp` defines shapes,
a validation CLI, and normalization tables only — nothing here calls
more than one cloud repo's MCP server, merges their results, or runs as
a standing process. See [ADR 0001](docs/adr/0001-no-runtime-coupling.md)
for the full reasoning and consequences of this boundary.

## Stop conditions checked — none triggered

- No common field was found to misrepresent a provider's real
  semantics — every genuine gap (AWS's dual firewall mechanism, GCP's
  missing route origin/state, Azure's missing generic Gateway, and
  more) is documented in `docs/normalization.md` rather than papered
  over with a false 1:1 mapping.
- No backward-compatibility decision required a major-version call —
  this is the initial `1.0.0` release; the compatibility policy and
  `negotiate()` machinery are built and tested, but no prior version
  exists yet to actually be compatible/incompatible against beyond the
  synthetic cases `test_compatibility_previous_minor.py` constructs.
- No cloud repo became runtime-coupled to this package or to each
  other — verified by grep across all three `tools/contracts.py` files
  finding zero `import multicloud_network_mcp`/`import aws_cloudops_mcp`/
  `import azure_network_mcp`/`import gcp_network_mcp` statements (only
  docstring/comment mentions), and zero new runtime dependencies added
  to any of the three cloud repos' `pyproject.toml` files.
- Federation/aggregation was not attempted, per this milestone's own
  instruction.

## Milestone 10 handoff

- This is the natural point to build the actual federation/aggregation
  layer this milestone deliberately deferred — it would consume the
  `<provider>_get_contract_capabilities`/`<provider>_export_normalized_topology`
  tools this milestone added across all three repos, entirely via MCP
  calls, never importing any cloud repo's internals (continuing ADR
  0001's boundary into whatever process hosts the aggregation itself).
- `ProviderCapabilityManifest.supports_diagnostics=false` on all three
  adapters today — a natural next increment is a
  `<provider>_export_normalized_findings` tool per repo, using the
  already-designed `Finding`/`PathExplanation` schemas this milestone
  built but no adapter yet populates from its own diagnostics engine.
- GCP's topology export currently never emits an `UNRESOLVED`-kind
  node (only `RESOURCE`/`EXTERNAL`) — `gcp_network_mcp`'s own topology
  builder doesn't yet track that distinction internally; the GCP golden
  example's `topology-graph` fixture demonstrates what a future,
  richer export *would* look like, ahead of the real collector
  supporting it.
- `docs/normalization.md`'s per-type gap table is the single best
  starting point for scoping which resource types a future federation
  layer can present with full confidence across all three clouds versus
  which will always need a "not available from every provider" caveat
  in its own UI/output.
