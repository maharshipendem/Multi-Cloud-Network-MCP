# gcp-network-mcp

A production-quality, **read-only** [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that gives AI clients secure, controlled access to Google Cloud
network infrastructure information.

> **This project is not affiliated with or endorsed by Google.**

This is the GCP server in a planned multi-cloud family (AWS / Azure /
GCP). It is **fully independent**: it does not import from, depend on,
or require any other server in that family, including `aws-cloudops-mcp`
or `azure-network-mcp`. This repository contains **only** GCP
functionality — it reuses those sibling projects' *architectural
patterns* (layered design, guardrails, response envelope shape), never
their code. A future Milestone 9 may unify these servers behind a common
contract; this milestone deliberately does not attempt that.

## What this is

`gcp-network-mcp` exposes 18 read-only MCP tools covering VPC networks,
subnetworks, routes, firewall rules and policies (hierarchical and
network-scoped), instance connectivity metadata, reserved addresses,
load balancing resources, Cloud Router/NAT, VPC Network Peering, Shared
VPC host/service relationships, and a deterministic cross-resource
topology graph. See [docs/tools.md](docs/tools.md) for the full list.

It **never** creates, modifies, or deletes anything. Every GCP client
library call this server makes is asserted read-only before it's
dispatched — see [docs/security.md](docs/security.md).

## Requirements

- Python 3.12+
- Google Cloud credentials the running identity can use via
  [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
  (a user's `gcloud auth application-default login` session, an attached
  service account, or workload identity federation)

## Installation

```bash
pip install -e ".[dev]"
```

## Authentication

This server **never accepts, stores, or reads a service account key
file's contents**. It resolves credentials exclusively through
Application Default Credentials (ADC):

- **Local development**: run `gcloud auth application-default login`
  once; no configuration needed.
- **Deployment**: attach a service account to the compute
  environment (Compute Engine, GKE, Cloud Run) and let workload identity
  supply credentials automatically, or set `GCP_IMPERSONATE_SERVICE_ACCOUNT`
  to have this server impersonate a specific service account from a
  broader base identity (the recommended alternative to a downloaded JSON
  key file).

See [docs/security.md#credential-handling](docs/security.md#credential-handling)
for the full model and why key files are discouraged.

## Configuration

Copy `.env.example` to `.env` and adjust. Every setting is a non-secret
identifier — see [.env.example](.env.example) for the full list
(`GCP_PROJECT_ALLOWLIST`, `GCP_DEFAULT_PROJECT_ID`,
`GCP_IMPERSONATE_SERVICE_ACCOUNT`, safety limits, etc.).

## Running

```bash
gcp-network-mcp
```

Runs the MCP server over stdio, the standard transport for local MCP
clients (Claude Desktop, Claude Code, etc.). Add it to your client's MCP
server configuration pointing at this command.

### Docker

```bash
docker build -t gcp-network-mcp:local .
docker compose run --rm gcp-network-mcp
```

The provided `docker-compose.yml` mounts your local `gcloud` ADC config
read-only for local development convenience only — see its comments for
why that mount is inappropriate in production.

## IAM

Grant the identity this server runs as a **least-privilege custom role**
— never `roles/editor` or `roles/owner`. See
[gcp-custom-role.yaml](gcp-custom-role.yaml) for a ready-to-use example
scoped to exactly the `*.get`/`*.list` permissions this milestone's tools
call.

## Development

```bash
ruff format --check .
ruff check .
mypy src
pytest -m "not integration" --cov=src --cov-report=term-missing
python -m build
docker build -t gcp-network-mcp:milestone-07 .
```

See [docs/development.md](docs/development.md) for the full contributor
workflow, and [docs/architecture.md](docs/architecture.md) for the
codebase's layering.

## Documentation

- [docs/architecture.md](docs/architecture.md) — layering, the
  `ClientFactory`/guardrail/pagination design
- [docs/security.md](docs/security.md) — credential handling,
  read-only enforcement, redaction, IAM
- [docs/tools.md](docs/tools.md) — every MCP tool, its parameters, and
  what it returns
- [docs/development.md](docs/development.md) — contributor workflow,
  testing conventions
- [CHANGELOG.md](CHANGELOG.md) — release history

## License

Apache License 2.0 — see [LICENSE](LICENSE).
