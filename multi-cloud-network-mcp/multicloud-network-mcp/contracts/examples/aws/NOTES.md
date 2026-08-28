# AWS golden examples -- notes

All 27 files under this directory were generated programmatically
(see the generation script referenced below) by constructing real
`multicloud_network_mcp.contracts.models` Pydantic instances and every
`urn` field via `multicloud_network_mcp.contracts.urn.build_urn()` --
never hand-typed -- then dumped to JSON. `python -m
multicloud_network_mcp.contracts validate contracts/examples/aws`
reports **27/27 PASS** (both JSON-Schema and Pydantic-model validation
for every file).

They all describe one internally-consistent, fictitious scenario: AWS
account `123456789012`, region `us-east-1`, a VPC `vpc-0abc123def456789`
("prod-vpc", `10.0.0.0/16`) with one public subnet
`subnet-0123456789abcdef0` (`us-east-1a`, `10.0.1.0/24`), an Internet
Gateway, a Transit Gateway attachment, a Site-to-Site VPN, a Direct
Connect private VIF, Route 53 public/resolver resources, an ALB, an S3
gateway VPC endpoint, and VPC Flow Logs -- plus a cross-account VPC
peering to a second (unresolvable) account `999988887777` used to
demonstrate the topology graph's `UNRESOLVED` node. All identifiers are
fake but AWS-ID-shaped; no real customer data.

## Coverage

