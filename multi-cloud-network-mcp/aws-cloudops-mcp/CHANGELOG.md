# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - Milestone 2 - VPC Topology

### Added

- Twelve new read-only MCP tools covering the broader VPC networking
  surface: `aws_list_internet_gateways`, `aws_list_egress_only_internet_gateways`,
  `aws_list_nat_gateways`, `aws_list_security_groups` (with rules from
  `ec2:DescribeSecurityGroupRules`), `aws_list_network_acls`,
  `aws_list_network_interfaces`, `aws_list_vpc_peering_connections`,
  `aws_list_managed_prefix_lists`, `aws_list_vpc_endpoints`,
  `aws_list_vpc_endpoint_services`, `aws_list_load_balancers` (ALB/NLB/GWLB
  + listeners + target groups + opt-in target health), and
  `aws_get_vpc_topology` (joins everything above into a typed node/edge
  graph for one VPC, with relationship/evidence per edge, orphan-reference
  handling for out-of-scope route/peering targets, partial-result
  warnings, and a tracked AWS API call count).
- `Settings.max_fanout_calls`: a new bounded-fan-out cap for the
  per-item enrichments AWS has no batch API for (VPC DNS attributes,
  managed prefix list entries, ELBv2 target health) -- opt-in via
  `include_*` tool parameters, capped, and reported via
  `CollectionWarning` rather than silently truncated.
- Capability metadata (`meta=`) attached to every tool, Milestone 1's
  included, so a future federation layer can discover resource types and
  confirm read-only status via `list_tools()` without importing this
  codebase.
- `aws/collection.py`: shared `observed_at` timestamping and an opt-in AWS
  API call counter used by `aws_get_vpc_topology`'s `api_call_count` and
  its recorded-call-budget test.

### Changed

- `Vpc`, `Subnet`, and `RouteTable` records now carry `account_id`,
  `observed_at`, and richer AWS-native fields (CIDR associations, IPv6,
  tenancy, DNS attributes on `Vpc`; AZ ID, IPv6 on `Subnet`; propagated-
  route flag, propagating VGWs on `RouteTable`). **Additive only** -- no
  existing field was renamed or removed, so Milestone 1 clients reading
  known fields by name are unaffected. See "Migration note" below.
- `aws_list_vpcs`/`aws_list_subnets`/`aws_list_route_tables` gained new
  optional input parameters (`vpc_ids`, `include_dns_attributes`,
  `subnet_ids`, `route_table_ids`); all default to preserving Milestone 1
  behavior exactly when omitted.
- Route `target_type` now distinguishes `gateway` (an actual internet
  gateway) from the new `virtual_private_gateway` value -- both share
  AWS's `GatewayId` route field, and treating them identically would have
  silently misclassified VPN-gateway routes as in-scope.
- Service-layer modules read configuration from `client_factory.settings`
  instead of the module-level `get_settings()` singleton, for per-call/
  per-test overridability (needed for the fan-out-cap tests above).

### Migration note

No schema-breaking change. Every new field on `Vpc`/`Subnet`/`RouteTable`
is additive with a default; every new tool input parameter is optional
with a default that reproduces Milestone 1 behavior. A client that reads
specific known fields by name (rather than doing strict/closed schema
validation) requires no code changes to keep working against this
release.

## [0.1.0] - Milestone 1 - Foundation

### Added

- MCP server foundation (stdio transport) with a layered architecture
  separating MCP transport, tool layer, security guardrails, AWS service
  layer, AWS client factory, and authentication.
- boto3-based AWS client factory with centralized region/retry/timeout
  configuration and session caching.
- AWS authentication supporting the standard boto3 credential chain
  (environment, shared config/credentials files, SSO profiles, IAM roles)
  plus optional cross-account `sts:AssumeRole` with automatic credential
  refresh.
- Structured JSON logging with per-request correlation IDs.
- Application-level read-only security guardrails, independent of IAM.
- Five MCP tools: `aws_get_caller_identity`, `aws_list_regions`,
  `aws_list_vpcs`, `aws_list_subnets`, `aws_list_route_tables`.
- Standard tool response envelope and custom exception hierarchy with
  AWS-error-to-client-error translation.
- Reusable AWS pagination helper and tag normalizer.
- Unit test suite (mocked AWS via moto) and an opt-in integration test
  suite marked `@pytest.mark.integration`.
- Dockerfile and docker-compose for local development.
- README, architecture/security/tools/development documentation, example
  least-privilege IAM policy, `.env.example`.

[Unreleased]: https://github.com/maharshipendem/Multi-Cloud-Network-MCP/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/maharshipendem/Multi-Cloud-Network-MCP/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/maharshipendem/Multi-Cloud-Network-MCP/releases/tag/v0.1.0
