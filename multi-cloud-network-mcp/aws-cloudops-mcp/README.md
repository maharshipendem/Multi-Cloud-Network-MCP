# aws-cloudops-mcp

A production-quality, **read-only** [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that gives AI clients secure, controlled access to AWS infrastructure
information — starting with identity, regions, and core VPC networking.

> **This project is not affiliated with or endorsed by Amazon Web Services.**

This is the AWS server in a planned multi-cloud family (AWS / Azure / GCP),
each independently deployable and usable on its own. This repository
contains **only** AWS functionality.

## Current milestone

**Milestone 4 — Network Diagnostics and Explainable Analysis (read-only).**
See [MILESTONE1_STATUS.md](MILESTONE1_STATUS.md),
[MILESTONE2_STATUS.md](MILESTONE2_STATUS.md),
[MILESTONE3_STATUS.md](MILESTONE3_STATUS.md), and
[MILESTONE4_STATUS.md](MILESTONE4_STATUS.md) for detailed status reports.

Implemented:

- MCP server foundation (stdio transport, layered architecture)
- boto3-based AWS integration with a centralized client factory
- Credential resolution via the standard boto3 chain (env vars, shared
  config/credentials files, SSO, instance/task IAM roles) plus optional
  cross-account `sts:AssumeRole`
- Structured JSON logging with per-request correlation IDs
- A read-only security guardrail layer, independent of IAM
- A deterministic, boto3-independent network diagnostics engine
  (`aws_cloudops_mcp.diagnostics`) -- route resolution, security group/
  NACL evaluation, internet exposure analysis, and consistency checks,
  each producing evidence-backed findings with explicit severity/
  confidence (including a first-class `"indeterminate"` value for
  incomplete data) rather than an LLM judgment call. Runs equally well
  against a live AWS snapshot or a saved offline fixture -- see
  [fixtures/demo_network_snapshot.json](fixtures/demo_network_snapshot.json).
- Fifty-three MCP tools (see [docs/tools.md](docs/tools.md)):
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
  - `aws_list_transit_gateways`, `aws_list_transit_gateway_attachments`,
    `aws_list_transit_gateway_route_tables`,
    `aws_search_transit_gateway_routes`
  - `aws_list_vpn_connections`, `aws_list_customer_gateways`,
    `aws_list_vpn_gateways`
  - `aws_list_direct_connect_connections`, `aws_list_direct_connect_lags`,
    `aws_list_direct_connect_virtual_interfaces`,
    `aws_list_direct_connect_gateways`
  - `aws_list_hosted_zones`, `aws_list_resource_record_sets`,
    `aws_list_resolver_endpoints`, `aws_list_resolver_rules`,
    `aws_list_resolver_rule_associations`,
    `aws_list_resolver_query_log_configs`,
    `aws_list_dns_firewall_rule_groups`,
    `aws_list_dns_firewall_rule_group_associations`
  - `aws_list_core_networks`, `aws_list_global_networks`,
    `aws_list_network_manager_sites`, `aws_list_network_manager_devices`,
    `aws_list_network_manager_links`, `aws_list_network_manager_connections`,
    `aws_list_transit_gateway_registrations`
  - `aws_list_flow_logs` — configuration/delivery metadata only, never log
    contents
  - `aws_get_hybrid_topology` — joins VPC/TGW/VPN/DX/DNS into a typed
    node/edge graph anchored on one Transit Gateway
  - `aws_explain_network_path` — deterministic route resolution (longest-
    prefix match across NAT/peering/TGW/gateway/endpoint/blackhole
    targets) combined with security group and NACL evaluation
  - `aws_find_network_risks` — CIDR overlap, orphaned/unpropagated
    Transit Gateway attachments, asymmetric peering routes, degraded
    resource states, and internet-exposed ENIs/load balancers
  - `aws_get_network_health` — degraded resource states, Flow Log
    coverage gaps, plus opt-in bounded CloudWatch metrics, Reachability
    Analyzer results, and recent CloudTrail network-configuration events
  - `aws_list_network_insights_paths`, `aws_list_network_insights_analyses`,
    `aws_list_network_insights_access_scopes`,
    `aws_list_network_insights_access_scope_analyses`,
    `aws_get_network_insights_access_scope_analysis_findings` — read-only
    Reachability Analyzer / Network Access Analyzer result retrieval
- Every AWS record carries `account_id`/`region`/`tags`/`observed_at`;
  optional per-item enrichment (DNS attributes, prefix list entries,
  target health, TGW route table associations/propagations, DNS resolver
  rule associations, Cloud WAN core network details/policy) is bounded and
  reported via warnings, never silently truncated
- VPN pre-shared keys and Direct Connect BGP authentication keys are never
  read from the AWS API response at all (redaction by omission, not
  scrubbing) — see [docs/security.md](docs/security.md)
- Capability metadata on every tool for future multi-cloud federation
  discovery
- Unit tests (mocked AWS via [moto](https://github.com/getmoto/moto) and
  `botocore.stub.Stubber`) and an opt-in integration test suite
- Docker image and docker-compose for local development

Not implemented yet (by design — see [Roadmap](#roadmap)): AWS Config,
cross-account discovery, network troubleshooting runbook automation,
Aviatrix integration, creating/starting any Reachability Analyzer or
Network Access Analyzer path/analysis, or any infrastructure-**mutating**
capability.

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
designed to accommodate them without a rewrite): Network Firewall, AWS
Config, AWS Organizations / multi-account discovery, deeper network
troubleshooting runbooks, and Aviatrix integration. A multi-cloud
federation/orchestration layer sitting above the AWS/Azure/GCP MCP
servers is planned as a separate project.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
