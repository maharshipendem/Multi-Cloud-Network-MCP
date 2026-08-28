# azure-network-mcp

A production-quality, **read-only** [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that gives AI clients secure, controlled access to Azure network
infrastructure information.

> **This project is not affiliated with or endorsed by Microsoft.**

This is the Azure server in a planned multi-cloud family (AWS / Azure / GCP).
It is **fully independent**: it does not import from, depend on, or require
any other server in that family, including `aws-cloudops-mcp`. This
repository contains **only** Azure functionality — it reuses that sibling
project's *architectural patterns* (layered design, guardrails, response
envelope shape), never its code.

## Current milestone

**Milestone 6 — Azure Advanced Networking and Diagnostics (read-only).**
See [MILESTONE6_STATUS.md](MILESTONE6_STATUS.md) (and
[MILESTONE5_STATUS.md](MILESTONE5_STATUS.md) for the foundation this
builds on) for detailed status reports.

Implemented across both milestones:

- MCP server foundation (stdio transport, layered architecture)
- Azure Resource Manager (ARM) integration via `azure-mgmt-network`,
  `azure-mgmt-resource`, `azure-mgmt-subscription`,
  `azure-mgmt-privatedns`, `azure-mgmt-dnsresolver`, and
  `azure-mgmt-monitor`, with a centralized, per-subscription-caching
  client factory
- Credential resolution via `azure.identity.DefaultAzureCredential`
  (workload identity federation, managed identity, service principal env
  vars, or an `az login` session) — never a hard-coded or tool-supplied
  credential
- Optional subscription and tenant allowlists, enforced before any ARM
  client is constructed for a disallowed scope
- Structured JSON logging with per-request correlation IDs
- A read-only security guardrail layer, independent of Azure RBAC —
  every ARM SDK call is asserted read-only before it reaches Azure,
  including five narrow, explicitly-justified exceptions for the SDK's
  `begin_*`-prefixed effective-route-table/effective-NSG/BGP-peer-status/
  advertised-and-learned-routes computations (long-running reads, not
  mutations)
