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

`target_type` is one of `gateway`, `nat_gateway`, `transit_gateway`,
`vpc_peering_connection`, `network_interface`,
`egress_only_internet_gateway`, `instance`, `local_gateway`,
`carrier_gateway`, `core_network`, or `null` for the implicit `local` route.

**Example request:**

```json
{ "tool": "aws_list_route_tables", "input": { "region": "us-east-1" } }
```

**Example response:** see the `data` shape above, wrapped in the standard
envelope.

---

## Example IAM policy

Least-privilege policy for the identity aws-cloudops-mcp runs as
(`AWSCloudOpsMCPReadOnlyRole` in production). Grants exactly what
Milestone 1's five tools need — nothing else:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudOpsMCPReadOnly",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "ec2:DescribeRegions",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeRouteTables"
      ],
      "Resource": "*"
    }
  ]
}
```

`Describe*`/`Get*` EC2 actions do not support resource-level restriction in
IAM (they require `Resource: "*"`); scoping happens by which *account/role*
this policy is attached to, not by ARN. **Do not** attach
`AdministratorAccess`, `PowerUserAccess`, or a wildcard `ec2:*` policy to
this role. See [docs/security.md](security.md) for the full security model.
