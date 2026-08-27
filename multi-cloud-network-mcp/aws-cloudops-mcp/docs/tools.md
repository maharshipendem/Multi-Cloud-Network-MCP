# MCP Tools

All tools return the same envelope (`aws_cloudops_mcp.models.responses.ToolResponse`):

```json
{
  "success": true,
  "tool": "aws_list_vpcs",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [],
  "metadata": { "count": 0, "request_id": "..." },
  "error": null
}
```

On failure, `success` is `false`, `data` is `null`, and `error` is populated
with a stable `type` and a client-safe `message` (see
[docs/security.md](security.md#error-handling) for the full error type
table).

---

## `aws_get_caller_identity`

**Purpose:** Return the AWS identity currently being used by the MCP
server.

**AWS API:** `sts:GetCallerIdentity`

**Required IAM permission:** `sts:GetCallerIdentity`

**Input:** none.

**Output (`data`):**

```json
{
  "account_id": "123456789012",
  "arn": "arn:aws:iam::123456789012:user/example",
  "user_id": "AIDAEXAMPLE"
}
```

**Example request:**

```json
{ "tool": "aws_get_caller_identity", "input": {} }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_get_caller_identity",
  "account_id": "123456789012",
  "region": null,
  "data": {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/example",
    "user_id": "AIDAEXAMPLE"
  },
  "metadata": { "request_id": "b1f7..." },
  "error": null
}
```

---

## `aws_list_regions`

**Purpose:** Return AWS regions accessible through EC2 DescribeRegions.

**AWS API:** `ec2:DescribeRegions`

**Required IAM permission:** `ec2:DescribeRegions`

**Input:**

```json
{ "region": "us-east-1" }
```

`region` is optional — it only selects which regional EC2 endpoint issues
the call (the result is the same regardless); it defaults to the server's
configured `AWS_DEFAULT_REGION`.

**Output (`data`):** list of

```json
{
  "region_name": "us-east-1",
  "endpoint": "ec2.us-east-1.amazonaws.com",
  "opt_in_status": "opt-in-not-required"
}
```

**Example request:**

```json
{ "tool": "aws_list_regions", "input": {} }
```

**Example response (truncated):**

```json
{
  "success": true,
  "tool": "aws_list_regions",
  "account_id": "123456789012",
  "region": null,
  "data": [
    { "region_name": "us-east-1", "endpoint": "ec2.us-east-1.amazonaws.com", "opt_in_status": "opt-in-not-required" },
    { "region_name": "eu-west-2", "endpoint": "ec2.eu-west-2.amazonaws.com", "opt_in_status": "opt-in-not-required" }
  ],
  "metadata": { "count": 2, "request_id": "..." },
  "error": null
}
```

---

## `aws_list_vpcs`

**Purpose:** List VPCs for a specified region.

**AWS API:** `ec2:DescribeVpcs` (paginated)

**Required IAM permission:** `ec2:DescribeVpcs`

**Input:**

```json
{ "region": "us-east-1" }
```

**Output (`data`):** list of

```json
{
  "vpc_id": "vpc-0123456789abcdef0",
  "cidr_block": "10.0.0.0/16",
  "state": "available",
  "is_default": false,
  "dhcp_options_id": "dopt-0123456789abcdef0",
  "tags": { "Name": "production-vpc", "Environment": "prod" },
  "region": "us-east-1"
}
```

**Example request:**

```json
{ "tool": "aws_list_vpcs", "input": { "region": "us-east-1" } }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_list_vpcs",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [
    {
      "vpc_id": "vpc-0123456789abcdef0",
      "cidr_block": "10.0.0.0/16",
      "state": "available",
      "is_default": false,
      "dhcp_options_id": "dopt-0123456789abcdef0",
      "tags": { "Name": "production-vpc" },
      "region": "us-east-1"
    }
  ],
  "metadata": { "count": 1, "request_id": "..." },
  "error": null
}
```

---

## `aws_list_subnets`

**Purpose:** List subnets for a region, optionally filtered by VPC.

**AWS API:** `ec2:DescribeSubnets` (paginated)

**Required IAM permission:** `ec2:DescribeSubnets`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` is optional; omit it to list subnets across the whole region.

**Output (`data`):** list of

```json
{
  "subnet_id": "subnet-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "cidr_block": "10.0.1.0/24",
  "availability_zone": "us-east-1a",
  "available_ip_address_count": 251,
  "map_public_ip_on_launch": true,
  "tags": { "Name": "public-subnet-a" },
  "region": "us-east-1"
}
```

**Example request:**

```json
{ "tool": "aws_list_subnets", "input": { "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" } }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_list_subnets",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [
    {
      "subnet_id": "subnet-0123456789abcdef0",
      "vpc_id": "vpc-0123456789abcdef0",
      "cidr_block": "10.0.1.0/24",
      "availability_zone": "us-east-1a",
      "available_ip_address_count": 251,
      "map_public_ip_on_launch": true,
      "tags": { "Name": "public-subnet-a" },
      "region": "us-east-1"
    }
  ],
  "metadata": { "count": 1, "request_id": "..." },
  "error": null
}
```

---

## `aws_list_route_tables`

**Purpose:** List route tables for a region, optionally filtered by VPC,
with normalized routes and associations for downstream troubleshooting
logic.

**AWS API:** `ec2:DescribeRouteTables` (paginated)

**Required IAM permission:** `ec2:DescribeRouteTables`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` is optional; omit it to list route tables across the whole region.

**Output (`data`):** list of

```json
{
  "route_table_id": "rtb-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "routes": [
    {
      "destination_cidr_block": "10.0.0.0/16",
      "destination_prefix_list_id": null,
      "target": "local",
      "target_type": null,
      "state": "active",
      "origin": "CreateRouteTable"
    },
    {
      "destination_cidr_block": "0.0.0.0/0",
      "destination_prefix_list_id": null,
      "target": "igw-0123456789abcdef0",
      "target_type": "gateway",
      "state": "active",
      "origin": "CreateRoute"
    }
  ],
  "associations": [
    {
      "route_table_association_id": "rtbassoc-0123456789abcdef0",
      "subnet_id": "subnet-0123456789abcdef0",
      "gateway_id": null,
      "main": false
    }
  ],
  "tags": { "Name": "public-rtb" },
  "region": "us-east-1"
}
```

`target_type` is one of `gateway` (an internet gateway; the target ID
starts with `igw-`), `virtual_private_gateway` (`vgw-` — out of this
milestone's scope, still surfaced as an edge/route but with no matching
resource tool yet), `nat_gateway`, `transit_gateway`,
`vpc_peering_connection`, `network_interface`,
`egress_only_internet_gateway`, `instance`, `local_gateway`,
`carrier_gateway`, `core_network`, or `null` for the implicit `local` route
(where `target` is the literal string `"local"`).

**Example request:**

```json
{ "tool": "aws_list_route_tables", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_internet_gateways`

**Purpose:** List internet gateways, optionally filtered by attached VPC.

**AWS API:** `ec2:DescribeInternetGateways` (paginated)