- Redaction by omission for every secret-shaped field Azure's SDK embeds
  directly on a list/get response (VPN pre-shared keys, ExpressRoute
  authorization/service keys) — statically enforced, not just documented
  — see [docs/security.md#redaction](docs/security.md#redaction)
- Two deterministic topology tools (`azure_get_vnet_topology`,
  `azure_get_hybrid_topology`) and a full diagnostics engine
  (`azure_explain_network_path`, `azure_find_network_risks`,
  `azure_get_network_health`) built on a five-rule catalog — see
  [docs/rule_catalog.md](docs/rule_catalog.md)
- 67 MCP tools total (19 from Milestone 5, 48 from Milestone 6) spanning
  identity, subscriptions, resource groups, core VNet networking, Virtual
  WAN/Virtual Hub/Route Server, VPN (vWAN and classic), ExpressRoute,
  Private Link, Private DNS/DNS Resolver, Azure Firewall, Network
  Watcher, Azure Monitor metrics, and the diagnostics engine — see
  [docs/tools.md](docs/tools.md) for the full list
- Capability metadata (`{"cloud": "azure", "read_only": true,
  "resource_types": [...]}`) on every tool for future multi-cloud
  federation discovery
- 300+ unit tests (95%+ line coverage), all offline — no moto-equivalent
  exists for Azure, so every ARM SDK operation-group method is
  monkeypatched directly (see [docs/development.md](docs/development.md))
  — plus an offline diagnostics dry-run mode
  ([fixtures/demo_hybrid_snapshot.json](fixtures/demo_hybrid_snapshot.json))
  and an opt-in integration test suite
- Docker image and docker-compose for local development

Not implemented (out of scope, by design — see
[docs/limitations.md](docs/limitations.md) for the reasoning behind
each): any infrastructure-**mutating** capability, AWS/GCP integration
or cross-cloud federation code, Network Watcher actions that create
persistent resources or run a new diagnostic (troubleshooting,
configuration diagnostics, packet capture), ExpressRoute circuit
authorizations, Connection Monitor time-series data, or Azure Firewall /
Front Door / CDN inventory beyond firewall and firewall-policy summaries.

## Architecture

```
AI / MCP Client
       |
       v
Azure Network MCP
       |
       +--- MCP Tool Layer          (src/azure_network_mcp/tools/)
       |
       +--- Security Guardrails     (src/azure_network_mcp/security/)
       |
       +--- ARM Service Layer       (src/azure_network_mcp/arm/)
       |
       +--- ARM Client Factory      (src/azure_network_mcp/arm/client_factory.py)
       |
       +--- Authentication          (src/azure_network_mcp/auth/)
       |
       v
Azure Resource Manager APIs
```

See [docs/architecture.md](docs/architecture.md) for the full explanation,
including how ARM's subscription-scoped (rather than region-scoped)
clients shape this design.

## Installation

Requires Python 3.12+.

```bash
git clone <this-repo-url> azure-network-mcp
cd azure-network-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Configuration is environment-variable driven via
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `azure-network-mcp` | Server name reported to MCP clients |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `AZURE_TENANT_ID` | _(unset)_ | Non-secret tenant identifier scoping `DefaultAzureCredential` |
| `AZURE_CLIENT_ID` | _(unset)_ | Non-secret client/managed-identity identifier |
| `AZURE_SUBSCRIPTION_ALLOWLIST` | _(unset)_ | Comma-separated subscription IDs this server may operate against |
| `AZURE_TENANT_ALLOWLIST` | _(unset)_ | Comma-separated tenant IDs this server may operate against |
| `AZURE_DEFAULT_SUBSCRIPTION_ID` | _(unset)_ | Subscription used when a tool call omits one |
| `AZURE_MAX_RETRIES` | `3` | Azure SDK retry attempts |
| `AZURE_CONNECTION_TIMEOUT` | `5.0` | Azure SDK connect timeout (seconds) |
| `AZURE_READ_TIMEOUT` | `20.0` | Azure SDK read timeout (seconds) |
| `MAX_PAGE_RESULTS` | `1000` | Safety cap on paginated results per tool call |
| `MAX_FANOUT_CALLS` | `50` | Safety cap on bounded per-item enrichment calls |
| `MAX_CONCURRENCY` | `10` | Reserved concurrency cap for future parallel collection |

Never put real credentials in `.env` or `.env.example` — every variable
above is a non-secret identifier, never a secret value.

## Authentication

azure-network-mcp never accepts or stores raw Azure credentials. It
resolves credentials exclusively through
`azure.identity.DefaultAzureCredential`'s standard resolution chain:

1. Environment variables for a service principal (`AZURE_CLIENT_ID`,
   `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`), or a certificate
   (`AZURE_CLIENT_CERTIFICATE_PATH`) — read directly by the Azure
   Identity SDK, never by this codebase
2. Workload identity federation (Kubernetes/AKS)
3. A managed identity attached to the compute environment (Azure VM, App
   Service, Container Apps) when deployed in Azure
4. An interactively-authenticated Azure CLI (`az login`),
   PowerShell, or Developer CLI session

`AZURE_TENANT_ID`/`AZURE_CLIENT_ID` in this server's own configuration
are non-secret identifiers that only narrow *which* identity/tenant
`DefaultAzureCredential` resolves against. See
[docs/security.md](docs/security.md) for the full credential-handling
model and the least-privilege custom role in
[azure-custom-role.json](azure-custom-role.json).

## Running locally

```bash
azure-network-mcp
# or
python -m azure_network_mcp.server
```

The server communicates over stdio, the standard transport for local MCP
clients.

### Example MCP client configuration

See [mcp-client-config.example.json](mcp-client-config.example.json), or
inline:

```json
{
  "mcpServers": {
    "azure-network-mcp": {
      "command": "azure-network-mcp",
      "env": {
        "AZURE_TENANT_ID": "<your-tenant-id>",
        "AZURE_DEFAULT_SUBSCRIPTION_ID": "<your-subscription-id>"
      }
    }
  }
}
```

## Running tests

```bash
pytest                 # unit tests only (default; no Azure credentials needed)
pytest -m integration  # integration tests against a REAL Azure subscription (opt-in)
pytest --cov=src --cov-report=term-missing
```

Azure has no moto-equivalent SDK mocking library — unit tests
monkeypatch the ARM SDK's operation-group methods directly and never
require real credentials. See [docs/development.md](docs/development.md).

## Docker

```bash
docker build -t azure-network-mcp .
docker run --rm -i \
  -e AZURE_TENANT_ID \
  -e AZURE_CLIENT_ID \
  -e AZURE_DEFAULT_SUBSCRIPTION_ID \
  azure-network-mcp
```

Or with `docker-compose` (reads an `az login` session from your local
`~/.azure`, mounted read-only):

```bash
docker compose run --rm azure-network-mcp
```

Credentials are always resolved at **runtime**, never baked into the
image. See [docs/development.md](docs/development.md) for details.

## Security model

- **Read-only by design.** This milestone cannot perform any Azure
  mutation. See [docs/security.md](docs/security.md) for the full threat
  model and defense-in-depth layers (MCP tool allowlist → application
  guardrails → Azure RBAC role → Azure Resource Manager API).
- **Azure RBAC is the authoritative boundary.** Application guardrails
  are defense-in-depth, not a substitute for a least-privilege RBAC role.
  Use the example role in
  [azure-custom-role.json](azure-custom-role.json).
- Credentials, client secrets, certificates, and access tokens are never
  logged.

## Roadmap

Future Azure MCP milestones (not implemented here, but the architecture
is designed to accommodate them without a rewrite): Azure Front Door and
CDN, DNS zone (public) visibility, deeper Network Watcher diagnostics
(configuration diagnostics, troubleshooting-result retrieval), Connection
Monitor time-series data, and richer firewall-policy rule detail beyond
per-collection summaries. A cross-cloud data contract unifying this
repository with `aws-cloudops-mcp` is explicitly deferred to a future
milestone (see [docs/limitations.md](docs/limitations.md)); a multi-cloud
federation/orchestration layer sitting above the AWS/Azure/GCP MCP
servers is planned as a separate project.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
