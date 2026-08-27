# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] - Milestone 4 - Network Diagnostics and Explainable Analysis

### Added

- A new, boto3/MCP-transport-independent diagnostics engine
  (`aws_cloudops_mcp.diagnostics`): deterministic route resolution
  (longest-prefix match across local/NAT/peering/TGW/gateway/endpoint/
  blackhole targets, AWS's static-over-propagated tie-break),
  security group (stateful, initiating-direction-only) and network ACL
  (stateless, all four legs including the ephemeral-port return path)
  evaluation, internet exposure analysis (distinguishing potential
  exposure from proven reachability), and consistency checks (CIDR
  overlap, orphaned/unpropagated Transit Gateway attachments,
  asymmetric VPC peering routes, degraded/failed resource states).
  Every conclusion is a `Finding` (rule ID + version, severity,
  confidence, summary, affected resources, evidence, reasoning steps,
  assumptions, limitations, freshness, advisory-only remediation);
  `confidence: "indeterminate"` is a first-class outcome when required
  evidence is missing, never an omission.
- `aws_explain_network_path`, `aws_find_network_risks`, and
  `aws_get_network_health` — the three tools built on the diagnostics
  engine, plus five read-only Reachability Analyzer / Network Access
  Analyzer result-retrieval tools
  (`aws_list_network_insights_paths`, `aws_list_network_insights_analyses`,
  `aws_list_network_insights_access_scopes`,
  `aws_list_network_insights_access_scope_analyses`,
  `aws_get_network_insights_access_scope_analysis_findings`). None of
  these create a path, analysis, scope, or scope analysis.
- `aws/snapshot.py::collect_network_snapshot` — the single seam bridging
  live AWS calls to the diagnostics engine, reusing every Milestone 1-3
  service-layer function with no new AWS API surface of its own.
- `diagnostics/offline.py` — an offline dry-run mode: load a saved,
  sanitized snapshot JSON file and run the exact same diagnostics
  functions against it, with zero AWS calls. See
  `fixtures/demo_network_snapshot.json` for a hand-built demo fixture
  reproducing several findings at once.
- Bounded, opt-in CloudWatch metric queries (`aws/network_metrics.py`,
  a fixed catalog of network-relevant metrics per resource type) and
  CloudTrail network-configuration event lookup (`aws/cloudtrail.py`,
  capped lookback window and result count, metadata-only -- never the
  raw event payload).
- `security.guardrails.READ_ONLY_PREFIXES` gained a `lookup_` prefix
  (with `cloudtrail:LookupEvents` added to `READ_ONLY_ACTIONS`) for the
  one genuinely read-only CloudTrail operation this milestone calls
  that doesn't follow the describe/get/list/search naming convention.

### Changed

- Fixed a route-target classification bug in `aws/networking.py`
  (present since Milestone 2): AWS reuses the `GatewayId` route field a
  third way, for Gateway-type VPC endpoints (`vpce-...`, paired with a
  `DestinationPrefixListId`) — previously misclassified as a plain
  `"gateway"` (implying an internet gateway). Now correctly classified
  as `"vpc_endpoint"`; `aws/topology.py`'s in-scope route target set
  updated to match, with no change to `aws_get_vpc_topology`'s node/edge
  output for accounts using Gateway endpoints (the endpoint node already
  existed independently of this classification).
- Nothing in Milestone 1-3's tool contracts changed otherwise. All other
  Milestone 4 additions are new tools and additive optional model
  fields.

## [0.3.0] - Milestone 3 - Transit, Hybrid Connectivity, and DNS

### Added

- Twenty-eight new read-only MCP tools covering transit, hybrid
  connectivity, and DNS: Transit Gateway (`aws_list_transit_gateways`,
  `aws_list_transit_gateway_attachments`,
  `aws_list_transit_gateway_route_tables` with opt-in
  associations/propagations, `aws_search_transit_gateway_routes`);
  Site-to-Site VPN (`aws_list_vpn_connections`, `aws_list_customer_gateways`,
  `aws_list_vpn_gateways`); Direct Connect
  (`aws_list_direct_connect_connections`, `aws_list_direct_connect_lags`,
  `aws_list_direct_connect_virtual_interfaces`,
  `aws_list_direct_connect_gateways` with opt-in associations); DNS
  (`aws_list_hosted_zones`, `aws_list_resource_record_sets`,
  `aws_list_resolver_endpoints`, `aws_list_resolver_rules` with opt-in
  associations, `aws_list_resolver_rule_associations`,
  `aws_list_resolver_query_log_configs`, `aws_list_dns_firewall_rule_groups`,
  `aws_list_dns_firewall_rule_group_associations`); Network Manager / Cloud
  WAN (`aws_list_core_networks` with opt-in details/policy,
  `aws_list_global_networks`, `aws_list_network_manager_sites`,
  `aws_list_network_manager_devices`, `aws_list_network_manager_links`,
  `aws_list_network_manager_connections`,
  `aws_list_transit_gateway_registrations`); Flow Logs
  (`aws_list_flow_logs`, configuration/delivery metadata only, never log
  contents); and `aws_get_hybrid_topology` — joins VPC, Transit Gateway,
  VPN, Direct Connect, and DNS into a typed node/edge graph anchored on
  one Transit Gateway, with an explicit `external_endpoint` node type for
  labeled non-AWS boundaries (e.g. a customer gateway's public IP),
  cross-account attachment warnings, and out-of-scope attachment-type
  warnings.
- `AwsResource` (the base model every record extends) gained four
  additive optional fields: `scope` (`"regional"`/`"global"`),
  `source_api`, `collection_completeness` (`"complete"`/`"partial"`), and
  `redacted` — all backward compatible with Milestone 1/2 consumers since
  every field is optional with a default.
- `security.guardrails.READ_ONLY_PREFIXES` gained a `search_` prefix
  (with `ec2:SearchTransitGatewayRoutes` added to `READ_ONLY_ACTIONS`)
  for the one genuinely read-only AWS operation in this milestone that
  doesn't follow the `describe_`/`get_`/`list_` naming convention.
- Redaction-by-omission for VPN pre-shared keys and Direct Connect BGP
  authentication keys: neither field is ever read from the raw AWS API
  response, and every affected record is stamped `redacted: true`. See
  [docs/security.md](docs/security.md#redaction-and-size-limits).

### Changed

- Nothing in Milestone 1/2's tool contracts changed. All Milestone 3
  additions are new tools and additive optional model fields.

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
