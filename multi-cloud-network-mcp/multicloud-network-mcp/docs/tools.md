# Adapter tools

This contract does not itself expose MCP tools — it's a shapes-and-CLI
package. Each cloud repo exposes its own adapter surface using its
existing MCP interface, per
[ADR 0001](adr/0001-no-runtime-coupling.md)'s "narrowly scoped,
backward-compatible adapter additions" boundary. The recommended (not
mandated — a repo may choose the capability-declared-mapping form
instead) naming convention, one new tool per cloud repo:

| Tool | Purpose |
|---|---|
| `<provider>_get_contract_capabilities` | Returns one `ProviderCapabilityManifest` (`contracts/models/capability.py`) — which contract version this adapter targets, which resource types it can export, and via which tool. |
| `<provider>_export_normalized_topology` | Returns a `TopologyGraph` (`contracts/models/topology.py`) for one scope, built from that repo's own already-collected data, mapped into this contract's node/edge/URN shape. |

A repo with an existing diagnostics engine (Azure, GCP; AWS has its own
too) may additionally expose:

| Tool | Purpose |
|---|---|
| `<provider>_export_normalized_findings` | Returns `list[Finding]` (`contracts/models/diagnostics.py`), mapped from that repo's own rule catalog output. |

**What these tools must NOT do**: construct
`multicloud_network_mcp.contracts.models.*` instances directly (that
would be the runtime dependency ADR 0001 prohibits) — they build plain
dicts/light mapping code matching the contract's shape, verified against
this package's schemas and golden-example tests in that repo's own CI
(see `tests/contracts/test_golden_examples.py`'s docstring for the
copyable pattern).

**What every existing cloud-native tool keeps doing**: exactly what it
already does today, completely unchanged — the normalized-export tool
is additive, never a replacement.

## Adapter change notes, per cloud repo

See `MILESTONE9_STATUS.md` for what was actually added to each of the
three cloud repos in this milestone (a capability-manifest declaration
in each, plus which repos also got a normalized-topology export).
