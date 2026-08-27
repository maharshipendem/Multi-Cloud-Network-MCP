# Tools Reference

All 19 tools are read-only. Every tool's MCP `meta` field carries
`{"cloud": "azure", "read_only": true, "resource_types": [...]}` so a
client (or a future multi-cloud federation layer) can confirm this
without importing this codebase — see `tools/capabilities.py`.

Every tool returns the same response envelope
(`models/responses.py::ToolResponse`):

```json
{
  "success": true,
  "tool": "azure_list_virtual_networks",
  "subscription_id": "11111111-1111-1111-1111-111111111111",
  "resource_group": null,
  "data": [ /* normalized resource records */ ],
  "metadata": { "request_id": "...", "count": 3 },
  "error": null
}
```

On failure, `success` is `false`, `data` is `null`, and `error` is
`{"type": "...", "message": "..."}` — see
[docs/security.md#error-handling](security.md#error-handling) for the
full list of `error.type` values.

Every tool that accepts an optional `subscription_id` falls back to
`AZURE_DEFAULT_SUBSCRIPTION_ID` when omitted, and the envelope's
`subscription_id` reports whichever one was actually used.

## Identity and context

### `azure_get_caller_identity`

Reports the credential type and configured tenant/subscription
context — never a token or secret. No parameters.

**RBAC:** none (reads only local configuration).

### `azure_list_subscriptions`

Lists subscriptions visible to the configured identity, filtered to
`AZURE_SUBSCRIPTION_ALLOWLIST` if set. No parameters.

**RBAC:** `Microsoft.Resources/subscriptions/read`

### `azure_list_tenants`

Lists tenants visible to the configured identity, filtered to
`AZURE_TENANT_ALLOWLIST` if set. No parameters.

**RBAC:** none beyond authentication (tenant listing is directory-level,
not RBAC-gated).

### `azure_list_locations`

Lists Azure regions available to a subscription.

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Resources/subscriptions/locations/read`

## Resource groups

### `azure_list_resource_groups`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `name_contains` | no | Case-insensitive substring filter on the resource group name |
| `only_with_network_resources` | no | Keep only groups containing a `Microsoft.Network` resource (bounded fan-out; see `MAX_FANOUT_CALLS`) |

**RBAC:** `Microsoft.Resources/subscriptions/resourceGroups/read`,
`Microsoft.Resources/subscriptions/resourceGroups/resources/read`
(only needed when `only_with_network_resources` is used)

## Virtual networks and subnets

### `azure_list_virtual_networks`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/virtualNetworks/read`

### `azure_list_subnets`

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the virtual network |
| `virtual_network_name` | yes | Name of the virtual network |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Network/virtualNetworks/subnets/read`

## Route tables

### `azure_list_route_tables`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/routeTables/read`

### `azure_get_effective_route_table`

The route table Azure actually applies to a network interface — merged
from system routes, user-defined routes, and BGP-propagated routes.

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the network interface |
| `network_interface_name` | yes | Name of the network interface |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Network/networkInterfaces/effectiveRouteTable/action`
(a read-only computation despite the `/action` permission shape — see
[docs/security.md](security.md#why-begin_-needs-two-narrow-exceptions))

## Network security groups

### `azure_list_network_security_groups`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/networkSecurityGroups/read`

### `azure_list_security_rules`

The custom rules configured on one NSG (not Azure's built-in defaults —
those come back embedded on the NSG record itself, in
`default_security_rules`).

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the NSG |
| `network_security_group_name` | yes | Name of the network security group |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Network/networkSecurityGroups/securityRules/read`

### `azure_get_effective_network_security_groups`

The NSGs and rules Azure actually applies to a network interface, across
subnet- and NIC-level associations, with Application Security Group
references expanded into concrete IP prefixes.

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the network interface |
| `network_interface_name` | yes | Name of the network interface |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Network/networkInterfaces/effectiveNetworkSecurityGroups/action`
(read-only for the same reason as the effective route table action above)

## Network interfaces and public IPs

### `azure_list_network_interfaces`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/networkInterfaces/read`

### `azure_list_public_ip_addresses`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/publicIPAddresses/read`

## Peering, NAT, and load balancing

### `azure_list_virtual_network_peerings`

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the virtual network |
| `virtual_network_name` | yes | Name of the virtual network |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** `Microsoft.Network/virtualNetworks/virtualNetworkPeerings/read`

### `azure_list_nat_gateways`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/natGateways/read`

### `azure_list_load_balancers`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/loadBalancers/read`

### `azure_list_application_gateways`

| Parameter | Required | Description |
|---|---|---|
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |
| `resource_group` | no | Omit to list across the whole subscription |

**RBAC:** `Microsoft.Network/applicationGateways/read`

## Topology

### `azure_get_vnet_topology`

A deterministic topology graph for one virtual network: typed nodes
(`virtual_network`, `subnet`, `network_security_group`, `route_table`,
`nat_gateway`, `network_interface`, `public_ip_address`,
`virtual_network_peering`) and typed edges with `evidence`, scoped to the
VNet's own resource group. See
[docs/architecture.md#topology-assembly-azure_get_vnet_topology](architecture.md#topology-assembly-azure_get_vnet_topology).

| Parameter | Required | Description |
|---|---|---|
| `resource_group` | yes | Resource group containing the virtual network |
| `virtual_network_name` | yes | Name of the virtual network to map |
| `subscription_id` | no | Falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID` |

**RBAC:** every read action listed above for virtual networks, subnets,
NSGs, route tables, NAT gateways, network interfaces, public IPs, and
peerings (this tool calls all of those service functions internally).

## RBAC actions by tool

The full set of actions every tool above needs, deduplicated, is captured
in [`azure-custom-role.json`](../azure-custom-role.json) — assign that
role (or the built-in `Reader` role) to the identity this server runs as.
See [docs/security.md#azure-rbac-least-privilege](security.md#azure-rbac-least-privilege).
