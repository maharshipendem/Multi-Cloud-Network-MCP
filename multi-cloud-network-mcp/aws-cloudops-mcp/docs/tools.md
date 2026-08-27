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

## Example IAM policy

Least-privilege policy for the identity aws-cloudops-mcp runs as
(`AWSCloudOpsMCPReadOnlyRole` in production). Grants exactly what every
Milestone 1 + Milestone 2 tool needs — nothing else:

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
        "ec2:DescribeVpcEndpointServices"
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
      "Sid": "AWSCloudOpsMCPReadOnlySTS",
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    }
  ]
}
```

`Describe*`/`Get*` EC2 and ELB actions do not support resource-level
restriction in IAM (they require `Resource: "*"`); scoping happens by
which *account/role* this policy is attached to, not by ARN. **Do not**
attach `AdministratorAccess`, `PowerUserAccess`, or a wildcard `ec2:*`/
`elasticloadbalancing:*` policy to this role. See
[docs/security.md](security.md) for the full security model.
