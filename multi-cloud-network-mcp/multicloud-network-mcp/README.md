# multicloud-network-mcp

Versioned, vendor-neutral network contracts shared by the
[`aws-cloudops-mcp`](../aws-cloudops-mcp), [`azure-network-mcp`](../azure-network-mcp),
and [`gcp-network-mcp`](../gcp-network-mcp) MCP servers.

This package defines JSON Schema 2020-12 (and corresponding typed
Pydantic models) for the cloud-agnostic shapes those three servers can
normalize their own provider-native data into — a stable URN scheme,
resource/topology/diagnostic contracts, a normalization specification,
and a version/compatibility policy — **without** making any of the three
cloud repos depend on each other, on this package's implementation
internals, or on a shared runtime process. See
[docs/architecture.md](docs/architecture.md) and
[docs/adr/0001-no-runtime-coupling.md](docs/adr/0001-no-runtime-coupling.md)
for why that boundary is enforced, not just a convention.

This repository does **not** implement cross-cloud aggregation/
federation — see the [Milestone 9 status report](MILESTONE9_STATUS.md)
for the explicit scope boundary.

## Quickstart

```bash
pip install -e ".[dev]"
python -m multicloud_network_mcp.contracts validate contracts/examples
pytest tests/contracts
```

## Layout

```
contracts/examples/{aws,azure,gcp}/   Golden examples from all three clouds
src/multicloud_network_mcp/contracts/
├── models/         Typed Pydantic models (the canonical source of truth)
├── normalization/  CIDR/protocol/port/route/severity normalization tables
├── schemas/v1/      Generated JSON Schema 2020-12 files (see scripts/generate_schemas.py)
├── urn.py           The canonical URN grammar (docs/urn_grammar.md)
├── validate.py       The engine behind `contracts validate`
└── __main__.py        The `python -m multicloud_network_mcp.contracts` CLI
docs/               Architecture, URN grammar, normalization spec, versioning policy, ADRs
tests/contracts/     Round-trip, URN, extension-preservation, forward-compat, golden-example tests
```

See [docs/tools.md](docs/tools.md) for what each cloud repo's adapter
exposes, and [docs/versioning.md](docs/versioning.md) for the
compatibility/deprecation policy.