**Required IAM permission:** `ec2:DescribeInternetGateways`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` and `internet_gateway_ids` are both optional (`vpc_id` takes
precedence if both are given).

**Output (`data`):** list of

```json
{
  "internet_gateway_id": "igw-0123456789abcdef0",
  "owner_id": "123456789012",
  "attachments": [{ "vpc_id": "vpc-0123456789abcdef0", "state": "available" }],
  "tags": { "Name": "main-igw" },
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_egress_only_internet_gateways`

**Purpose:** List egress-only internet gateways (IPv6 outbound-only
gateways).

**AWS API:** `ec2:DescribeEgressOnlyInternetGateways` (paginated)

**Required IAM permission:** `ec2:DescribeEgressOnlyInternetGateways`

**Input:**

```json
{ "region": "us-east-1" }
```

`egress_only_internet_gateway_ids` is optional.

**Output (`data`):** list of

```json
{
  "egress_only_internet_gateway_id": "eigw-0123456789abcdef0",
  "attachments": [{ "vpc_id": "vpc-0123456789abcdef0", "state": "attached" }],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_nat_gateways`

**Purpose:** List NAT gateways, optionally filtered by VPC or subnet.
Includes recently deleted gateways (`state: "deleted"`) rather than hiding
them.

**AWS API:** `ec2:DescribeNatGateways` (paginated)

**Required IAM permission:** `ec2:DescribeNatGateways`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id`, `subnet_id`, and `nat_gateway_ids` are all optional.

**Output (`data`):** list of

```json
{
  "nat_gateway_id": "nat-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "subnet_id": "subnet-0123456789abcdef0",
  "state": "available",
  "connectivity_type": "public",
  "addresses": [
    { "allocation_id": "eipalloc-0123456789abcdef0", "public_ip": "203.0.113.5", "private_ip": "10.0.1.20", "is_primary": true, "status": "succeeded" }
  ],
  "failure_code": null,
  "failure_message": null,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_security_groups`

**Purpose:** List security groups and their rules, normalized by
direction/protocol/ports/peer/rule ID.

**AWS API:** `ec2:DescribeSecurityGroups` + `ec2:DescribeSecurityGroupRules`
(one call each, not per-group — rules are fetched once for exactly the
groups the first call returned)

**Required IAM permission:** `ec2:DescribeSecurityGroups`,
`ec2:DescribeSecurityGroupRules`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` and `security_group_ids` are both optional.

**Output (`data`):** list of

```json
{
  "group_id": "sg-0123456789abcdef0",
  "group_name": "web",
  "description": "web tier",
  "vpc_id": "vpc-0123456789abcdef0",
  "owner_id": "123456789012",
  "rules": [
    {
      "security_group_rule_id": "sgr-0123456789abcdef0",
      "security_group_id": "sg-0123456789abcdef0",
      "is_egress": false,
      "ip_protocol": "tcp",
      "from_port": 443,
      "to_port": 443,
      "peer": { "type": "ipv4", "value": "0.0.0.0/0" },
      "description": "public https",
      "account_id": "123456789012",
      "region": "us-east-1",
      "observed_at": "2026-08-27T18:00:00+00:00"
    }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

`peer.type` is one of `ipv4`, `ipv6`, `prefix_list`, or `security_group`
(with `referenced_group_id`/`referenced_vpc_id`/`referenced_owner_id`
populated for the last).

---

## `aws_list_network_acls`

**Purpose:** List network ACLs, entries sorted by (direction, rule number)
so evaluation order is explicit.

**AWS API:** `ec2:DescribeNetworkAcls` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkAcls`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` and `network_acl_ids` are both optional.

**Output (`data`):** list of

```json
{
  "network_acl_id": "acl-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "is_default": false,
  "entries": [
    {
      "rule_number": 100,
      "protocol": "6",
      "rule_action": "allow",
      "egress": false,
      "cidr_block": "0.0.0.0/0",
      "port_range_from": 443,
      "port_range_to": 443
    }
  ],
  "associations": [{ "network_acl_association_id": "aclassoc-0123456789abcdef0", "subnet_id": "subnet-0123456789abcdef0" }],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_network_interfaces`

**Purpose:** List elastic network interfaces (ENIs).

**AWS API:** `ec2:DescribeNetworkInterfaces` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkInterfaces`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id`, `subnet_id`, and `network_interface_ids` are all optional.

**Output (`data`):** list of

```json
{
  "network_interface_id": "eni-0123456789abcdef0",
  "subnet_id": "subnet-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "description": "primary network interface",
  "status": "in-use",
  "interface_type": "interface",
  "private_ip_address": "10.0.1.15",
  "private_ip_addresses": ["10.0.1.15"],
  "public_ip": null,
  "security_group_ids": ["sg-0123456789abcdef0"],
  "attachment": { "attachment_id": "eni-attach-0123456789abcdef0", "instance_id": "i-0123456789abcdef0", "device_index": 0, "status": "attached", "delete_on_termination": true },
  "requester_managed": false,
  "requester_id": null,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_vpc_peering_connections`

**Purpose:** List VPC peering connections, filterable by VPC on either the
requester or accepter side.

**AWS API:** `ec2:DescribeVpcPeeringConnections` (paginated; called twice
when `vpc_id` is given, once per side, and the results merged)

**Required IAM permission:** `ec2:DescribeVpcPeeringConnections`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

**Output (`data`):** list of

```json
{
  "vpc_peering_connection_id": "pcx-0123456789abcdef0",
  "status_code": "active",
  "status_message": "Active",
  "requester": { "vpc_id": "vpc-0123456789abcdef0", "owner_id": "123456789012", "region": "us-east-1", "cidr_blocks": ["10.0.0.0/16"] },
  "accepter": { "vpc_id": "vpc-0987654321fedcba0", "owner_id": "123456789012", "region": "us-east-1", "cidr_blocks": ["10.1.0.0/16"] },
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

---

## `aws_list_managed_prefix_lists`

**Purpose:** List customer-managed prefix lists, optionally with entries.

**AWS API:** `ec2:DescribeManagedPrefixLists` (paginated) +
`ec2:GetManagedPrefixListEntries` (opt-in, one call per prefix list, bounded
by `max_fanout_calls`)

**Required IAM permission:** `ec2:DescribeManagedPrefixLists`,
`ec2:GetManagedPrefixListEntries`

**Input:**

```json
{ "region": "us-east-1", "include_entries": true }
```

**Output (`data`):** list of

```json
{
  "prefix_list_id": "pl-0123456789abcdef0",
  "prefix_list_name": "office-networks",
  "state": "create-complete",
  "address_family": "IPv4",
  "max_entries": 10,
  "version": 1,
  "owner_id": "123456789012",
  "entries": [{ "cidr": "10.0.0.0/24", "description": "office" }],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

`entries` is `null` unless `include_entries: true` was passed. If the fan-out
cap is reached or an entry fetch fails, that prefix list's `entries` stays
`null` and a warning appears in `metadata.warnings`.

---

## `aws_list_vpc_endpoints`

**Purpose:** List VPC endpoints (Gateway/Interface/GatewayLoadBalancer).

**AWS API:** `ec2:DescribeVpcEndpoints` (paginated)

**Required IAM permission:** `ec2:DescribeVpcEndpoints`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0", "include_policies": false }
```

**Output (`data`):** list of

```json
{
  "vpc_endpoint_id": "vpce-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "service_name": "com.amazonaws.us-east-1.s3",
  "vpc_endpoint_type": "Gateway",
  "state": "available",
  "route_table_ids": ["rtb-0123456789abcdef0"],
  "subnet_ids": [],
  "security_group_ids": [],
  "network_interface_ids": [],
  "private_dns_enabled": null,
  "dns_entries": [],
  "policy_document": null,
  "policy_document_truncated": false,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

`policy_document` is `null` unless `include_policies: true` was passed, and
even then is truncated past 8000 characters
(`policy_document_truncated: true`) — see
[docs/security.md](security.md#redaction-and-size-limits).

---

## `aws_list_vpc_endpoint_services`

**Purpose:** List VPC endpoint services visible to this account/region
(AWS-provided services plus the account's own endpoint service
configurations).

**AWS API:** `ec2:DescribeVpcEndpointServices` (paginated)

**Required IAM permission:** `ec2:DescribeVpcEndpointServices`

**Input:**

```json
{ "region": "us-east-1" }
```

**Output (`data`):** list of

```json
{
  "service_name": "com.amazonaws.us-east-1.s3",
  "service_id": "vpce-svc-0123456789abcdef0",
  "service_type": ["Gateway"],
  "owner": "amazon",
  "availability_zones": ["us-east-1a", "us-east-1b"],
  "private_dns_name": null,
  "vpc_endpoint_policy_supported": true,
  "region": "us-east-1"
}
```

---

## `aws_list_load_balancers`

**Purpose:** List ALBs/NLBs/GWLBs joined with their listeners and target
groups, optionally with target health.

**AWS API:** `elbv2:DescribeLoadBalancers` (paginated),
`elbv2:DescribeTargetGroups` (paginated, account-wide, single call),
`elbv2:DescribeListeners` (one call per load balancer — no batch API
exists), `elbv2:DescribeTags` (batched, ≤20 ARNs per call),
`elbv2:DescribeTargetHealth` (opt-in, one call per target group, bounded by
`max_fanout_calls`)

**Required IAM permission:** `elasticloadbalancing:DescribeLoadBalancers`,
`elasticloadbalancing:DescribeListeners`,
`elasticloadbalancing:DescribeTargetGroups`,
`elasticloadbalancing:DescribeTags`,
`elasticloadbalancing:DescribeTargetHealth`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0", "include_target_health": false }
```

**Output (`data`):** list of

```json
{
  "load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/web/0123456789abcdef",
  "load_balancer_name": "web",
  "dns_name": "web-123456789.us-east-1.elb.amazonaws.com",
  "scheme": "internet-facing",
  "vpc_id": "vpc-0123456789abcdef0",
  "type": "application",
  "state": "active",
  "ip_address_type": "ipv4",
  "availability_zones": [{ "zone_name": "us-east-1a", "subnet_id": "subnet-0123456789abcdef0" }],
  "security_group_ids": ["sg-0123456789abcdef0"],
  "listeners": [
    { "listener_arn": "arn:...:listener/app/web/.../...", "load_balancer_arn": "arn:...:loadbalancer/app/web/...", "protocol": "HTTPS", "port": 443, "default_actions": [{ "type": "forward", "target_group_arn": "arn:...:targetgroup/web-tg/..." }] }
  ],
  "target_groups": [
    {
      "target_group_arn": "arn:...:targetgroup/web-tg/...",
      "target_group_name": "web-tg",
      "protocol": "HTTP",
      "port": 80,
      "vpc_id": "vpc-0123456789abcdef0",
      "target_type": "ip",
      "load_balancer_arns": ["arn:...:loadbalancer/app/web/..."],
      "targets": null,
      "tags": {},
      "account_id": "123456789012",
      "region": "us-east-1",
      "observed_at": "2026-08-27T18:00:00+00:00"
    }
  ],
  "tags": { "Name": "web" },
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00"
}
```

`targets` on each target group is `null` unless
`include_target_health: true` was passed.

---

## `aws_get_vpc_topology`

**Purpose:** Join every resource type above into one typed node/edge graph
for a single VPC — the deterministic, evidence-backed synthesis this
milestone builds toward. See [docs/architecture.md](architecture.md#topology-construction)
for how the graph is assembled and how out-of-scope references (a route to
a VPN gateway, a peering connection to an unrelated VPC) are handled.

**AWS API:** every read-only API listed above for the resource types in
scope, invoked only for resources that belong to (or directly attach to)
the requested VPC.

**Required IAM permission:** the union of every permission listed above.

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

Both fields are required — this tool has no "list everything" mode; it
always scopes to one VPC.

**Output (`data`):**

```json
{
  "vpc_id": "vpc-0123456789abcdef0",
  "region": "us-east-1",
  "nodes": [
    { "node_id": "vpc-0123456789abcdef0", "node_type": "vpc", "label": "prod-vpc", "vpc_id": "vpc-0123456789abcdef0", "region": "us-east-1", "tags": { "Name": "prod-vpc" } },
    { "node_id": "subnet-0123456789abcdef0", "node_type": "subnet", "label": "subnet-0123456789abcdef0", "vpc_id": "vpc-0123456789abcdef0", "region": "us-east-1", "tags": {} }
  ],
  "edges": [
    {
      "source_id": "vpc-0123456789abcdef0",
      "target_id": "subnet-0123456789abcdef0",
      "relationship": "contains",
      "evidence": "subnet subnet-0123456789abcdef0 VpcId=vpc-0123456789abcdef0"
    },
    {
      "source_id": "rtb-0123456789abcdef0",
      "target_id": "vgw-0123456789abcdef0",
      "relationship": "routes_to",
      "evidence": "route in rtb-0123456789abcdef0: 192.168.0.0/16 -> virtual_private_gateway:vgw-0123456789abcdef0 (state=active)"
    }
  ],
  "warnings": [
    {
      "resource_type": "route_target",
      "code": "OUT_OF_SCOPE_TARGET",
      "message": "Route table rtb-0123456789abcdef0 routes to virtual_private_gateway:vgw-0123456789abcdef0, a resource type outside this milestone's coverage -- the edge is recorded but no node exists for that target."
    }
  ],
  "api_call_count": 14
}
```

`node_type` is one of: `vpc`, `subnet`, `route_table`, `internet_gateway`,
`egress_only_internet_gateway`, `nat_gateway`, `security_group`,
`network_acl`, `network_interface`, `vpc_peering_connection`,
`vpc_endpoint`, `load_balancer`, `target_group`,
`managed_prefix_list` (only when referenced by a route). `relationship`
values include `contains`, `associated_with`, `main_route_table`,
`routes_to`, `local_route`, `attached_to`, `hosts`, `protected_by`,
`resides_in`, `member_of`, `peers_with_vpc`, `peered_with`,
`has_endpoint`, `deployed_in`, `references`. An edge whose `target_id`
does not match any `node_id` is an **orphan reference** — a real
relationship AWS reports that points outside this milestone's resource
coverage (e.g. a VPN gateway, or a peered VPC not requested). Orphan
references are never silently dropped; they always pair with a
`warnings` entry explaining why.

---

## `aws_list_transit_gateways`

**Purpose:** List Transit Gateways in a region.

**AWS API:** `ec2:describe_transit_gateways` (paginated)

**Required IAM permission:** `ec2:DescribeTransitGateways`

**Input:**

```json
{ "region": "us-east-1" }
```

`transit_gateway_ids` is optional.

**Output (`data`):** list of

```json
{
  "transit_gateway_id": "tgw-0123456789abcdef0",
  "transit_gateway_arn": "arn:aws:ec2:us-east-1:123456789012:transit-gateway/tgw-0123456789abcdef0",
  "owner_id": "123456789012",
  "description": "prod-hub",
  "state": "available",
  "options": {
    "amazon_side_asn": 64512,
    "auto_accept_shared_attachments": "disable",
    "default_route_table_association": "enable",
    "default_route_table_propagation": "enable",
    "dns_support": "enable",
    "vpn_ecmp_support": "enable",
    "multicast_support": "disable",
    "cidr_blocks": []
  },
  "tags": { "Name": "prod-hub" },
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeTransitGateways",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_transit_gateways", "input": { "region": "us-east-1" } }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_list_transit_gateways",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [
    {
      "transit_gateway_id": "tgw-0123456789abcdef0",
      "transit_gateway_arn": "arn:aws:ec2:us-east-1:123456789012:transit-gateway/tgw-0123456789abcdef0",
      "owner_id": "123456789012",
      "description": "prod-hub",
      "state": "available",
      "options": {
        "amazon_side_asn": 64512,
        "auto_accept_shared_attachments": "disable",
        "default_route_table_association": "enable",
        "default_route_table_propagation": "enable",
        "dns_support": "enable",
        "vpn_ecmp_support": "enable",
        "multicast_support": "disable",
        "cidr_blocks": []
      },
      "tags": { "Name": "prod-hub" },
      "account_id": "123456789012",
      "region": "us-east-1",
      "observed_at": "2026-08-27T18:00:00+00:00",
      "scope": "regional",
      "source_api": "ec2:DescribeTransitGateways",
      "collection_completeness": "complete",
      "redacted": false
    }
  ],
  "metadata": { "count": 1, "request_id": "..." },
  "error": null
}
```

---

## `aws_list_transit_gateway_attachments`

**Purpose:** List Transit Gateway attachments (VPC/VPN/Direct Connect
gateway/peering/Connect), optionally filtered by Transit Gateway or
resource type. Includes attachments owned by another account when visible
through this account's side of the Transit Gateway -- `resource_owner_id`
differing from the caller's own account ID signals a cross-account
attachment.

**AWS API:** `ec2:describe_transit_gateway_attachments` (paginated)

**Required IAM permission:** `ec2:DescribeTransitGatewayAttachments`

**Input:**

```json
{ "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0", "resource_type": "vpc" }
```

`transit_gateway_id` and `resource_type` (one of `vpc`, `vpn`,
`direct-connect-gateway`, `peering`, `connect`, `tgw-peering`) are both
optional.

**Output (`data`):** list of

```json
{
  "transit_gateway_attachment_id": "tgw-attach-0123456789abcdef0",
  "transit_gateway_id": "tgw-0123456789abcdef0",
  "transit_gateway_owner_id": "123456789012",
  "resource_owner_id": "123456789012",
  "resource_type": "vpc",
  "resource_id": "vpc-0123456789abcdef0",
  "state": "available",
  "association": { "transit_gateway_route_table_id": "tgw-rtb-0123456789abcdef0", "state": "associated" },
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeTransitGatewayAttachments",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_transit_gateway_attachments", "input": { "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_transit_gateway_route_tables`

**Purpose:** List Transit Gateway route tables, optionally with each
table's attachment associations and/or propagations included.

**AWS API:** `ec2:describe_transit_gateway_route_tables` (paginated) +
`ec2:get_transit_gateway_route_table_associations` /
`ec2:get_transit_gateway_route_table_propagations` (opt-in, one call each
per route table, sharing one fan-out budget, bounded by
`max_fanout_calls`)

**Required IAM permission:** `ec2:DescribeTransitGatewayRouteTables`,
`ec2:GetTransitGatewayRouteTableAssociations`,
`ec2:GetTransitGatewayRouteTablePropagations`

**Input:**

```json
{ "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0", "include_associations": true, "include_propagations": false }
```

`transit_gateway_id` and `transit_gateway_route_table_ids` are both
optional (`transit_gateway_id` takes precedence if both are given).
`include_associations`/`include_propagations` default to `false`.

**Output (`data`):** list of

```json
{
  "transit_gateway_route_table_id": "tgw-rtb-0123456789abcdef0",
  "transit_gateway_id": "tgw-0123456789abcdef0",
  "state": "available",
  "default_association_route_table": true,
  "default_propagation_route_table": true,
  "associations": [
    { "transit_gateway_attachment_id": "tgw-attach-0123456789abcdef0", "resource_id": "vpc-0123456789abcdef0", "resource_type": "vpc", "state": "associated" }
  ],
  "propagations": null,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeTransitGatewayRouteTables",
  "collection_completeness": "complete",
  "redacted": false
}
```

`associations`/`propagations` stay `null` unless the corresponding
`include_*` flag was passed. If the shared fan-out budget is exhausted
before every route table is enriched, the remaining route tables keep
`associations`/`propagations` as `null` and a `FANOUT_CAP_REACHED`
warning appears in `metadata.warnings` for each one skipped.

**Example request:**

```json
{ "tool": "aws_list_transit_gateway_route_tables", "input": { "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0", "include_associations": true } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_search_transit_gateway_routes`

**Purpose:** Search one Transit Gateway route table's routes by exact-match
destination CIDR and/or route type (static/propagated).

**AWS API:** `ec2:search_transit_gateway_routes`

**Required IAM permission:** `ec2:SearchTransitGatewayRoutes`

**Input:**

```json
{ "region": "us-east-1", "transit_gateway_route_table_id": "tgw-rtb-0123456789abcdef0", "destination_cidr_block": "10.1.0.0/16", "route_search_type": null, "max_results": 100 }
```

`destination_cidr_block` and `route_search_type` (`"static"` or
`"propagated"`) are both optional; if neither is given, the underlying AWS
call is filtered to `type in (static, propagated)` so it still returns
every real route rather than requiring the caller to supply a filter. AWS
itself constrains `MaxResults` to `[5, 1000]` on the wire; `max_results`
is clamped into that range for the actual AWS call, but the tool still
slices its response down to (and never exceeds) whatever smaller
`max_results` the caller asked for -- so passing `max_results: 1` returns
at most one route even though AWS was asked for 5.

**Output (`data`):** list of

```json
{
  "destination_cidr_block": "10.1.0.0/16",
  "route_type": "propagated",
  "state": "active",
  "attachments": [
    { "transit_gateway_attachment_id": "tgw-attach-0123456789abcdef0", "resource_id": "vpc-0123456789abcdef0", "resource_type": "vpc" }
  ]
}
```

Note these records do not carry `account_id`/`region`/`tags`/`observed_at`
-- unlike most list tools in this file, `TransitGatewayRoute` is a plain
route record (like the nested `routes` entries under
`aws_list_route_tables`), not a top-level `AwsResource`.

**Example request:**

```json
{ "tool": "aws_search_transit_gateway_routes", "input": { "region": "us-east-1", "transit_gateway_route_table_id": "tgw-rtb-0123456789abcdef0", "destination_cidr_block": "10.1.0.0/16" } }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_search_transit_gateway_routes",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [
    {
      "destination_cidr_block": "10.1.0.0/16",
      "route_type": "propagated",
      "state": "active",
      "attachments": [
        { "transit_gateway_attachment_id": "tgw-attach-0123456789abcdef0", "resource_id": "vpc-0123456789abcdef0", "resource_type": "vpc" }
      ]
    }
  ],
  "metadata": { "count": 1, "request_id": "..." },
  "error": null
}
```

---

## `aws_list_vpn_connections`

**Purpose:** List Site-to-Site VPN connections, including per-tunnel
telemetry and static routes.

**Security note:** this tool never returns the IKE pre-shared key. AWS's
raw `DescribeVpnConnections` response embeds the pre-shared key (and
other vendor-specific detail) inside a `CustomerGatewayConfiguration`
XML/JSON blob; that field is never read from the AWS response by this
codebase -- there is no code path by which it could reach a normalized
record, let alone this tool's output. `redacted` is always `true` on
every record this tool returns, documenting that omission explicitly
rather than leaving a client to assume the record is a complete
passthrough of the AWS response. See
[docs/security.md](security.md#secrets).

**AWS API:** `ec2:describe_vpn_connections` (not paginated by AWS --
returns everything in one call)

**Required IAM permission:** `ec2:DescribeVpnConnections`

**Input:**

```json
{ "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0" }
```

`vpn_connection_ids` and `transit_gateway_id` are both optional.

**Output (`data`):** list of

```json
{
  "vpn_connection_id": "vpn-0123456789abcdef0",
  "state": "available",
  "vpn_type": "ipsec.1",
  "category": "VPN",
  "customer_gateway_id": "cgw-0123456789abcdef0",
  "vpn_gateway_id": null,
  "transit_gateway_id": "tgw-0123456789abcdef0",
  "gateway_association_state": "associated",
  "options": {
    "static_routes_only": false,
    "tunnel_inside_ip_version": "ipv4",
    "enable_acceleration": false,
    "local_ipv4_network_cidr": "0.0.0.0/0",
    "remote_ipv4_network_cidr": "0.0.0.0/0"
  },
  "static_routes": [],
  "tunnels": [
    {
      "outside_ip_address": "203.0.113.10",
      "status": "UP",
      "status_message": "",
      "last_status_change": "2026-08-20T10:00:00+00:00",
      "accepted_route_count": 2,
      "options": { "tunnel_inside_cidr": "169.254.10.0/30", "dpd_timeout_seconds": 30, "ike_versions": ["ikev2"] }
    }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeVpnConnections",
  "collection_completeness": "complete",
  "redacted": true
}
```

Note there is no `customer_gateway_configuration` field, no
`pre_shared_key` field, and no field anywhere in this model that could
carry either -- this is an intentional, permanent omission (see
[docs/security.md](security.md#secrets)), not something a future
`include_*` flag will ever add.

**Example request:**

```json
{ "tool": "aws_list_vpn_connections", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_customer_gateways`

**Purpose:** List customer gateways -- the on-premises side of a
Site-to-Site VPN.

**AWS API:** `ec2:describe_customer_gateways`

**Required IAM permission:** `ec2:DescribeCustomerGateways`

**Input:**

```json
{ "region": "us-east-1" }
```

`customer_gateway_ids` is optional.

**Output (`data`):** list of

```json
{
  "customer_gateway_id": "cgw-0123456789abcdef0",
  "state": "available",
  "gateway_type": "ipsec.1",
  "ip_address": "203.0.113.99",
  "bgp_asn": "65000",
  "device_name": "branch-office-router",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeCustomerGateways",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_customer_gateways", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_vpn_gateways`

**Purpose:** List virtual private gateways -- the AWS side of a classic
Site-to-Site VPN, distinct from a Transit Gateway.

**AWS API:** `ec2:describe_vpn_gateways`

**Required IAM permission:** `ec2:DescribeVpnGateways`

**Input:**

```json
{ "region": "us-east-1" }
```

`vpn_gateway_ids` is optional.

**Output (`data`):** list of

```json
{
  "vpn_gateway_id": "vgw-0123456789abcdef0",
  "state": "available",
  "gateway_type": "ipsec.1",
  "amazon_side_asn": 64512,
  "vpc_attachments": [{ "vpc_id": "vpc-0123456789abcdef0", "state": "attached" }],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeVpnGateways",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_vpn_gateways", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_direct_connect_connections`

**Purpose:** List Direct Connect connections, including hosted
connections visible to this identity (a hosted connection's owner sees it
via the same API, distinguished by `partner_name`/`lag_id`).

**AWS API:** `directconnect:describe_connections`

**Required IAM permission:** `directconnect:DescribeConnections`

**Input:**

```json
{ "region": "us-east-1" }
```

`connection_id` is optional.

**Output (`data`):** list of

```json
{
  "connection_id": "dxcon-0123456789abcdef0",
  "connection_name": "primary-dx",
  "connection_state": "available",
  "location": "EqDC2",
  "bandwidth": "10Gbps",
  "vlan": 100,
  "partner_name": null,
  "lag_id": null,
  "aws_device": "EqDC2-1-2-3456-1",
  "has_logical_redundancy": "yes",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "directconnect:DescribeConnections",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_direct_connect_connections", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_direct_connect_lags`

**Purpose:** List Direct Connect Link Aggregation Groups.

**AWS API:** `directconnect:describe_lags`

**Required IAM permission:** `directconnect:DescribeLags`

**Input:**

```json
{ "region": "us-east-1" }
```

`lag_id` is optional.

**Output (`data`):** list of

```json
{
  "lag_id": "dxlag-0123456789abcdef0",
  "lag_name": "prod-lag",
  "lag_state": "available",
  "location": "EqDC2",
  "number_of_connections": 2,
  "minimum_links": 1,
  "connections_bandwidth": "10Gbps",
  "has_logical_redundancy": "yes",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "directconnect:DescribeLags",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_direct_connect_lags", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_direct_connect_virtual_interfaces`

**Purpose:** List Direct Connect virtual interfaces (private/public),
including BGP peer operational status.

**Security note:** this tool never returns the BGP MD5 authentication
key. AWS's raw `DescribeVirtualInterfaces` response can carry an
`authKey` field at both the virtual interface level and per-BGP-peer, and
a `customerRouterConfig` field (a generated router config snippet that
can embed the same key) -- neither is ever read from the AWS response by
this codebase, and `VirtualInterfaceBgpPeer` has no field that could hold
one. See [docs/security.md](security.md#secrets).

**AWS API:** `directconnect:describe_virtual_interfaces`

**Required IAM permission:** `directconnect:DescribeVirtualInterfaces`

**Input:**

```json
{ "region": "us-east-1", "connection_id": "dxcon-0123456789abcdef0" }
```

`connection_id` and `virtual_interface_id` are both optional.

**Output (`data`):** list of

```json
{
  "virtual_interface_id": "dxvif-0123456789abcdef0",
  "virtual_interface_name": "prod-private-vif",
  "virtual_interface_type": "private",
  "virtual_interface_state": "available",
  "connection_id": "dxcon-0123456789abcdef0",
  "direct_connect_gateway_id": "dxgw-0123456789abcdef0",
  "vlan": 100,
  "asn": 65000,
  "amazon_address": "192.168.1.1/30",
  "customer_address": "192.168.1.2/30",
  "address_family": "ipv4",
  "route_filter_prefixes": ["10.0.0.0/16"],
  "bgp_peers": [
    { "bgp_peer_id": "bgp-peer-0123456789abcdef0", "asn": 65000, "address_family": "ipv4", "bgp_peer_state": "available", "bgp_status": "up" }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "directconnect:DescribeVirtualInterfaces",
  "collection_completeness": "complete",
  "redacted": true
}
```

Note there is no `auth_key`/`bgp_auth_key` field, and no
`customer_router_config` field, anywhere in this model or its nested
`bgp_peers` entries -- this is an intentional, permanent omission (see
[docs/security.md](security.md#secrets)).

**Example request:**

```json
{ "tool": "aws_list_direct_connect_virtual_interfaces", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_direct_connect_gateways`

**Purpose:** List Direct Connect Gateways (global-scope), optionally with
their VGW/TGW associations.

**AWS API:** `directconnect:describe_direct_connect_gateways` +
`directconnect:describe_direct_connect_gateway_associations` (opt-in, one
call per gateway, bounded by `max_fanout_calls`)

**Required IAM permission:** `directconnect:DescribeDirectConnectGateways`,
`directconnect:DescribeDirectConnectGatewayAssociations`

**Input:**

```json
{ "region": "us-east-1", "include_associations": true }
```

`direct_connect_gateway_id` is optional. `region` selects which regional
Direct Connect endpoint issues the call -- the gateway itself is a
global-scope resource (`scope: "global"` on the record).

**Output (`data`):** list of

```json
{
  "direct_connect_gateway_id": "dxgw-0123456789abcdef0",
  "direct_connect_gateway_name": "prod-dxgw",
  "direct_connect_gateway_state": "available",
  "amazon_side_asn": 64512,
  "owner_account": "123456789012",
  "associations": [
    {
      "association_id": "assoc-0123456789abcdef0",
      "direct_connect_gateway_id": "dxgw-0123456789abcdef0",
      "associated_gateway_id": "tgw-0123456789abcdef0",
      "associated_gateway_type": "transitGateway",
      "association_state": "associated",
      "allowed_prefixes": ["10.0.0.0/8"]
    }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "directconnect:DescribeDirectConnectGateways",
  "collection_completeness": "complete",
  "redacted": false
}
```

`associations` is an empty list (not `null`) unless
`include_associations: true` was passed and the fan-out budget allowed at
least one lookup.

**Example request:**

```json
{ "tool": "aws_list_direct_connect_gateways", "input": { "region": "us-east-1", "include_associations": true } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_hosted_zones`

**Purpose:** List Route 53 hosted zones (global scope), including linked
VPC IDs for private zones.

**AWS API:** `route53:list_hosted_zones` (paginated) +
`route53:get_hosted_zone` (called once per private zone, best-effort)

**Required IAM permission:** `route53:ListHostedZones`,
`route53:GetHostedZone`

**Input:**

```json
{ "region": "us-east-1" }
```

`region` only selects which endpoint issues the call -- Route 53 has no
regional API, and every record is stamped `scope: "global"` (with
`region` still populated as the bootstrap region, so callers filtering by
`region` are unaffected).

**Output (`data`):** list of

```json
{
  "hosted_zone_id": "Z0123456789ABCDEFGHIJ",
  "name": "internal.example.com.",
  "private_zone": true,
  "record_set_count": 12,
  "comment": "internal services",
  "linked_vpc_ids": ["vpc-0123456789abcdef0"],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "route53:ListHostedZones",
  "collection_completeness": "complete",
  "redacted": false
}
```

`linked_vpc_ids` is only populated for private zones; if the follow-up
`GetHostedZone` call fails for a given zone, that zone is still returned
with `linked_vpc_ids: []` rather than being dropped or failing the whole
call (best-effort enrichment).

**Example request:**

```json
{ "tool": "aws_list_hosted_zones", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_resource_record_sets`

**Purpose:** List record-set summaries for one hosted zone, bounded by
`max_record_sets`.

**AWS API:** `route53:list_resource_record_sets` (paginated, capped)

**Required IAM permission:** `route53:ListResourceRecordSets`

**Input:**

```json
{ "region": "us-east-1", "hosted_zone_id": "Z0123456789ABCDEFGHIJ", "max_record_sets": 300 }
```

`max_record_sets` defaults to 300 and is capped at 1000 regardless of what
is requested -- a hosted zone can hold an unbounded number of record
sets, so this is a hard output cap, not a page size.

**Output (`data`):** list of

```json
{
  "name": "app.internal.example.com.",
  "record_type": "A",
  "ttl": 300,
  "resource_records": ["10.0.1.15"],
  "alias_target": null,
  "set_identifier": null,
  "routing_policy": "simple"
}
```

These records do not carry `account_id`/`region`/`tags`/`observed_at` --
`ResourceRecordSetSummary` is a plain nested record, not a top-level
`AwsResource`. If `max_record_sets` is reached before the zone is fully
enumerated, `metadata.warnings` carries an `OUTPUT_CAP_REACHED` entry
alongside the (truncated) list.

**Example request:**

```json
{ "tool": "aws_list_resource_record_sets", "input": { "region": "us-east-1", "hosted_zone_id": "Z0123456789ABCDEFGHIJ" } }
```

**Example response:**

```json
{
  "success": true,
  "tool": "aws_list_resource_record_sets",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [
    {
      "name": "app.internal.example.com.",
      "record_type": "A",
      "ttl": 300,
      "resource_records": ["10.0.1.15"],
      "alias_target": null,
      "set_identifier": null,
      "routing_policy": "simple"
    }
  ],
  "metadata": {
    "count": 1,
    "request_id": "...",
    "warnings": [
      {
        "resource_type": "resource_record_set",
        "code": "OUTPUT_CAP_REACHED",
        "message": "Hosted zone Z0123456789ABCDEFGHIJ may have more record sets than the 300-record cap for a single call; results are truncated."
      }
    ]
  },
  "error": null
}
```

---

## `aws_list_resolver_endpoints`

**Purpose:** List Route 53 Resolver endpoints.

**AWS API:** `route53resolver:list_resolver_endpoints` (paginated) +
`route53resolver:list_resolver_endpoint_ip_addresses` (one call per
endpoint, not bounded/opt-in -- always fetched since it is required to
show the endpoint's IP addresses at all)

**Required IAM permission:** `route53resolver:ListResolverEndpoints`,
`route53resolver:ListResolverEndpointIpAddresses`

**Input:**

```json
{ "region": "us-east-1" }
```

**Output (`data`):** list of

```json
{
  "resolver_endpoint_id": "rslvr-in-0123456789abcdef0",
  "name": "inbound-resolver",
  "status": "OPERATIONAL",
  "direction": "INBOUND",
  "host_vpc_id": "vpc-0123456789abcdef0",
  "security_group_ids": ["sg-0123456789abcdef0"],
  "ip_addresses": [
    { "ip": "10.0.1.10", "subnet_id": "subnet-0123456789abcdef0", "status": "ATTACHED" }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListResolverEndpoints",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_resolver_endpoints", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_resolver_rules`

**Purpose:** List Route 53 Resolver rules -- the forwarding rules behind
split-horizon DNS -- optionally with each rule's associated VPC IDs.

**AWS API:** `route53resolver:list_resolver_rules` (paginated) +
`route53resolver:list_resolver_rule_associations` (opt-in, one call per
rule, bounded by `max_fanout_calls`)

**Required IAM permission:** `route53resolver:ListResolverRules`,
`route53resolver:ListResolverRuleAssociations`

**Input:**

```json
{ "region": "us-east-1", "include_associations": true }
```

**Output (`data`):** list of

```json
{
  "resolver_rule_id": "rslvr-rr-0123456789abcdef0",
  "domain_name": "corp.example.com.",
  "status": "COMPLETE",
  "rule_type": "FORWARD",
  "resolver_endpoint_id": "rslvr-out-0123456789abcdef0",
  "target_ips": [{ "ip": "192.168.1.2", "port": 53 }],
  "owner_id": "123456789012",
  "share_status": "NOT_SHARED",
  "associated_vpc_ids": ["vpc-0123456789abcdef0"],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListResolverRules",
  "collection_completeness": "complete",
  "redacted": false
}
```

`associated_vpc_ids` is `null` unless `include_associations: true` was
passed. This is the mechanism behind split-horizon DNS: a private hosted
zone plus a `FORWARD` rule scoped to specific VPCs via these
associations. If the fan-out budget is exhausted, remaining rules keep
`associated_vpc_ids: null` and a `FANOUT_CAP_REACHED` warning appears in
`metadata.warnings`.

**Example request:**

```json
{ "tool": "aws_list_resolver_rules", "input": { "region": "us-east-1", "include_associations": true } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_resolver_rule_associations`

**Purpose:** List Resolver rule-to-VPC associations, optionally filtered
by rule.

**AWS API:** `route53resolver:list_resolver_rule_associations` (paginated)

**Required IAM permission:** `route53resolver:ListResolverRuleAssociations`

**Input:**

```json
{ "region": "us-east-1", "resolver_rule_id": "rslvr-rr-0123456789abcdef0" }
```

`resolver_rule_id` is optional.

**Output (`data`):** list of

```json
{
  "resolver_rule_association_id": "rslvr-rrassoc-0123456789abcdef0",
  "resolver_rule_id": "rslvr-rr-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "status": "COMPLETE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListResolverRuleAssociations",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_resolver_rule_associations", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_resolver_query_log_configs`

**Purpose:** List Resolver query logging configurations.

**Security note:** this tool returns configuration metadata only --
destination ARN, status, share status. There is no field and no code path
anywhere in this tool that can retrieve actual DNS query log entries;
that is out of scope for this milestone entirely, not merely un-opted-in.

**AWS API:** `route53resolver:list_resolver_query_log_configs` (paginated)

**Required IAM permission:** `route53resolver:ListResolverQueryLogConfigs`

**Input:**

```json
{ "region": "us-east-1" }
```

**Output (`data`):** list of

```json
{
  "resolver_query_log_config_id": "rqlc-0123456789abcdef0",
  "name": "prod-query-logs",
  "status": "CREATED",
  "destination_arn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/route53resolver/prod",
  "share_status": "NOT_SHARED",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListResolverQueryLogConfigs",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_resolver_query_log_configs", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_dns_firewall_rule_groups`

**Purpose:** List DNS Firewall rule groups, where the configured identity
has permission.

**AWS API:** `route53resolver:list_firewall_rule_groups` (paginated,
best-effort)

**Required IAM permission:** `route53resolver:ListFirewallRuleGroups`

**Input:**

```json
{ "region": "us-east-1" }
```

**Output (`data`):** list of

```json
{
  "firewall_rule_group_id": "rslvr-frg-0123456789abcdef0",
  "name": "prod-dns-firewall",
  "rule_count": null,
  "status": null,
  "owner_id": "123456789012",
  "share_status": "NOT_SHARED",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListFirewallRuleGroups",
  "collection_completeness": "complete",
  "redacted": false
}
```

`rule_count` and `status` are `null` in practice: `ListFirewallRuleGroups`
itself never returns `RuleCount`/`Status` in its response, even though
the model has fields for them -- these stay unpopulated unless a future
milestone adds a per-group enrichment call. DNS Firewall is a distinct,
separately-permissioned capability within the Resolver API; if this call
is denied (e.g. `AccessDeniedException`), the tool degrades to an empty
list with an `ACCESS_DENIED` (or `UNAVAILABLE`) `CollectionWarning`
rather than failing the whole tool call -- see
[docs/security.md](security.md).

**Example request:**

```json
{ "tool": "aws_list_dns_firewall_rule_groups", "input": { "region": "us-east-1" } }
```

**Example response (permission gap):**

```json
{
  "success": true,
  "tool": "aws_list_dns_firewall_rule_groups",
  "account_id": "123456789012",
  "region": "us-east-1",
  "data": [],
  "metadata": {
    "count": 0,
    "request_id": "...",
    "warnings": [
      {
        "resource_type": "dns_firewall_rule_group",
        "code": "ACCESS_DENIED",
        "message": "Could not list DNS Firewall rule groups: AccessDeniedException."
      }
    ]
  },
  "error": null
}
```

---

## `aws_list_dns_firewall_rule_group_associations`

**Purpose:** List DNS Firewall rule group VPC associations, where
allowed.

**AWS API:** `route53resolver:list_firewall_rule_group_associations`
(paginated, best-effort)

**Required IAM permission:**
`route53resolver:ListFirewallRuleGroupAssociations`

**Input:**

```json
{ "region": "us-east-1", "vpc_id": "vpc-0123456789abcdef0" }
```

`vpc_id` is optional.

**Output (`data`):** list of

```json
{
  "firewall_rule_group_association_id": "rslvr-frgassoc-0123456789abcdef0",
  "firewall_rule_group_id": "rslvr-frg-0123456789abcdef0",
  "vpc_id": "vpc-0123456789abcdef0",
  "priority": 100,
  "mutation_protection": "ENABLED",
  "status": "COMPLETE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "route53resolver:ListFirewallRuleGroupAssociations",
  "collection_completeness": "complete",
  "redacted": false
}
```

Same access-denied degradation as `aws_list_dns_firewall_rule_groups`: a
permission gap returns an empty list with an `ACCESS_DENIED` (or
`UNAVAILABLE`) warning rather than an error.

**Example request:**

```json
{ "tool": "aws_list_dns_firewall_rule_group_associations", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_core_networks`

**Purpose:** List Cloud WAN core networks, optionally with segment/edge
details and policy document.

**AWS API:** `networkmanager:list_core_networks` (paginated) +
`networkmanager:get_core_network` (opt-in via `include_details`, one call
per core network) + `networkmanager:get_core_network_policy` (opt-in via
`include_policy`, further one call per core network) -- both enrichments
share one fan-out budget bounded by `max_fanout_calls`

**Required IAM permission:** `networkmanager:ListCoreNetworks`,
`networkmanager:GetCoreNetwork`, `networkmanager:GetCoreNetworkPolicy`

**Input:**

```json
{ "region": "us-east-1", "include_details": true, "include_policy": false }
```

An account with no Cloud WAN usage returns an empty list, not an error.

**Output (`data`):** list of

```json
{
  "core_network_id": "core-network-0123456789abcdef0",
  "core_network_arn": "arn:aws:networkmanager::123456789012:core-network/core-network-0123456789abcdef0",
  "global_network_id": "global-network-0123456789abcdef0",
  "owner_account_id": "123456789012",
  "state": "AVAILABLE",
  "description": "prod-core-network",
  "segments": [{ "name": "production", "edge_locations": ["us-east-1"] }],
  "edges": [{ "edge_location": "us-east-1", "asn": 64512 }],
  "policy_document": null,
  "policy_document_truncated": false,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:ListCoreNetworks",
  "collection_completeness": "complete",
  "redacted": false
}
```

`segments`/`edges` are `null` unless `include_details: true` was passed;
`policy_document` is `null` unless `include_policy: true` was passed, and
is truncated past `MAX_POLICY_DOCUMENT_CHARS` (8000 characters, the same
cap used for VPC endpoint policies -- `policy_document_truncated: true`
when this happens). Where the account and SDK support them, both
enrichment calls succeed and `collection_completeness` stays
`"complete"`. If either enrichment call fails for a reason suggesting the
capability itself is unsupported for this account/SDK combination (not a
transient error), that core network's `collection_completeness` is set
to `"partial"` and an `UNSUPPORTED_CAPABILITY` warning is added to
`metadata.warnings` instead of the whole call failing; if the shared
fan-out budget runs out first, the skipped enrichment instead produces a
`FANOUT_CAP_REACHED` warning, also with `collection_completeness:
"partial"` on that record.

**Example request:**

```json
{ "tool": "aws_list_core_networks", "input": { "region": "us-east-1", "include_details": true } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_global_networks`

**Purpose:** List Network Manager global networks.

**AWS API:** `networkmanager:describe_global_networks` (paginated)

**Required IAM permission:** `networkmanager:DescribeGlobalNetworks`

**Input:**

```json
{ "region": "us-east-1" }
```

`global_network_ids` is optional.

**Output (`data`):** list of

```json
{
  "global_network_id": "global-network-0123456789abcdef0",
  "global_network_arn": "arn:aws:networkmanager::123456789012:global-network/global-network-0123456789abcdef0",
  "description": "prod-global-network",
  "state": "AVAILABLE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:DescribeGlobalNetworks",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_global_networks", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_manager_sites`

**Purpose:** List Network Manager sites for a global network.

**AWS API:** `networkmanager:get_sites` (paginated)

**Required IAM permission:** `networkmanager:GetSites`

**Input:**

```json
{ "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" }
```

Both fields are required.

**Output (`data`):** list of

```json
{
  "site_id": "site-0123456789abcdef0",
  "global_network_id": "global-network-0123456789abcdef0",
  "description": "HQ datacenter",
  "location": { "address": "1 Example Way, Seattle, WA", "latitude": "47.6062", "longitude": "-122.3321" },
  "state": "AVAILABLE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:GetSites",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_network_manager_sites", "input": { "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_manager_devices`

**Purpose:** List Network Manager devices for a global network.

**AWS API:** `networkmanager:get_devices` (paginated)

**Required IAM permission:** `networkmanager:GetDevices`

**Input:**

```json
{ "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" }
```

Both fields are required.

**Output (`data`):** list of

```json
{
  "device_id": "device-0123456789abcdef0",
  "global_network_id": "global-network-0123456789abcdef0",
  "site_id": "site-0123456789abcdef0",
  "description": "core router 1",
  "device_type": "router",
  "vendor": "Cisco",
  "model": "ASR1001-X",
  "state": "AVAILABLE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:GetDevices",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_network_manager_devices", "input": { "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_manager_links`

**Purpose:** List Network Manager links for a global network.

**AWS API:** `networkmanager:get_links` (paginated)

**Required IAM permission:** `networkmanager:GetLinks`

**Input:**

```json
{ "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" }
```

Both fields are required.

**Output (`data`):** list of

```json
{
  "link_id": "link-0123456789abcdef0",
  "global_network_id": "global-network-0123456789abcdef0",
  "site_id": "site-0123456789abcdef0",
  "description": "ISP uplink",
  "link_type": "broadband",
  "bandwidth": { "upload_speed": 1000, "download_speed": 1000 },
  "provider": "Example ISP",
  "state": "AVAILABLE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:GetLinks",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_network_manager_links", "input": { "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_manager_connections`

**Purpose:** List Network Manager connections for a global network.

**AWS API:** `networkmanager:get_connections` (paginated)

**Required IAM permission:** `networkmanager:GetConnections`

**Input:**

```json
{ "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" }
```

Both fields are required.

**Output (`data`):** list of

```json
{
  "connection_id": "connection-0123456789abcdef0",
  "global_network_id": "global-network-0123456789abcdef0",
  "device_id": "device-0123456789abcdef0",
  "connected_device_id": "device-0987654321fedcba0",
  "link_id": "link-0123456789abcdef0",
  "connected_link_id": null,
  "description": "core-to-edge link",
  "state": "AVAILABLE",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:GetConnections",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_network_manager_connections", "input": { "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_transit_gateway_registrations`

**Purpose:** List Transit Gateway registrations to a Network Manager
global network -- the link between a classic Transit Gateway and Network
Manager.

**AWS API:** `networkmanager:get_transit_gateway_registrations`
(paginated)

**Required IAM permission:**
`networkmanager:GetTransitGatewayRegistrations`

**Input:**

```json
{ "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" }
```

Both fields are required.

**Output (`data`):** list of

```json
{
  "global_network_id": "global-network-0123456789abcdef0",
  "transit_gateway_arn": "arn:aws:ec2:us-east-1:123456789012:transit-gateway/tgw-0123456789abcdef0",
  "state": "AVAILABLE",
  "state_message": null,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "global",
  "source_api": "networkmanager:GetTransitGatewayRegistrations",
  "collection_completeness": "complete",
  "redacted": false
}
```

Note this record has no ID field of its own beyond `transit_gateway_arn`
-- a registration is identified by which Transit Gateway it registers,
not by a separate registration ID.

**Example request:**

```json
{ "tool": "aws_list_transit_gateway_registrations", "input": { "region": "us-east-1", "global_network_id": "global-network-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_flow_logs`

**Purpose:** List VPC Flow Log configurations and delivery/aggregation
metadata, optionally filtered by resource ID.

**Security note:** this tool returns configuration and delivery metadata
only (destination, status, format, aggregation interval). There is no
field, parameter, or code path anywhere in this codebase that retrieves
actual flow log record contents (the traffic records written to
CloudWatch Logs/S3/Kinesis Firehose) -- that is an explicit,
unconditional guardrail, not an opt-in choice.

**AWS API:** `ec2:describe_flow_logs` (paginated)

**Required IAM permission:** `ec2:DescribeFlowLogs`

**Input:**

```json
{ "region": "us-east-1", "resource_id": "vpc-0123456789abcdef0" }
```

`resource_id` and `flow_log_ids` are both optional (`resource_id` takes
precedence if both are given).

**Output (`data`):** list of

```json
{
  "flow_log_id": "fl-0123456789abcdef0",
  "flow_log_status": "ACTIVE",
  "resource_id": "vpc-0123456789abcdef0",
  "traffic_type": "ALL",
  "log_destination_type": "cloud-watch-logs",
  "log_destination": "arn:aws:logs:us-east-1:123456789012:log-group:/vpc/flowlogs",
  "log_group_name": "/vpc/flowlogs",
  "deliver_logs_status": "SUCCESS",
  "deliver_logs_error_message": null,
  "log_format": "${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status}",
  "max_aggregation_interval": 600,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeFlowLogs",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_flow_logs", "input": { "region": "us-east-1", "resource_id": "vpc-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_get_hybrid_topology`

**Purpose:** Join VPC, VPN, Direct Connect, and DNS resources attached to
one Transit Gateway into a typed node/edge topology graph -- the hybrid
connectivity counterpart to Milestone 2's `aws_get_vpc_topology`, anchored
on a Transit Gateway rather than a single VPC. This is a connectivity/
configuration map, not a reachability analysis: it does not claim or
imply that traffic actually flows along any edge, only that AWS reports
the relationship. See [docs/architecture.md](architecture.md) for how
Milestone 2's topology assembly pattern (raw collection fully separate
from graph construction) carries over here.

Classic Network Manager resources (sites, devices, links, connections)
are **not** joined into this graph, even when a registered global network
exists for the Transit Gateway -- they have their own dedicated
`aws_list_network_manager_*` tools above. Only VPC, TGW, VPN, Direct
Connect Gateway, and DNS (hosted zones + Resolver endpoints) are joined
here, matching this milestone's topology scope exactly.

**AWS API:** `ec2:describe_transit_gateways`,
`ec2:describe_transit_gateway_attachments`,
`ec2:describe_vpn_connections`, `ec2:describe_customer_gateways`,
`route53:list_hosted_zones` (+ `route53:get_hosted_zone` for private
zones), `route53resolver:list_resolver_endpoints` (+
`route53resolver:list_resolver_endpoint_ip_addresses`) -- invoked only for
resources that attach to (or are joined from) the requested Transit
Gateway.

**Required IAM permission:** the union of every permission needed by the
tools above: `ec2:DescribeTransitGateways`,
`ec2:DescribeTransitGatewayAttachments`, `ec2:DescribeVpnConnections`,
`ec2:DescribeCustomerGateways`, `route53:ListHostedZones`,
`route53:GetHostedZone`, `route53resolver:ListResolverEndpoints`,
`route53resolver:ListResolverEndpointIpAddresses`.

**Input:**

```json
{ "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0" }
```

Both fields are required -- like `aws_get_vpc_topology`, this tool has no
"list everything" mode; it always scopes to one Transit Gateway. If the
Transit Gateway does not exist in the given region, the tool returns a
`RESOURCE_NOT_FOUND` error rather than an empty graph.

**Output (`data`):**

```json
{
  "transit_gateway_id": "tgw-0123456789abcdef0",
  "region": "us-east-1",
  "nodes": [
    { "node_id": "tgw-0123456789abcdef0", "node_type": "transit_gateway", "label": "prod-hub", "vpc_id": null, "region": "us-east-1", "tags": { "Name": "prod-hub" } },
    { "node_id": "tgw-attach-0123456789abcdef0", "node_type": "transit_gateway_attachment", "label": "vpc:vpc-0123456789abcdef0", "vpc_id": null, "region": "us-east-1", "tags": {} },
    { "node_id": "vpc-0123456789abcdef0", "node_type": "vpc", "label": "vpc-0123456789abcdef0", "vpc_id": "vpc-0123456789abcdef0", "region": "us-east-1", "tags": {} },
    { "node_id": "tgw-attach-0987654321fedcba0", "node_type": "transit_gateway_attachment", "label": "vpn:vpn-0123456789abcdef0", "vpc_id": null, "region": "us-east-1", "tags": {} },
    { "node_id": "vpn-0123456789abcdef0", "node_type": "vpn_connection", "label": "vpn-0123456789abcdef0", "vpc_id": null, "region": "us-east-1", "tags": {} },
    { "node_id": "cgw-0123456789abcdef0", "node_type": "customer_gateway", "label": "cgw-0123456789abcdef0", "vpc_id": null, "region": "us-east-1", "tags": {} },
    { "node_id": "external:203.0.113.99", "node_type": "external_endpoint", "label": "203.0.113.99", "vpc_id": null, "region": "us-east-1", "tags": {} }
  ],
  "edges": [
    { "source_id": "tgw-0123456789abcdef0", "target_id": "tgw-attach-0123456789abcdef0", "relationship": "has_attachment", "evidence": "attachment tgw-attach-0123456789abcdef0 TransitGatewayId=tgw-0123456789abcdef0" },
    { "source_id": "tgw-attach-0123456789abcdef0", "target_id": "vpc-0123456789abcdef0", "relationship": "attaches", "evidence": "attachment tgw-attach-0123456789abcdef0 ResourceId=vpc-0123456789abcdef0 ResourceType=vpc" },
    { "source_id": "tgw-0123456789abcdef0", "target_id": "tgw-attach-0987654321fedcba0", "relationship": "has_attachment", "evidence": "attachment tgw-attach-0987654321fedcba0 TransitGatewayId=tgw-0123456789abcdef0" },
    { "source_id": "tgw-attach-0987654321fedcba0", "target_id": "vpn-0123456789abcdef0", "relationship": "attaches", "evidence": "attachment tgw-attach-0987654321fedcba0 ResourceId=vpn-0123456789abcdef0 ResourceType=vpn" },
    { "source_id": "vpn-0123456789abcdef0", "target_id": "cgw-0123456789abcdef0", "relationship": "terminates_at", "evidence": "vpn connection vpn-0123456789abcdef0 CustomerGatewayId=cgw-0123456789abcdef0" },
    { "source_id": "cgw-0123456789abcdef0", "target_id": "external:203.0.113.99", "relationship": "represents", "evidence": "customer gateway cgw-0123456789abcdef0 IpAddress=203.0.113.99" }
  ],
  "warnings": [],
  "api_call_count": 7
}
```

`node_type` values this tool can produce, beyond Milestone 2's VPC-scoped
set: `transit_gateway`, `transit_gateway_attachment`, `vpc`,
`vpn_connection`, `customer_gateway`, `direct_connect_gateway`,
`hosted_zone`, `resolver_endpoint`, and `external_endpoint`.
`external_endpoint` is this tool's explicit label for a genuinely
non-AWS entity -- specifically, a customer gateway's public on-premises
IP address -- that the graph can name but not further resolve; it is
distinct from an **orphan reference** (an edge whose target has no node
at all), which this tool uses for AWS-domain resources outside this
milestone's resolution scope.

`relationship` values include `has_attachment` (Transit Gateway to its
attachment), `attaches` (an attachment to the VPC/VPN
connection/Direct-Connect-Gateway it attaches), `terminates_at` (a VPN
connection to its customer gateway), `represents` (a customer gateway to
the `external_endpoint` node for its public IP), `resolves_for` (a VPC to
a hosted zone whose `linked_vpc_ids` include it), and `hosts` (a VPC to a
Resolver endpoint whose `host_vpc_id` matches it).

Attachment resource types this tool resolves into their own node beyond
the attachment node itself are `vpc`, `vpn`, and
`direct-connect-gateway`. An attachment of any other type (`peering`,
`connect`, `tgw-peering`) still gets a `transit_gateway_attachment` node
-- just no deeper resolution -- paired with an `OUT_OF_SCOPE_TARGET`
`CollectionWarning` explaining why no further node was created. A
cross-account attachment (`resource_owner_id` differing from the caller's
own account) still gets a node but is paired with a
`CROSS_ACCOUNT_ATTACHMENT` warning noting only attachment-level metadata
is visible. `api_call_count` tracks every AWS API call made while
assembling this graph.

**Example request:**

```json
{ "tool": "aws_get_hybrid_topology", "input": { "region": "us-east-1", "transit_gateway_id": "tgw-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope (a single object, not a list -- `metadata.count` is not set for
this tool, matching `aws_get_vpc_topology`).

---

## `aws_explain_network_path`

**Purpose:** Explain whether traffic from a source (subnet, ENI, or IP) can
reach a destination IP/CIDR: deterministic route resolution (longest-prefix
match across local/NAT/peering/TGW/gateway/endpoint/blackhole targets)
combined with security group (stateful) and network ACL (stateless, all
four legs) evaluation where enough information is given to evaluate them.
Every conclusion carries severity, confidence, evidence, and reasoning
steps; when required evidence is missing, the result says indeterminate
rather than guessing. Never claims certainty from incomplete data and
never changes any AWS configuration.

**AWS API:** Builds on the same read-only snapshot collection as
`aws_get_vpc_topology` -- `ec2:DescribeVpcs`, `DescribeSubnets`,
`DescribeRouteTables`, `DescribeSecurityGroups`,
`DescribeSecurityGroupRules`, `DescribeNetworkAcls`,
`DescribeNetworkInterfaces`, `DescribeInternetGateways`,
`DescribeEgressOnlyInternetGateways`, `DescribeNatGateways`,
`DescribeVpcPeeringConnections`, `DescribeVpcEndpoints`,
`DescribeManagedPrefixLists` + `GetManagedPrefixListEntries` (only for
prefix lists actually referenced by a collected route), plus
`elasticloadbalancing:DescribeLoadBalancers`/`DescribeListeners`/
`DescribeTargetGroups`/`DescribeTags` -- collected region-wide in one pass
(then filtered client-side), not once per source/destination pair. When
`include_transit_gateway: true`, also `ec2:DescribeTransitGateways`,
`DescribeTransitGatewayAttachments`, `DescribeTransitGatewayRouteTables`,
`GetTransitGatewayRouteTableAssociations`,
`GetTransitGatewayRouteTablePropagations`, `SearchTransitGatewayRoutes`.
No AWS API call this tool makes is new relative to Milestones 1-3 -- the
diagnostics engine itself never imports boto3; it reasons entirely from
the already-collected, normalized snapshot.

**Required IAM permission:** the union of the actions above -- all already
covered by the Milestone 1-3 policy (see
[Example IAM policy](#example-iam-policy) below); this tool needs no new
EC2/ELB permissions.

**Input:**

```json
{
  "region": "us-east-1",
  "destination": "198.51.100.10",
  "source_subnet_id": "subnet-0123456789abcdef0",
  "protocol": "tcp",
  "port": 443,
  "include_transit_gateway": false
}
```

`destination` (an IP address or CIDR block) and `region` are required.
Exactly one of `source_subnet_id`, `source_eni_id`, or (`source_ip` +
`vpc_id`) must identify the source; if more than one is given,
`source_eni_id` wins, then `source_subnet_id`, then `source_ip`+`vpc_id`.
`destination_eni_id`/`destination_ip` are optional and enable security
group/NACL evaluation on the destination side when known.  `protocol`
defaults to `"tcp"`; `port` is optional but required for network ACL
evaluation. `include_transit_gateway` is opt-in and adds the Transit
Gateway API calls above so a path routed through a TGW can be resolved.

**Output (`data`):**

A `PathExplanation`:

```json
{
  "overall_verdict": "partially_evaluated",
  "route_verdict": "routable",
  "hops": [
    {
      "hop_number": 1,
      "vpc_id": "vpc-0123456789abcdef0",
      "location_id": "subnet-0123456789abcdef0",
      "route_table_id": "rtb-0123456789abcdef0",
      "matched_route": {
        "destination_cidr_block": "0.0.0.0/0",
        "destination_prefix_list_id": null,
        "target": "igw-0123456789abcdef0",
        "target_type": "gateway",
        "state": "active",
        "origin": "CreateRoute"
      },
      "target_type": "gateway",
      "description": "Matched route to gateway:igw-0123456789abcdef0."
    }
  ],
  "findings": [
    {
      "rule_id": "ROUTE-001",
      "rule_version": "1.0.0",
      "severity": "info",
      "confidence": "high",
      "summary": "Path terminates via gateway:igw-0123456789abcdef0.",
      "affected_resources": ["igw-0123456789abcdef0"],
      "evidence": [
        {
          "source": "subnet:subnet-0123456789abcdef0",
          "detail": "VpcId=vpc-0123456789abcdef0 CidrBlock=10.0.1.0/24"
        },
        {
          "source": "route_table:rtb-0123456789abcdef0",
          "detail": "0.0.0.0/0 -> gateway:igw-0123456789abcdef0 (state=active, origin=CreateRoute)"
        }
      ],
      "reasoning": [
        {
          "step": 1,
          "description": "Resolved source to subnet subnet-0123456789abcdef0 in VPC vpc-0123456789abcdef0.",
          "evidence_indices": [0]
        },
        {
          "step": 2,
          "description": "Longest-prefix match in rtb-0123456789abcdef0: 0.0.0.0/0 -> gateway:igw-0123456789abcdef0.",
          "evidence_indices": [1]
        }
      ],
      "assumptions": [],
      "limitations": [
        "security group evaluation skipped: no source ENI could be resolved (pass source_eni_id, or a source_ip matching a known ENI)",
        "network ACL evaluation skipped: requires a same-VPC path with concrete source_ip, destination_ip, and port"
      ],
      "freshness": "2026-08-27T18:00:00+00:00",
      "remediation": null
    }
  ]
}
```

`route_verdict` is the routing-layer-only verdict from longest-prefix-match
resolution: `routable`, `blocked_at_routing`, `left_analyzed_scope`,
`unresolved_target`, or `indeterminate`. `overall_verdict` additionally
folds in security group and NACL evaluation: `allowed`, `blocked`,
`partially_evaluated`, or `indeterminate` -- `blocked` if routing itself
fails or a security group/NACL evaluation finds a deny; `partially_evaluated`
if routing succeeds but a required evaluation was skipped (as in the
example above) or a run evaluation itself came back `confidence:
"indeterminate"`; `allowed` only when routing succeeds and every
evaluation that ran found no deny.

`findings` always includes the `ROUTE-001` route-resolution finding, plus
a `SEC-001` (security group) finding whenever a source ENI can be resolved
(directly from `source_eni_id`, or by matching `source_ip` against a
collected ENI's private/public IP), plus a `SEC-002` (network ACL) finding
whenever the path stays within one VPC (the last hop's `target_type` is
`local`) and concrete `source_ip`, `destination_ip`, and `port` were all
given.

**`confidence` can legitimately be `"indeterminate"`** on any finding this
tool returns -- this is a first-class, expected outcome when required
evidence is missing (an unresolvable prefix-list route, a peer VPC or
Transit Gateway target outside the collected snapshot, a routing cycle),
never an error and never hidden as one. Separately, when security-group or
network-ACL evaluation is **skipped outright** -- not run at all, as
opposed to run and indeterminate -- because the tool lacks enough
information to run it (no source ENI is resolvable, or the path leaves
the VPC before a known destination subnet is reached), that is always
recorded as an explicit `limitations` entry on the route finding, exactly
as shown above; it is never silently treated as "allowed." `remediation`,
when present, is always advisory text for a human to read and act on --
nothing in this tool, or anywhere in this codebase, executes it.

**Example request:**

```json
{ "tool": "aws_explain_network_path", "input": { "region": "us-east-1", "destination": "198.51.100.10", "source_subnet_id": "subnet-0123456789abcdef0", "protocol": "tcp", "port": 443 } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope (a single object, not a list -- `metadata.count` is not set for
this tool).

---

## `aws_find_network_risks`

**Purpose:** Scan a region (optionally scoped to specific VPCs) for
network misconfigurations: CIDR overlap, orphaned/unpropagated Transit
Gateway attachments, asymmetric VPC peering routes, degraded/failed
resource states, and internet-exposed ENIs/load balancers (distinguishing
potential exposure from proven reachability). Returns every finding
checked, including informational ones, unless `min_severity` filters them
out -- "not evaluated" never looks the same as "checked, nothing found."
Read-only; never modifies any resource.

**AWS API:** The same core snapshot collection as `aws_explain_network_path`
above (`ec2:DescribeVpcs`/`DescribeSubnets`/`DescribeRouteTables`/
`DescribeSecurityGroups`/`DescribeSecurityGroupRules`/`DescribeNetworkAcls`/
`DescribeNetworkInterfaces`/`DescribeInternetGateways`/
`DescribeEgressOnlyInternetGateways`/`DescribeNatGateways`/
`DescribeVpcPeeringConnections`/`DescribeVpcEndpoints`/
`DescribeManagedPrefixLists`+`GetManagedPrefixListEntries`,
`elasticloadbalancing:DescribeLoadBalancers`/`DescribeListeners`/
`DescribeTargetGroups`/`DescribeTags`), plus the same opt-in Transit
Gateway calls when `include_transit_gateway: true`. No AWS API call here
is new relative to Milestones 1-3.

**Required IAM permission:** the union of the actions above -- already
covered by the Milestone 1-3 policy; this tool needs no new permissions.

**Input:**

```json
{
  "region": "us-east-1",
  "vpc_ids": ["vpc-0123456789abcdef0"],
  "min_severity": "medium",
  "include_transit_gateway": false
}
```

`vpc_ids` restricts the scan to specific VPCs; omit for the whole region.
`min_severity` (one of `critical`, `high`, `medium`, `low`, `info`) drops
findings less severe than the threshold from the returned list; omit it
to get every finding, including informational "checked, nothing found"
ones. `include_transit_gateway` is opt-in and adds Transit Gateway
attachment/route-table collection so the TGW-related rules (`CONSIST-002`,
`CONSIST-003`) can run.

**Rule catalog** -- the full set of rules the diagnostics engine
registers. This tool always runs every rule marked "risk scan" below
unconditionally (not individually selectable); the `ROUTE-*`/`SEC-*`
rules only ever run inside `aws_explain_network_path`, not here:

| rule_id | title | default_severity | runs in |
| --- | --- | --- | --- |
| `CONSIST-001` | CIDR overlap | `high` | risk scan |
| `CONSIST-002` | Orphaned Transit Gateway attachment | `medium` | risk scan |
| `CONSIST-003` | Missing Transit Gateway route propagation | `low` | risk scan |
| `CONSIST-004` | Asymmetric VPC peering route | `high` | risk scan |
| `CONSIST-005` | Degraded or failed resource state | `high` | risk scan |
| `EXPOSE-001` | ENI internet exposure | `medium` | risk scan |
| `EXPOSE-002` | Load balancer internet exposure | `medium` | risk scan |
| `ROUTE-001` | Route resolution | `info` | `aws_explain_network_path` only |
| `SEC-001` | Security group evaluation | `info` | `aws_explain_network_path` only |
| `SEC-002` | Network ACL evaluation | `info` | `aws_explain_network_path` only |

Every ENI and every load balancer in the scanned scope is checked by
`EXPOSE-001`/`EXPOSE-002`, including ones with nothing wrong -- an `info`
finding, not an omission -- so "checked, nothing found" never looks like
"not checked."

**Output (`data`):** a plain list of `Finding`, deterministically sorted
by `(severity, rule_id, first affected_resources entry)` so repeated runs
against the same snapshot always produce the same order:

```json
[
  {
    "rule_id": "EXPOSE-001",
    "rule_version": "1.0.0",
    "severity": "critical",
    "confidence": "high",
    "summary": "eni-0123456789abcdef0 is reachable from the public internet: it has a public IP, a route to an internet gateway, and a security group/NACL that permit inbound traffic on tcp:22-22.",
    "affected_resources": ["eni-0123456789abcdef0"],
    "evidence": [
      { "source": "network_interface:eni-0123456789abcdef0", "detail": "PublicIp=203.0.113.44" },
      { "source": "subnet:subnet-0123456789abcdef0", "detail": "has active route to an internet gateway: True" },
      { "source": "network_interface:eni-0123456789abcdef0", "detail": "security group ingress open to 0.0.0.0/0 or ::/0: tcp:22-22" },
      { "source": "subnet:subnet-0123456789abcdef0", "detail": "NACL permits inbound from 0.0.0.0/0 or ::/0: True" }
    ],
    "reasoning": [
      {
        "step": 1,
        "description": "has_public_ip=True, has_public_route=True, open_sg_ingress_rules=1, nacl_allows_inbound=True.",
        "evidence_indices": [0, 1, 2, 3]
      }
    ],
    "assumptions": [],
    "limitations": [],
    "freshness": "2026-08-27T18:00:00+00:00",
    "remediation": "Restrict the security group ingress rule to a specific known CIDR, or remove the public IP/route if this resource is not meant to be internet-facing."
  },
  {
    "rule_id": "CONSIST-003",
    "rule_version": "1.0.0",
    "severity": "low",
    "confidence": "medium",
    "summary": "Attachment tgw-attach-0123456789abcdef0 (vpc:vpc-0123456789abcdef0) is associated but has no route propagation into any route table.",
    "affected_resources": ["tgw-attach-0123456789abcdef0"],
    "evidence": [
      { "source": "transit_gateway_attachment:tgw-attach-0123456789abcdef0", "detail": "associated, not propagated" }
    ],
    "reasoning": [
      { "step": 1, "description": "No propagation found in any collected route table.", "evidence_indices": [0] }
    ],
    "assumptions": [],
    "limitations": [],
    "freshness": "2026-08-27T18:00:00+00:00",
    "remediation": "Enable route propagation for tgw-attach-0123456789abcdef0, or add static routes, if its routes should be reachable."
  }
]
```

As with `aws_explain_network_path`, a finding's `confidence` can be
`"indeterminate"` (e.g. an ENI or load balancer referenced by ID that this
snapshot could not resolve) -- always a first-class, explicit outcome,
carried in `limitations`, never an omission. `remediation` is always
advisory text; nothing in this codebase executes it.

**Example request:**

```json
{ "tool": "aws_find_network_risks", "input": { "region": "us-east-1", "min_severity": "low" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope. `metadata.count` is the number of findings returned (after
`min_severity` filtering, if given).

---

## `aws_get_network_health`

**Purpose:** Report network resource health: degraded/failed NAT
gateways, Transit Gateway attachments, and VPN tunnels; which VPCs have no
Flow Log configured; and, opt-in, bounded CloudWatch metrics, existing
Reachability Analyzer results that found no path or failed, and recent
(capped, read-only) CloudTrail network-configuration events. This tool
**never enables Flow Logs, never creates a Reachability Analyzer
path/analysis, and never retrieves log record contents** -- every signal
it reports is a read of state that already exists.

**AWS API:** The same core snapshot collection as the other diagnostic
tools, always including VPN resources (`ec2:DescribeVpnConnections`,
`DescribeCustomerGateways`) since VPN tunnel health feeds the degraded-
resource check; plus `ec2:DescribeFlowLogs` (Flow Log coverage, always
collected); plus, opt-in, `cloudwatch:GetMetricStatistics` (one call per
catalog metric per NAT gateway in scope, bounded by `max_fanout_calls`),
`ec2:DescribeNetworkInsightsAnalyses` (reads existing analyses only --
never `StartNetworkInsightsAnalysis`), and `cloudtrail:LookupEvents`
(bounded lookback and result cap).

**Required IAM permission:** the core snapshot and `ec2:DescribeFlowLogs`
permissions above (already granted by the Milestone 1-3 policy), plus two
permissions this milestone adds: `cloudwatch:GetMetricStatistics` and
`cloudtrail:LookupEvents` (`ec2:DescribeNetworkInsightsAnalyses` is
covered by the new Network Insights statement documented for the tools
below).

**Input:**

```json
{
  "region": "us-east-1",
  "vpc_ids": ["vpc-0123456789abcdef0"],
  "include_metrics": false,
  "include_reachability_analyses": false,
  "include_recent_changes": false
}
```

`vpc_ids` restricts the report to specific VPCs; omit for the whole
region. All three `include_*` flags default to `false`:

- `include_metrics` queries a small, curated catalog of the specific
  CloudWatch metrics each network resource type actually publishes that
  matter for a health check (`KNOWN_NETWORK_METRICS`) -- NAT Gateway
  `ErrorPortAllocation`/`PacketsDropCount`, Transit Gateway
  `PacketDropCountBlackhole`/`PacketDropCountNoRoute`, and VPN
  `TunnelState` -- not open-ended metric discovery via
  `cloudwatch:ListMetrics`. Today this tool queries every catalog metric
  (both NAT gateway metrics) for each NAT gateway in scope: one
  `cloudwatch:GetMetricStatistics` call per metric per NAT gateway, each
  bounded to a 24-hour lookback and capped at 288 datapoints, drawn from
  the shared `max_fanout_calls` budget. If the budget is exhausted before
  every NAT gateway is queried, the remaining ones are skipped and a note
  is added to `limitations` rather than the `metrics` list silently
  coming back incomplete with no explanation.
- `include_reachability_analyses` lists existing Reachability Analyzer
  analyses (`ec2:DescribeNetworkInsightsAnalyses`) and surfaces only the
  ones where `network_path_found` is `false` or `status` is `"failed"` --
  it never starts a new analysis.
- `include_recent_changes` looks up recent CloudTrail events
  (`cloudtrail:LookupEvents`, filtered server-side to
  `EventSource=ec2.amazonaws.com` and further filtered client-side to a
  fixed allowlist of network-relevant event names -- route/security-group/
  NACL/peering/Transit-Gateway-attachment/NAT/internet-gateway/VPN/VPC-
  endpoint mutations), with a lookback capped at 7 days (24 hours by
  default) and results capped at 50.

**Output (`data`):**

A `NetworkHealthReport`:

```json
{
  "region": "us-east-1",
  "collected_at": "2026-08-27T18:00:00+00:00",
  "degraded_resources": [
    {
      "rule_id": "CONSIST-005",
      "rule_version": "1.0.0",
      "severity": "high",
      "confidence": "high",
      "summary": "NAT gateway nat-0123456789abcdef0 is in state 'failed': Insufficient capacity.",
      "affected_resources": ["nat-0123456789abcdef0"],
      "evidence": [
        { "source": "nat_gateway:nat-0123456789abcdef0", "detail": "State=failed FailureCode=InsufficientCapacity" }
      ],
      "reasoning": [
        { "step": 1, "description": "NAT gateway state is 'failed'.", "evidence_indices": [0] }
      ],
      "assumptions": [],
      "limitations": [],
      "freshness": "2026-08-27T18:00:00+00:00",
      "remediation": "Replace the NAT gateway; a failed NAT gateway silently drops all egress traffic routed to it."
    }
  ],
  "flow_log_configs": [
    {
      "flow_log_id": "fl-0123456789abcdef0",
      "flow_log_status": "ACTIVE",
      "resource_id": "vpc-0987654321fedcba0",
      "traffic_type": "ALL",
      "log_destination_type": "cloud-watch-logs",
      "log_destination": "arn:aws:logs:us-east-1:123456789012:log-group:/vpc/flowlogs",
      "log_group_name": "/vpc/flowlogs",
      "deliver_logs_status": "SUCCESS",
      "deliver_logs_error_message": null,
      "log_format": "${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status}",
      "max_aggregation_interval": 600,
      "tags": {},
      "account_id": "123456789012",
      "region": "us-east-1",
      "observed_at": "2026-08-27T18:00:00+00:00"
    }
  ],
  "vpcs_without_flow_logs": ["vpc-0123456789abcdef0"],
  "metrics": [],
  "unhealthy_reachability_analyses": [],
  "recent_config_changes": [],
  "limitations": []
}
```

`degraded_resources` reuses the exact same `CONSIST-005` rule
`aws_find_network_risks` runs -- this tool's health report and the risk
scanner agree by construction, not by two independently-maintained checks.
`vpcs_without_flow_logs` is every VPC in scope whose `vpc_id` does not
appear as a Flow Log's `resource_id` -- this only reports the *absence* of
a Flow Log configuration; it never enables one. `metrics`/
`unhealthy_reachability_analyses`/`recent_config_changes` stay empty
unless the corresponding `include_*` flag was passed. `limitations` is a
top-level list of any global caveats for this report (currently just the
`max_fanout_calls`-exhaustion note for `include_metrics`, if it occurs) --
distinct from the per-finding `limitations` inside `degraded_resources`.

**Example request:**

```json
{ "tool": "aws_get_network_health", "input": { "region": "us-east-1", "include_metrics": true, "include_recent_changes": true } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope (a single object, not a list -- `metadata.count` is not set for
this tool).

---

## `aws_list_network_insights_paths`

**Purpose:** List existing Reachability Analyzer path definitions.
Read-only result *retrieval* -- this tool never creates a path
(`ec2:CreateNetworkInsightsPath` is a mutating operation, out of scope for
this milestone).

**AWS API:** `ec2:DescribeNetworkInsightsPaths` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkInsightsPaths`

**Input:**

```json
{ "region": "us-east-1", "network_insights_path_ids": ["nip-0123456789abcdef0"] }
```

`network_insights_path_ids` is optional; omit it to list every path
definition in the region.

**Output (`data`):** list of

```json
{
  "network_insights_path_id": "nip-0123456789abcdef0",
  "network_insights_path_arn": "arn:aws:ec2:us-east-1:123456789012:network-insights-path/nip-0123456789abcdef0",
  "source": "eni-0123456789abcdef0",
  "destination": "eni-0987654321fedcba0",
  "source_ip": null,
  "destination_ip": null,
  "protocol": "tcp",
  "destination_port": 443,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeNetworkInsightsPaths",
  "collection_completeness": "complete",
  "redacted": false
}
```

A path definition on its own does not mean it has ever been analyzed --
pair this with `aws_list_network_insights_analyses` (filtered to this
path's ID) to see whether, and with what result.

**Example request:**

```json
{ "tool": "aws_list_network_insights_paths", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_insights_analyses`

**Purpose:** List existing Reachability Analyzer analyses for a path,
including whether a network path was found. Read-only result *retrieval*
-- this tool never starts a new analysis
(`ec2:StartNetworkInsightsAnalysis` is a mutating operation, out of scope
for this milestone).

**AWS API:** `ec2:DescribeNetworkInsightsAnalyses` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkInsightsAnalyses`

**Input:**

```json
{ "region": "us-east-1", "network_insights_path_id": "nip-0123456789abcdef0" }
```

`network_insights_path_id` and `network_insights_analysis_ids` are both
optional; omit both to list every analysis in the region.

**Output (`data`):** list of

```json
{
  "network_insights_analysis_id": "nia-0123456789abcdef0",
  "network_insights_analysis_arn": "arn:aws:ec2:us-east-1:123456789012:network-insights-analysis/nia-0123456789abcdef0",
  "network_insights_path_id": "nip-0123456789abcdef0",
  "status": "succeeded",
  "status_message": null,
  "warning_message": null,
  "network_path_found": false,
  "start_date": "2026-08-27T17:00:00+00:00",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeNetworkInsightsAnalyses",
  "collection_completeness": "complete",
  "redacted": false
}
```

`network_path_found: false` here is exactly the signal
`aws_get_network_health`'s `include_reachability_analyses` flag surfaces
under `unhealthy_reachability_analyses` -- an analysis that completed but
found no path, or one whose `status` is `"failed"`.

**Example request:**

```json
{ "tool": "aws_list_network_insights_analyses", "input": { "region": "us-east-1", "network_insights_path_id": "nip-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_insights_access_scopes`

**Purpose:** List existing Network Access Analyzer scope definitions.
Read-only result *retrieval* -- this tool never creates a scope
(`ec2:CreateNetworkInsightsAccessScope` is a mutating operation, out of
scope for this milestone).

**AWS API:** `ec2:DescribeNetworkInsightsAccessScopes` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkInsightsAccessScopes`

**Input:**

```json
{ "region": "us-east-1", "network_insights_access_scope_ids": ["nis-0123456789abcdef0"] }
```

`network_insights_access_scope_ids` is optional; omit it to list every
access scope in the region.

**Output (`data`):** list of

```json
{
  "network_insights_access_scope_id": "nis-0123456789abcdef0",
  "network_insights_access_scope_arn": "arn:aws:ec2:us-east-1:123456789012:network-insights-access-scope/nis-0123456789abcdef0",
  "created_date": "2026-08-01T12:00:00+00:00",
  "updated_date": "2026-08-01T12:00:00+00:00",
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeNetworkInsightsAccessScopes",
  "collection_completeness": "complete",
  "redacted": false
}
```

**Example request:**

```json
{ "tool": "aws_list_network_insights_access_scopes", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_list_network_insights_access_scope_analyses`

**Purpose:** List existing Network Access Analyzer scope analyses,
including whether findings were found. Read-only result *retrieval* --
this tool never starts a new scope analysis
(`ec2:StartNetworkInsightsAccessScopeAnalysis` is a mutating operation,
out of scope for this milestone).

**AWS API:** `ec2:DescribeNetworkInsightsAccessScopeAnalyses` (paginated)

**Required IAM permission:** `ec2:DescribeNetworkInsightsAccessScopeAnalyses`

**Input:**

```json
{ "region": "us-east-1", "network_insights_access_scope_id": "nis-0123456789abcdef0" }
```

`network_insights_access_scope_id` is optional; omit it to list every
scope analysis in the region.

**Output (`data`):** list of

```json
{
  "network_insights_access_scope_analysis_id": "nisa-0123456789abcdef0",
  "network_insights_access_scope_analysis_arn": "arn:aws:ec2:us-east-1:123456789012:network-insights-access-scope-analysis/nisa-0123456789abcdef0",
  "network_insights_access_scope_id": "nis-0123456789abcdef0",
  "status": "succeeded",
  "status_message": null,
  "warning_message": null,
  "start_date": "2026-08-27T17:00:00+00:00",
  "end_date": "2026-08-27T17:05:00+00:00",
  "findings_found": "true",
  "analyzed_eni_count": 42,
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:DescribeNetworkInsightsAccessScopeAnalyses",
  "collection_completeness": "complete",
  "redacted": false
}
```

`findings_found` is AWS's own tri-state string (`"true"`, `"false"`, or
`"unknown"`), passed through as-is rather than coerced to a boolean --
`"unknown"` (the analysis has not finished, or AWS could not determine it)
is a genuinely different state from `"false"` (finished, found nothing).
When `findings_found` is `"true"`, pass this record's
`network_insights_access_scope_analysis_id` to
`aws_get_network_insights_access_scope_analysis_findings` to retrieve the
findings themselves.

**Example request:**

```json
{ "tool": "aws_list_network_insights_access_scope_analyses", "input": { "region": "us-east-1", "network_insights_access_scope_id": "nis-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## `aws_get_network_insights_access_scope_analysis_findings`

**Purpose:** Retrieve findings for a completed Network Access Analyzer
scope analysis, bounded to a maximum number of findings. Read-only result
*retrieval* -- this tool never starts, modifies, or deletes any scope
analysis.

**AWS API:** `ec2:GetNetworkInsightsAccessScopeAnalysisFindings`
(paginated; AWS itself paginates this call, and this tool follows pages
only up to `max_results`, since a single scope analysis can produce a
very large number of findings)

**Required IAM permission:** `ec2:GetNetworkInsightsAccessScopeAnalysisFindings`

**Input:**

```json
{ "region": "us-east-1", "network_insights_access_scope_analysis_id": "nisa-0123456789abcdef0", "max_results": 100 }
```

`network_insights_access_scope_analysis_id` is required. `max_results`
defaults to 100 and bounds how many findings this call returns in total.

**Output (`data`):** list of

```json
{
  "finding_id": "nisaf-0123456789abcdef0",
  "network_insights_access_scope_analysis_id": "nisa-0123456789abcdef0",
  "network_insights_access_scope_id": "nis-0123456789abcdef0",
  "finding_components": [
    { "component_id": "eni-0123456789abcdef0", "component_arn": "arn:aws:ec2:us-east-1:123456789012:network-interface/eni-0123456789abcdef0" },
    { "component_id": "sg-0123456789abcdef0", "component_arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0123456789abcdef0" }
  ],
  "tags": {},
  "account_id": "123456789012",
  "region": "us-east-1",
  "observed_at": "2026-08-27T18:00:00+00:00",
  "scope": "regional",
  "source_api": "ec2:GetNetworkInsightsAccessScopeAnalysisFindings",
  "collection_completeness": "complete",
  "redacted": false
}
```

Each `finding_components` entry is a bounded summary (component ID/ARN
only) of one path component, not AWS's full nested explanation payload
for that component -- this tool retrieves scope-analysis results, it does
not reproduce the console's full analysis view.

**Example request:**

```json
{ "tool": "aws_get_network_insights_access_scope_analysis_findings", "input": { "region": "us-east-1", "network_insights_access_scope_analysis_id": "nisa-0123456789abcdef0" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## Example IAM policy

Least-privilege policy for the identity aws-cloudops-mcp runs as
(`AWSCloudOpsMCPReadOnlyRole` in production). Grants exactly what every
Milestone 1 + Milestone 2 + Milestone 3 + Milestone 4 tool needs — nothing
else:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudOpsMCPReadOnlyEC2",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeRegions",
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcAttribute",
        "ec2:DescribeSubnets",
        "ec2:DescribeRouteTables",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeEgressOnlyInternetGateways",
        "ec2:DescribeNatGateways",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSecurityGroupRules",
        "ec2:DescribeNetworkAcls",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeVpcPeeringConnections",
        "ec2:DescribeManagedPrefixLists",
        "ec2:GetManagedPrefixListEntries",
        "ec2:DescribeVpcEndpoints",
        "ec2:DescribeVpcEndpointServices",
        "ec2:DescribeTransitGateways",
        "ec2:DescribeTransitGatewayAttachments",
        "ec2:DescribeTransitGatewayRouteTables",
        "ec2:GetTransitGatewayRouteTableAssociations",
        "ec2:GetTransitGatewayRouteTablePropagations",
        "ec2:SearchTransitGatewayRoutes",
        "ec2:DescribeVpnConnections",
        "ec2:DescribeCustomerGateways",
        "ec2:DescribeVpnGateways",
        "ec2:DescribeFlowLogs"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyELB",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyDirectConnect",
      "Effect": "Allow",
      "Action": [
        "directconnect:DescribeConnections",
        "directconnect:DescribeLags",
        "directconnect:DescribeVirtualInterfaces",
        "directconnect:DescribeDirectConnectGateways",
        "directconnect:DescribeDirectConnectGatewayAssociations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyRoute53",
      "Effect": "Allow",
      "Action": [
        "route53:ListHostedZones",
        "route53:GetHostedZone",
        "route53:ListResourceRecordSets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyRoute53Resolver",
      "Effect": "Allow",
      "Action": [
        "route53resolver:ListResolverEndpoints",
        "route53resolver:ListResolverEndpointIpAddresses",
        "route53resolver:ListResolverRules",
        "route53resolver:ListResolverRuleAssociations",
        "route53resolver:ListResolverQueryLogConfigs",
        "route53resolver:ListFirewallRuleGroups",
        "route53resolver:ListFirewallRuleGroupAssociations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyNetworkManager",
      "Effect": "Allow",
      "Action": [
        "networkmanager:ListCoreNetworks",
        "networkmanager:GetCoreNetwork",
        "networkmanager:GetCoreNetworkPolicy",
        "networkmanager:DescribeGlobalNetworks",
        "networkmanager:GetSites",
        "networkmanager:GetDevices",
        "networkmanager:GetLinks",
        "networkmanager:GetConnections",
        "networkmanager:GetTransitGatewayRegistrations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyNetworkInsights",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeNetworkInsightsPaths",
        "ec2:DescribeNetworkInsightsAnalyses",
        "ec2:DescribeNetworkInsightsAccessScopes",
        "ec2:DescribeNetworkInsightsAccessScopeAnalyses",
        "ec2:GetNetworkInsightsAccessScopeAnalysisFindings"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyCloudTrail",
      "Effect": "Allow",
      "Action": ["cloudtrail:LookupEvents"],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlyCloudWatch",
      "Effect": "Allow",
      "Action": ["cloudwatch:GetMetricStatistics"],
      "Resource": "*"
    },
    {
      "Sid": "AWSCloudOpsMCPReadOnlySTS",
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    }
  ]
}
```

Milestone 4's diagnostics engine (`aws_explain_network_path`,
`aws_find_network_risks`, `aws_get_network_health`) reuses the existing
Milestone 1-3 EC2/ELB `Describe*`/`Get*` actions already granted above --
it assembles its snapshot by calling the same service-layer functions in
`aws/networking.py`, `aws/gateways.py`, `aws/nat.py`, `aws/security.py`,
`aws/nacls.py`, `aws/enis.py`, `aws/peering.py`, `aws/endpoints.py`,
`aws/prefix_lists.py`, `aws/loadbalancers.py`, `aws/transit_gateway.py`,
and `aws/vpn.py`, so no new EC2/ELB action is required. The three new
statements above cover what genuinely is new: Reachability
Analyzer/Network Access Analyzer result retrieval
(`AWSCloudOpsMCPReadOnlyNetworkInsights`, used directly by the five
`aws_list_network_insights_*`/`aws_get_network_insights_*` tools and,
opt-in, by `aws_get_network_health`), recent network-configuration event
lookup (`AWSCloudOpsMCPReadOnlyCloudTrail`, opt-in via
`aws_get_network_health`'s `include_recent_changes`), and bounded NAT
gateway health metrics (`AWSCloudOpsMCPReadOnlyCloudWatch`, opt-in via
`aws_get_network_health`'s `include_metrics`).

`Describe*`/`Get*`/`List*`/`LookupEvents` actions do not support
resource-level restriction in IAM (they require `Resource: "*"`); scoping
happens by which *account/role* this policy is attached to, not by ARN.
**Do not** attach `AdministratorAccess`, `PowerUserAccess`, or a wildcard
`ec2:*`/`elasticloadbalancing:*`/`route53:*`/`route53resolver:*`/
`directconnect:*`/`networkmanager:*`/`cloudtrail:*`/`cloudwatch:*` policy
to this role. See [docs/security.md](security.md) for the full security
model.