All 21 canonical resource types have an AWS example, plus two
`firewall-rule` examples (stateful Security Group rule and stateless
NACL entry, per the milestone's explicit ask), plus one
`topology-graph`, one `finding`, one `path-explanation`, one
`response-envelope`, and one `provider-capability-manifest` -- 27 files
total. Nothing was skipped: the milestone brief called out that AWS
Route 53 Resolver's `ResolverEndpoint`/`ResolverRule` *do* give AWS a
real (if not identical) `dns-resolver`/`dns-rule` equivalent, so both
were built rather than omitted.

## Synthesized (not directly-collected) examples

- **`address.aws-synthesized-eip.json`** -- AWS has no first-class
  Elastic IP resource in its own model set (see
  `resources.py::Address`'s docstring). This record was synthesized
  from `network-interface.aws-web-eni.json`'s `extensions.aws.public_ip`
  field (`203.0.113.55`), matching the milestone's suggested approach of
  deriving an `Address` from a `NetworkInterface.public_ip`. `extensions.aws`
  on the file itself documents the synthesis (`synthesized_from`,
  `network_interface_id`, and a `note`). A real adapter would do this
  same synthesis at write-time, not read it from a dedicated "Elastic
  IP" AWS API call (there isn't one -- Elastic IPs are enumerated via
  `ec2:DescribeAddresses`, but the *first-class resource concept* this
  contract's `Address` model represents doesn't map 1:1 onto that API
  the way it does for Azure `PublicIpAddress`/GCP `Address`).

- **`endpoint.aws-s3-gateway-vpc-endpoint.json`** -- built from a
  Gateway-type `VpcEndpoint` (S3), which is a direct, lossless mapping.
  Not itself a synthesis, but note `subnet_urn` is intentionally `None`:
  a Gateway endpoint attaches to route tables, not subnets, unlike an
  Interface-type endpoint. AWS's *producer*-side `Endpoint` records
  (`endpoint_type="producer"`) were **not** built here -- per
  `resources.py::Endpoint`'s docstring, AWS has no distinct "VPC
  endpoint service" resource of its own; that side would need to be
  synthesized from a `LoadBalancer`'s endpoint-service configuration,
  which felt like a second, more speculative synthesis beyond this
  milestone's scope. Documenting the gap here rather than fabricating
  a producer-side example.

## Judgment calls mapping AWS values onto this contract's vocabularies

- **`route.aws-default-route-via-igw.json`**: raw AWS `Route.origin ==
  "CreateRoute"` normalizes to `RouteOrigin.STATIC` and raw
  `Route.state == "active"` normalizes to `RouteState.ACTIVE`, per
  `normalization/route.py`'s AWS table. Both the normalized and raw
  values are present (`origin`/`state` canonical fields, `extensions.aws.raw_origin`/`raw_state`
  for the untouched originals).

- **`vpn-tunnel.aws-tunnel-established.json`**: raw AWS tunnel
  `status == "UP"` maps onto this contract's `ObservedState.UP`
  (`"up"`) for the canonical `status` field; the untouched raw string
  `"UP"` is preserved verbatim in `native_status`, per
  `resources.py::VpnTunnel`'s docstring. `peer_gateway_urn` is `None`
  since the customer gateway is an on-premises device with no canonical
  `VpnGateway` record of its own in this collection -- `peer_ip`
  (`198.51.100.10`) is the only identifying fact captured for it. **No
  pre-shared-key or `CustomerGatewayConfiguration` field was populated
  anywhere** -- there is no such field on the canonical model, matching
  this contract's permanent `redacted=True` guarantee and AWS's own
  `aws-cloudops-mcp` model, which never reads that field either.

- **`vpn-gateway.aws-virtual-private-gateway.json`**: `is_ha=True` is a
  **best-effort inference**, not a directly-observed AWS field -- an AWS
  Virtual Private Gateway has no HA flag of its own. The inference is
  based on its attached VPN Connection provisioning two tunnels by
  default (see the paired `vpn-tunnel` example); documented in
  `extensions.aws.note` on the file itself, per
  `resources.py::VpnGateway`'s docstring instruction to preserve the
  raw facts an inference was based on.

- **`peering.aws-vpc-peering-cross-account.json`**: `allow_forwarded_traffic`,
  `exchange_subnet_routes`, `import_custom_routes`, and
  `export_custom_routes` are all left `None` (not `False`) -- AWS's
  `VpcPeeringConnection` model has no matching native fields; route
  exchange for an AWS peering is driven entirely by each side's route
  table contents, not a single boolean, so defaulting to `False` would
  have asserted something AWS never actually reports. `remote_network_urn`
  is `None` and `remote_native_id` is populated instead, since the
  accepter VPC (`vpc-0fedcba9876543210`) is in a cross-account scope
  this collection cannot resolve -- paired with the `UNRESOLVED` node
  for the same peer in `topology-graph.aws-vpc-topology.json`.

- **`interconnect-attachment.aws-private-virtual-interface.json`**:
  `router_urn` points at the Transit Gateway
  (`transit-hub.aws-transit-gateway.json`) this private VIF's Direct
  Connect Gateway is associated with. This is an adapter-layer judgment
  call, not a lossless 1:1 field read -- AWS's own `VirtualInterface`
  model has no single "router" field; the real chain is three separate
  AWS resources (VIF -> Direct Connect Gateway -> Transit Gateway
  association), and the intermediate Direct Connect Gateway has no
  canonical resource type of its own in this contract. Documented via
  `extensions.aws.note`.

- **`dns-zone.aws-public-hosted-zone.json`**: Route 53 is a global
  service, so this file's `CloudScope.region` is intentionally omitted
  (only `account_id` is set) to represent that -- unlike AWS's own
  `aws-cloudops-mcp` model, which keeps a `region` field populated with
  the bootstrap API endpoint region even for global resources. That
  AWS-specific bootstrap-region detail, if ever needed, belongs under
  `extensions.aws`, not this contract's `scope.region`, since populating
  `scope.region` here would misrepresent Route 53 as region-scoped.

- **`dns-resolver.aws-resolver-outbound-endpoint.json`** /
  **`dns-rule.aws-resolver-forwarding-rule.json`**: paired deliberately
  -- an AWS `FORWARD`-type `ResolverRule` (which is what
  `dns-rule.aws-resolver-forwarding-rule.json` represents) attaches to
  an **outbound** resolver endpoint, not an inbound one, so the paired
  `DnsResolver` example uses `direction="outbound"` rather than
  `"inbound"` to keep the two records a coherent, realistic pair.

- **`firewall-rule.aws-security-group-allow-ssh.json`**: deliberately
  modeled as *overly permissive* (`source_ranges=["0.0.0.0/0"]`, port
  22) so it could double as the subject of
  `finding.aws-exposed-ssh-security-group.json` and
  `path-explanation.aws-ssh-from-internet.json` -- both reference this
  exact rule's URN. `associated_resource_urns` points at the
  `NetworkInterface` this rule's security group is attached to; there is
  no canonical "security-group-as-a-rule-group" resource type in this
  contract (only individual `FirewallRule` records), so the native
  Security Group ID (`sg-0abc123def456789`) is preserved under
  `extensions.aws.security_group_id` rather than invented as a new
  first-class type.

- **`firewall-rule.aws-nacl-deny-inbound.json`**: `stateful=false`,
  matching the contract's explicit rule that this is `True` for every
  AWS Security Group rule and `False` only for an AWS NACL entry (per
  `resources.py::FirewallRule`'s docstring). `associated_resource_urns`
  points at the `Subnet` the NACL is associated with (NACLs attach to
  subnets, not individual interfaces).

## Topology graph (`topology-graph.aws-vpc-topology.json`)

6 nodes / 5 edges, `completeness="partial"` (required whenever
`warnings` is non-empty):

- 4 `RESOURCE` nodes: the VPC, its public subnet, the Internet Gateway,
  and the Virtual Private Gateway -- all reusing the exact same `urn`
  values as their standalone resource example files.
- 1 `EXTERNAL` node: the on-premises VPN peer IP (`198.51.100.10`,
  the same peer IP as `vpn-tunnel.aws-tunnel-established.json`'s
  `peer_ip`). Its `urn` is still minted through `build_urn()` (for
  grammar validity) using a free-form, non-`ResourceType`-enum slug
  (`"external"`) as the URN's resource-type segment, and an empty
  scope dict (no `CloudScope`) -- since `build_urn()`'s `resource_type`
  parameter accepts `ResourceType | str` specifically so a non-canonical
  reference like this can still be minted through the same grammar
  rather than hand-assembled.
- 1 `UNRESOLVED` node: the cross-account peered VPC
  (`vpc-0fedcba9876543210`, account `999988887777`), paired with a
  `CollectionWarning` (`code="cross_account_permission_denied"`)
  explaining that this collection's credentials have no cross-account
  read access to resolve the peer VPC's own attributes, even though the
  peering connection itself was observed from the local side.

## Not built

Nothing was skipped outright. Every one of the 21 canonical resource
types, both `FirewallRule` variants, and all 6 non-resource schema
types (`topology-graph`, `finding`, `path-explanation`,
`response-envelope`, `provider-capability-manifest`, plus the 21
resource types) have an AWS example under this directory.

The one deliberately-not-built variant is an AWS **producer-side**
`Endpoint` (`endpoint_type="producer"`) -- see "Synthesized" section
above for why.

## Version pins used

- `contract_version` / `min_supported_contract_version` in
  `provider-capability-manifest.aws-manifest.json`:
  `1.0.0` (`multicloud_network_mcp.contracts.version.CONTRACT_VERSION`
  at generation time).
- `urn_grammar_version`: `1`
  (`multicloud_network_mcp.contracts.version.URN_GRAMMAR_VERSION`).
- `adapter_version`: `0.4.0`, matching
  `aws-cloudops-mcp/pyproject.toml`'s `version` field at generation
  time (checked directly, not guessed).
