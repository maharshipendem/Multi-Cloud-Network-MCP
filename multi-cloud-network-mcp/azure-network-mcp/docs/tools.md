# Tools Reference

All 67 tools are read-only (19 from Milestone 5, 48 from Milestone 6 —
see [Milestone 6 tools](#milestone-6-tools) below). Every tool's MCP
`meta` field carries
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

## Milestone 6 tools

All parameters named `subscription_id` fall back to
`AZURE_DEFAULT_SUBSCRIPTION_ID` when omitted, exactly as in Milestone 5.
`resource_group` is optional (omit to list across the whole subscription)
unless marked **required** below. Full per-field schemas are in each
tool's own docstring (`src/azure_network_mcp/tools/*.py`) — this table is
a navigation aid, not a schema replacement.

### Virtual WAN / Virtual Hub / Route Server

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_list_virtual_wans` | List Virtual WANs | — |
| `azure_list_virtual_hubs` | List Virtual Hubs (a hub with `sku="Standard"` and no vWAN is a standalone Route Server) | — |
| `azure_list_hub_route_tables` | One hub's route tables and routes | `resource_group`\*, `virtual_hub_name`\* |
| `azure_list_hub_virtual_network_connections` | One hub's VNet connections | `resource_group`\*, `virtual_hub_name`\* |
| `azure_list_virtual_hub_bgp_connections` | One hub's BGP peers | `resource_group`\*, `virtual_hub_name`\* |
| `azure_get_hub_bgp_connection_routes` | Advertised/learned routes for one hub BGP connection (read-only `begin_*`) | `resource_group`\*, `virtual_hub_name`\*, `connection_name`\*, `direction`\* |
| `azure_list_route_maps` | One hub's routing-intent policies | `resource_group`\*, `virtual_hub_name`\* |
| `azure_list_route_servers` | Standalone Route Servers (filtered Virtual Hubs) | — |
| `azure_list_route_server_peers` | One Route Server's BGP peers | `resource_group`\*, `route_server_name`\* |
| `azure_get_route_server_peer_routes` | Advertised/learned routes for one Route Server peer (read-only `begin_*`) | `resource_group`\*, `route_server_name`\*, `peer_connection_name`\*, `direction`\* |

### VPN (vWAN-scoped and classic)

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_list_vpn_gateways` | List vWAN VPN gateways | — |
| `azure_list_vpn_sites` | List VPN sites (never includes `site_key`) | — |
| `azure_list_vpn_connections` | One vWAN gateway's site connections (never includes `shared_key`) | `resource_group`\*, `vpn_gateway_name`\* |
| `azure_list_virtual_network_gateways` | Classic (non-vWAN) VPN/ExpressRoute gateways | `resource_group`\* |
| `azure_list_local_network_gateways` | Classic on-premises gateway definitions | `resource_group`\* |
| `azure_list_virtual_network_gateway_connections` | Classic S2S/VNet-to-VNet/ExpressRoute connections (never includes `authorization_key`/`shared_key`) | `resource_group`\* |
| `azure_get_bgp_peer_status` | Live BGP session state for a classic gateway's peers (read-only `begin_*`) | `resource_group`\*, `virtual_network_gateway_name`\* |

### ExpressRoute

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_list_express_route_circuits` | List circuits (never includes `authorization_key`/`service_key`) | — |
| `azure_list_express_route_circuit_peerings` | One circuit's peerings (never includes `shared_key`) | `resource_group`\*, `circuit_name`\* |
| `azure_list_express_route_circuit_connections` | One peering's Global Reach connections (never includes `authorization_key`) | `resource_group`\*, `circuit_name`\*, `peering_name`\* |
| `azure_list_express_route_gateways` | List vWAN ExpressRoute gateways | — |
| `azure_list_express_route_connections` | One gateway's circuit-peering connections (never includes `authorization_key`) | `resource_group`\*, `express_route_gateway_name`\* |
| `azure_list_express_route_ports` | List ExpressRoute Direct ports | — |
| `azure_list_express_route_links` | One port's physical fiber links | `resource_group`\*, `port_name`\* |

### Private Link / Private DNS / DNS Resolver

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_list_private_endpoints` | List Private Endpoints | — |
| `azure_list_private_link_services` | List Private Link Services | — |
| `azure_list_service_endpoint_policies` | List service endpoint policies | — |
| `azure_list_private_dns_zones` | List Private DNS zones | — |
| `azure_list_private_dns_virtual_network_links` | One zone's VNet links | `resource_group`\*, `zone_name`\* |
| `azure_list_private_dns_record_sets` | One zone's record sets (bounded summary) | `resource_group`\*, `zone_name`\* |
| `azure_list_dns_resolvers` | List Azure DNS Resolvers | — |
| `azure_list_dns_resolver_inbound_endpoints` | One resolver's inbound endpoints | `resource_group`\*, `dns_resolver_name`\* |
| `azure_list_dns_resolver_outbound_endpoints` | One resolver's outbound endpoints | `resource_group`\*, `dns_resolver_name`\* |
| `azure_list_dns_forwarding_rulesets` | List DNS forwarding rulesets | — |
| `azure_list_dns_forwarding_rules` | One ruleset's rules | `resource_group`\*, `ruleset_name`\* |
| `azure_list_dns_forwarding_ruleset_virtual_network_links` | One ruleset's VNet links | `resource_group`\*, `ruleset_name`\* |

### Azure Firewall / Network Watcher / Azure Monitor

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_list_azure_firewalls` | List Azure Firewalls | — |
| `azure_list_firewall_policies` | List firewall policies | — |
| `azure_list_firewall_policy_rule_collection_groups` | One policy's rule collection groups (rule counts only) | `resource_group`\*, `firewall_policy_name`\* |
| `azure_list_network_watchers` | List Network Watcher instances | — |
| `azure_get_network_topology` | Azure's own native topology for one resource group (distinct from `azure_get_hybrid_topology`) | `resource_group`\*, `network_watcher_name`\*, `target_resource_group`\* |
| `azure_list_connection_monitors` | One watcher's existing connection monitors (config + last status, never created/started) | `resource_group`\*, `network_watcher_name`\* |
| `azure_list_flow_logs` | One watcher's VNet/NSG flow log configurations | `resource_group`\*, `network_watcher_name`\* |
| `azure_get_network_metrics` | Bounded Azure Monitor metrics for one resource (fixed catalog, 24h lookback) | `resource_id`\* |

### Diagnostics (deterministic engine)

See [docs/rule_catalog.md](rule_catalog.md) for exactly what each
underlying rule checks, and
[docs/security.md#deterministic-evidence-bound-diagnostics](security.md#deterministic-evidence-bound-diagnostics)
for the guarantees behind every `Finding`.

| Tool | Purpose | Key parameters |
|---|---|---|
| `azure_get_hybrid_topology` | Resource-group-scoped hybrid connectivity graph (VNets, hubs, VPN, ExpressRoute) | `resource_group`\* |
| `azure_explain_network_path` | Route (`ROUTE-001`) + NSG (`SEC-001`) evaluation for one source NIC → destination | `resource_group`\*, `network_interface_name`\*, `destination_ip`\*, `destination_port`\*, `protocol` |
| `azure_find_network_risks` | Whole-resource-group risk scan (`EXPOSE-001`, `CONSIST-001`, `CONSIST-002`) | `resource_group`\*, `min_severity` |
| `azure_get_network_health` | Degraded resources/connections + opt-in bounded metrics | `resource_group`\*, `include_metrics` |

\* Required parameter.

## RBAC actions by tool

The full set of actions every tool above needs, deduplicated, is captured
in [`azure-custom-role.json`](../azure-custom-role.json) — assign that
role (or the built-in `Reader` role) to the identity this server runs as.
See [docs/security.md#azure-rbac-least-privilege](security.md#azure-rbac-least-privilege).
