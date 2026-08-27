# aws-cloudops-mcp

A production-quality, **read-only** [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that gives AI clients secure, controlled access to AWS infrastructure
information — starting with identity, regions, and core VPC networking.

> **This project is not affiliated with or endorsed by Amazon Web Services.**

This is the AWS server in a planned multi-cloud family (AWS / Azure / GCP),
each independently deployable and usable on its own. This repository
contains **only** AWS functionality.

## Current milestone

**Milestone 2 — VPC Topology (read-only).** See
[MILESTONE1_STATUS.md](MILESTONE1_STATUS.md) and
[MILESTONE2_STATUS.md](MILESTONE2_STATUS.md) for detailed status reports.

Implemented:

- MCP server foundation (stdio transport, layered architecture)
- boto3-based AWS integration with a centralized client factory
- Credential resolution via the standard boto3 chain (env vars, shared
  config/credentials files, SSO, instance/task IAM roles) plus optional
  cross-account `sts:AssumeRole`
- Structured JSON logging with per-request correlation IDs
- A read-only security guardrail layer, independent of IAM
- Seventeen MCP tools (see [docs/tools.md](docs/tools.md)):
  - `aws_get_caller_identity`, `aws_list_regions`
  - `aws_list_vpcs`, `aws_list_subnets`, `aws_list_route_tables`
  - `aws_list_internet_gateways`, `aws_list_egress_only_internet_gateways`,
    `aws_list_nat_gateways`
  - `aws_list_security_groups`, `aws_list_network_acls`,
    `aws_list_network_interfaces`
  - `aws_list_vpc_peering_connections`, `aws_list_managed_prefix_lists`
  - `aws_list_vpc_endpoints`, `aws_list_vpc_endpoint_services`
  - `aws_list_load_balancers`
  - `aws_get_vpc_topology` — joins the above into a typed node/edge graph
    for one VPC
- Every AWS record carries `account_id`/`region`/`tags`/`observed_at`;
  optional per-item enrichment (DNS attributes, prefix list entries,
  target health) is bounded and reported via warnings, never silently
  truncated
- Capability metadata on every tool for future multi-cloud federation
  discovery
- Unit tests (mocked AWS via [moto](https://github.com/getmoto/moto)) and an
  opt-in integration test suite
- Docker image and docker-compose for local development

Not implemented yet (by design — see [Roadmap](#roadmap)): Transit Gateway,
Direct Connect, VPN, Route 53/DNS, CloudWatch/CloudTrail, cross-account
discovery, path/reachability analysis, Aviatrix integration, or any
infrastructure-**mutating** capability.

## Architecture

```
AI / MCP Client
       |
       v
AWS CloudOps MCP
       |
       +--- MCP Tool Layer          (src/aws_cloudops_mcp/tools/)
       |
       +--- Security Guardrails     (src/aws_cloudops_mcp/security/)
       |
       +--- AWS Service Layer       (src/aws_cloudops_mcp/aws/)
       |
       +--- AWS Client Factory      (src/aws_cloudops_mcp/aws/client_factory.py)
       |
       +--- Authentication          (src/aws_cloudops_mcp/auth/)
       |
       v
AWS APIs
```

See [docs/architecture.md](docs/architecture.md) for the full explanation,
including how this design accommodates multiple AWS accounts and regions in
later milestones.

## Installation

Requires Python 3.12+.

```bash
git clone <this-repo-url> aws-cloudops-mcp
cd aws-cloudops-mcp
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
| `APP_NAME` | `aws-cloudops-mcp` | Server name reported to MCP clients |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `AWS_PROFILE` | _(unset)_ | Named profile from `~/.aws/config` |
| `AWS_DEFAULT_REGION` | `us-east-1` | Default region for tools/bootstrap calls |
| `AWS_ROLE_ARN` | _(unset)_ | Role to assume for all AWS calls (cross-account) |
| `AWS_EXTERNAL_ID` | _(unset)_ | External ID for the AssumeRole call, if required |
| `AWS_SESSION_NAME` | `aws-cloudops-mcp` | STS session name for AssumeRole |
| `AWS_MAX_ATTEMPTS` | `3` | botocore retry attempts |
| `AWS_CONNECT_TIMEOUT` | `5` | botocore connect timeout (seconds) |
| `AWS_READ_TIMEOUT` | `20` | botocore read timeout (seconds) |
| `MAX_PAGE_RESULTS` | `1000` | Safety cap on paginated results per tool call |

Never put real credentials in `.env` or `.env.example`.

## Authentication

aws-cloudops-mcp never accepts or stores raw AWS credentials. It resolves
credentials through boto3's standard chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, etc.)
2. Shared credentials/config files (`~/.aws/credentials`, `~/.aws/config`),
   including SSO-backed profiles, selected via `AWS_PROFILE`
3. An IAM role attached to the compute environment (EC2 instance profile,
   ECS task role, Lambda execution role) when deployed in AWS

If `AWS_ROLE_ARN` is set, the server calls `sts:AssumeRole` using those base
credentials to obtain temporary, automatically-refreshed credentials scoped
to the target role — the foundation for future cross-account support. See
[docs/security.md](docs/security.md) for the full credential-handling model
and the example least-privilege IAM policy in [docs/tools.md](docs/tools.md).

## Running locally

```bash
aws-cloudops-mcp
# or
python -m aws_cloudops_mcp.server
```

The server communicates over stdio, the standard transport for local MCP
clients.

### Example MCP client configuration

For a client that reads a JSON server config (e.g. Claude Desktop-style
`mcp_servers` config):

```json
{
  "mcpServers": {
    "aws-cloudops-mcp": {
      "command": "aws-cloudops-mcp",
      "env": {
        "AWS_PROFILE": "my-readonly-profile",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

## Running tests

```bash
pytest                 # unit tests only (default; no AWS credentials needed)
pytest -m integration  # integration tests against a REAL AWS account (opt-in)
pytest --cov=aws_cloudops_mcp
```

Unit tests mock all AWS calls with [moto](https://github.com/getmoto/moto)
and never require real credentials.

## Docker

```bash
docker build -t aws-cloudops-mcp .
docker run --rm -i \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  -e AWS_DEFAULT_REGION=us-east-1 \
  aws-cloudops-mcp
```

Or with `docker-compose` (reads credentials from your local `~/.aws`, mounted
read-only):

```bash
docker compose run --rm aws-cloudops-mcp
```

Credentials are always passed at **runtime**, never baked into the image.
See [docs/development.md](docs/development.md) for details.

## Security model

- **Read-only by design.** Milestone 1 cannot perform any AWS mutation. See
  [docs/security.md](docs/security.md) for the full threat model and
  defense-in-depth layers (MCP tool allowlist → application guardrails →
  IAM read-only role → AWS API).
- **IAM is the authoritative boundary.** Application guardrails are
  defense-in-depth, not a substitute for least-privilege IAM. Use the
  example policy in [docs/tools.md](docs/tools.md).
- Credentials, access keys, secret keys, and session tokens are never
  logged.

## Roadmap

Future AWS MCP milestones (not implemented here, but the architecture is
designed to accommodate them without a rewrite): Transit Gateway (+ route
tables/attachments), Site-to-Site VPN, Direct Connect, Route 53 (+ private
hosted zones, Resolver), Network Firewall, CloudWatch, CloudTrail, AWS
Config, Reachability Analyzer, Flow Logs, AWS Organizations / multi-account
discovery, path analysis, network troubleshooting, and Aviatrix
integration. A multi-cloud federation/orchestration layer sitting above
the AWS/Azure/GCP MCP servers is planned as a separate project.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
