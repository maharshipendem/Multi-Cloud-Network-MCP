# Versioning and compatibility policy

Three independent version axes exist in this contract — see
`src/multicloud_network_mcp/contracts/version.py`'s module docstring for
the short version; this document is the full policy.

## The three axes

| Axis | Constant | Bumps when |
|---|---|---|
| **Contract content** | `CONTRACT_VERSION` (SemVer) | Any change to models, schemas, or normalization tables |
| **URN grammar** | `URN_GRAMMAR_VERSION` (integer, embedded in every minted URN as `v<N>`) | The URN grammar itself changes shape (see `docs/urn_grammar.md`) |
| **Schema `$id` path** | `SCHEMA_ID_VERSION` (tracks `CONTRACT_VERSION`'s major) | A new contract major version — a new `schemas/v<N>/` directory is published *alongside* the old one, never replacing it |

These are deliberately independent. The URN grammar can (and should)
stay stable across many contract content releases — bumping it is a
much bigger, rarer event than adding an optional field to `Route`.

## SemVer policy for `CONTRACT_VERSION`

- **Patch** (`1.0.0` → `1.0.1`): a schema description/example/docstring
  fix that changes no type, no required field, no enum value. Never
  observable by a consumer parsing real data.
- **Minor** (`1.0.0` → `1.1.0`): strictly additive and non-breaking —
  a new optional field, a new resource type, a new normalization-target
  enum value (see `models/enums.py`'s docstring — these are the enums
  whose corresponding model fields are typed `str`, specifically so a
  new value doesn't break an older consumer's parsing), a new topology
  relationship string, a new golden example. An old consumer must still
  successfully parse data produced under a newer minor version of the
  *same* major — this is the compatibility guarantee
  `tests/contracts/test_compatibility_previous_minor.py` exists to keep
  honest, not just assert.
- **Major** (`1.x` → `2.0.0`): the *only* kind of change allowed to
  break an existing consumer — removing/renaming a field, changing a
  field's type, narrowing a previously-open value set, changing the URN
  grammar in a way that breaks `parse_urn()` for `v1` URNs. A major
  bump requires the deprecation process below, not just a version-number
  change.

## What counts as "breaking" (major-only) vs. "additive" (minor-safe)

| Change | Major or minor? |
|---|---|
| Add an optional field to an existing model | Minor |
| Add a new resource type / `ResourceType` value | Minor |
| Add a new value to a normalization-target enum (`RouteOrigin`, `Severity`, etc.) | Minor — the corresponding model field is `str`-typed for exactly this reason |
| Add a new value to a **structural** enum (`NodeKind`, `Provider`, `Completeness`, `IpVersion`) | **Major** — these fields ARE strictly enum-typed; a new member changes what a strict consumer must handle |
| Remove or rename any field | Major |
| Change a field's required-ness from optional to required | Major |
| Change a field's JSON type (e.g. `string` → `integer`) | Major |
| Narrow an already-open `str` field's practical value set by adding schema-level `enum`/`pattern` constraints where none existed | Major — this would break a currently-valid producer, not just a consumer |
| Change the URN grammar's field order, delimiter, or escaping rule | Major, and bumps `URN_GRAMMAR_VERSION` |
| Fix a schema `$id`, `description`, or example with no type/shape change | Patch |

## Deprecation process

1. A field/enum value/resource type slated for removal is marked
   deprecated in its model docstring and its JSON Schema `description`
   (prefixed `"[DEPRECATED as of contract vX.Y.Z]"`) in the very next
   minor release — it keeps working, just documented as going away.
2. It stays present, fully functional, for **at least one full minor
   version cycle** before a major version may remove it — i.e. something
   deprecated in `1.3.0` cannot be removed before `2.0.0`, and must have
   shipped in at least one released minor (`1.3.x` or later, pre-`2.0`)
   with the deprecation notice visible.
3. The major version that removes it documents the removal in
   `CHANGELOG.md` under a `### Removed` heading, cross-referencing the
   minor version the deprecation notice first appeared in.
4. `ProviderCapabilityManifest.min_supported_contract_version` (see
   `models/capability.py`) is how an adapter declares "I no longer
   support anything older than this" independently of what the *latest*
   contract version is — an adapter may keep supporting a deprecated
   field for longer than the contract formally requires, at its own
   discretion, by keeping its own `min_supported_contract_version` low.

## Schema `$id` and publication

Every generated schema file's `$id` is rooted at `SCHEMA_BASE_URI`
(`https://schemas.multicloud-network-mcp.dev`) plus
`/schemas/v<SCHEMA_ID_VERSION>/<name>.schema.json`. This URI is **not**
resolved over the network by anything in this package — `contracts
validate` and every test load schemas from the local
`contracts/schemas/v<N>/` files directly. The URI exists so each
schema has a globally stable identity for `$ref` resolution today, and
so a consumer who *does* want to publish these schemas at a real
resolvable URL later can do so without changing every `$id` in every
file — only the base URI constant.

A new major version's schemas are published as an entirely new
`schemas/v2/` directory, side by side with `schemas/v1/` — never
overwriting the old directory in place. A consumer pinned to a `v1`
`$id` keeps resolving to exactly the schema it was built against,
indefinitely.

## Version negotiation

`models/capability.py::negotiate()` is the one place compatibility is
actually decided, not ad-hoc string comparison at each call site:

- Different contract **major** version between consumer and manifest →
  always incompatible.
- Consumer's minor is older than the manifest's own
  `min_supported_contract_version` → incompatible (the adapter has
  already dropped support for data that old).
- Consumer's minor is newer than the manifest's `contract_version` →
  incompatible (the adapter hasn't been verified against fields the
  consumer might expect yet) — a real, intentionally strict rule: a
  consumer built against a newer minor should not silently assume an
  older adapter's data is complete for its purposes.
- Otherwise → compatible.

See `tests/contracts/test_compatibility_previous_minor.py` for the
concrete proof that a manifest declaring
`min_supported_contract_version="1.0.0"` under `contract_version="1.1.0"`
still negotiates successfully against a `1.0.0`-built consumer.
