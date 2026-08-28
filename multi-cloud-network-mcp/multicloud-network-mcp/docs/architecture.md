# Architecture

## Layering

```
contracts/models/*.py    Typed Pydantic v2 models -- the canonical
                          source of truth. Every JSON Schema file under
                          contracts/schemas/v1/ is GENERATED from these,
                          never hand-edited (see below).

contracts/urn.py          The URN grammar every resource/topology-node
                          reference uses -- see docs/urn_grammar.md.

contracts/normalization/*.py  Pure functions + closed value tables for
                          CIDR/IP, protocol, port range, route origin/
                          state, and severity normalization -- what an
                          adapter calls to map a provider-native value
                          onto this contract's vocabulary. No provider
                          SDK imports, no network calls -- pure value
                          transforms only.

contracts/schemas/v1/*.json  Generated JSON Schema 2020-12 files, one
                          per model, produced by
                          scripts/generate_schemas.py. Every file's
                          first-8KB carries a "GENERATED -- do not
                          hand-edit" marker in its top-level
                          "$comment" field.

contracts/validate.py     The validation engine `python -m
                          multicloud_network_mcp.contracts validate`
                          drives -- loads every schema, validates every
                          example under a target directory against its
                          matching schema, and additionally round-trips
                          each example through the matching Pydantic
                          model (schema validity and typed-model
                          validity are BOTH checked, not just one).

contracts/examples/{aws,azure,gcp}/*.json   Golden examples: one real
                          resource's worth of data from each cloud,
                          hand-mapped into this contract's shape, that
                          `contracts validate` and
                          tests/contracts/test_golden_examples.py both
                          check against.
```

No module under `contracts/` imports a cloud SDK (`boto3`,
`azure-mgmt-*`, `google-cloud-*`) or anything from
`aws-cloudops-mcp`/`azure-network-mcp`/`gcp-network-mcp` — see
[ADR 0001](adr/0001-no-runtime-coupling.md) for why that boundary is a
hard rule, not just current practice.

## Why schemas are generated from models, not hand-authored

Pydantic v2's `model_json_schema()` targets JSON Schema Draft 2020-12 by
default (verified directly against the installed `pydantic==2.13.4` in
this repo's own venv — every generated schema's dialect matches what
this milestone requires with zero extra configuration). Given that,
hand-authoring ~25 JSON Schema files in parallel with ~25 Pydantic
models would only introduce a second copy of every field name/type/
constraint that could silently drift from the first. Instead:

1. The Pydantic models in `contracts/models/*.py` are the one place a
   field is defined.
2. `scripts/generate_schemas.py` walks every public model class and
   writes its `model_json_schema()` output to
   `contracts/schemas/v1/<name>.schema.json`, injecting `$id`
   (rooted at `SCHEMA_BASE_URI`, see `docs/versioning.md`), `$schema`
   (the 2020-12 dialect URI), and the generated-file marker.
3. `contracts validate` and every round-trip test check BOTH the raw
   JSON Schema validity of an example AND that the same example parses
   into the matching Pydantic model without error -- so "generated from
   models" is a property that's continuously verified, not just true at
   generation time.

This is the same "reproducible generation, clearly marked as generated"
requirement the milestone spec calls for, applied in the direction that
actually eliminates a source of drift (models → schemas) rather than the
other direction (schemas → models), since every consumer of this
contract that matters today (three Python MCP servers) needs typed
Python models as the primary artifact anyway.

## Extension preservation

Every model that represents a real provider resource extends
`ExtensibleModel` (`contracts/models/common.py`), carrying an
`extensions: dict[str, dict[str, Any]]` field namespaced by provider
slug. An adapter mapping raw provider data into this contract's shape
must put anything without a first-class canonical field into
`extensions[provider]`, never drop it — see
`docs/normalization.md`'s "never silently coerce unknown data"
guardrail and `tests/contracts/test_extensions_preserved.py`.

## Forward compatibility

See `contracts/models/enums.py`'s module docstring and
`docs/versioning.md` for the full rule: structural enums (`Provider`,
`NodeKind`, `Completeness`, `IpVersion`) are strictly validated;
normalization-target enums (`ResourceType`, `Severity`, `Confidence`,
route/firewall/protocol/state vocabularies) are carried on plain
`str`-typed model fields specifically so an older consumer parsing data
produced under a newer contract minor doesn't hard-fail on a value it
doesn't recognize yet — enforced at both the Pydantic layer (no strict
enum validation) and the JSON Schema layer (`type: string`, no `enum`
constraint) simultaneously.

## Topology: a formal `NodeKind` where every cloud repo today is informal

AWS's own topology tools represent "can't fully resolve this reference"
via an `external_endpoint` node-type string plus an undocumented
"orphan edge" convention (an edge whose target has no matching node);
Azure represents it via a free-form `node_type` string plus a
`CollectionWarning`; GCP represents it via a dedicated
`OUT_OF_SCOPE_TARGET` warning code with no node emitted at all. This
contract's `NodeKind` enum (`RESOURCE` / `EXTERNAL` / `UNRESOLVED`,
`contracts/models/enums.py`) formalizes all three into one explicit,
schema-enforced field — see `docs/normalization.md` for the full
per-provider mapping.

## Diagnostics: near-verbatim unification

All three cloud repos' own diagnostics engines already independently
converged on an essentially identical `Finding` shape (`rule_id`,
`rule_version`, `severity`, `confidence` with an explicit
`"indeterminate"` value, `summary`, `affected_resources`, `evidence`,
`reasoning`, `assumptions`, `limitations`, `freshness`, `remediation`).
`contracts/models/diagnostics.py::Finding` is the canonical version they
converge to — the one real structural change is that
`affected_resources`/`evidence[].source` reference this contract's
`urn` scheme instead of a raw provider-native ID string.
