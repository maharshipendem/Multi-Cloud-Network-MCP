# Development

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Validation

Run all of these before opening a PR:

```bash
ruff format --check .
ruff check .
mypy src
pytest tests/contracts
python -m multicloud_network_mcp.contracts validate contracts/examples
python -m build
```

No `docker build` step — this package is a library + CLI, not a
deployed MCP server, and has no Dockerfile.

## Changing a model

1. Edit the Pydantic model in `src/multicloud_network_mcp/contracts/models/*.py`.
   Follow `models/enums.py`'s docstring rule: a genuinely closed,
   contract-intrinsic field (`Provider`, `NodeKind`, `Completeness`,
   `IpVersion`) is strictly enum-typed; anything mapping provider data
   onto a vocabulary that might grow is plain `str`-typed.
2. Regenerate schemas — never hand-edit a file under
   `contracts/schemas/v1/`:
   ```bash
   python scripts/generate_schemas.py
   ```
3. Update any golden example under `contracts/examples/{aws,azure,gcp}/`
   the change affects, and re-validate:
   ```bash
   python -m multicloud_network_mcp.contracts validate contracts/examples
   ```
4. Add/update tests under `tests/contracts/` — see "Testing conventions"
   below for which file a given kind of change belongs in.
5. Decide the SemVer bump per `docs/versioning.md`'s table (additive →
   minor; anything else → major, with the deprecation process) and
   update `CHANGELOG.md`.

## Adding a new resource type

1. Add the model to `models/resources.py`, extending `CanonicalResource`.
   Add a docstring naming the AWS/Azure/GCP concepts it unifies and at
   least one genuine semantic gap, informed by real field names in each
   cloud repo's own `models/*.py` — never guessed.
2. Add the new `ResourceType` enum value in `models/enums.py`.
3. Re-export it from `models/__init__.py`'s `__all__`.
4. Add it to `scripts/generate_schemas.py`'s `_MODELS` list and to
   `validate.py`'s `_TYPE_TABLE`.
5. Regenerate schemas, add a golden example per provider (or document
   why a provider has no equivalent, per `docs/normalization.md`'s
   pattern), add round-trip + golden-example test coverage.
6. Document the mapping in `docs/normalization.md`.

## Testing conventions

- **`tests/contracts/test_urn.py`** — URN grammar round-trips,
  escaping, determinism, malformed-input rejection.
- **`tests/contracts/test_roundtrip.py`** — every model constructs and
  round-trips through JSON without loss.
- **`tests/contracts/test_extensions_preserved.py`** — the
  provider-namespaced `extensions` overflow bag survives a round trip
  and rejects an unrecognized provider namespace.
- **`tests/contracts/test_unknown_enum_forward_compat.py`** — a
  normalization-target field accepts a value this codebase has never
  heard of (simulating data from a newer contract minor); a structural
  enum field does not (by design — see `models/enums.py`).
- **`tests/contracts/test_absent_null_semantics.py`** — an omitted
  optional field and an explicit JSON `null` behave identically.
- **`tests/contracts/test_evidence_references.py`** — a `TopologyEdge`
  can never have zero evidence entries; `Finding`'s evidence
  (fact)/reasoning (inference) split stays structurally distinct.
- **`tests/contracts/test_partial_collections.py`** — `completeness`
  is enforced (raises, not just documented) to be `"partial"` whenever
  `warnings` is non-empty.
- **`tests/contracts/test_provider_semantic_mappings.py`** — the
  specific per-provider differences `docs/normalization.md` documents
  actually hold in the golden examples (e.g. AWS's two firewall
  mechanisms, GCP's missing route origin/state, Azure's `location` vs.
  `region`).
- **`tests/contracts/test_golden_examples.py`** — every example under
  `contracts/examples/` validates against both its schema and its
  model; designed to be copied into a cloud repo's own test suite
  pointed at that repo's own fixtures (see the file's own docstring).
- **`tests/contracts/test_compatibility_previous_minor.py`** —
  `negotiate()`'s major/minor compatibility rules, including the
  concrete "a consumer built against the previous minor still works"
  guarantee.
- **`tests/contracts/test_ipv4_ipv6.py`** — CIDR/IP normalization.

## Adding an adapter tool to a cloud repo

See `docs/tools.md` for the recommended tool-naming convention and
`docs/adr/0001-no-runtime-coupling.md` for the hard constraint: a cloud
repo's adapter tool never imports `multicloud_network_mcp` at runtime —
it builds plain dicts matching this contract's shape, verified against
this package's schemas/golden-example tests in that repo's own CI (as a
`dev`-only dependency there, if at all).
