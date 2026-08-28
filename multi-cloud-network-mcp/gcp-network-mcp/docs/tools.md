# Tools

Every tool returns the same envelope
(`{success, tool, project_id, data, metadata, error}` —
see `models/responses.py::ToolResponse`). `metadata.warnings`, when
present, is a list of `CollectionWarning` objects (`resource_type`,
`code`, `message`, `project_id`, `scope`) — a non-fatal issue collecting
one resource type (a disabled API, a permission gap, an unreachable
scope), never silently dropped.

Unless noted, `project_id` is optional on every tool and falls back to
`GCP_DEFAULT_PROJECT_ID`; the resolved project is validated against
`GCP_PROJECT_ALLOWLIST` (if configured) before any GCP API call is made.

| Tool | Parameters | Returns | Key IAM permissions |
|---|---|---|---|
| `gcp_get_caller_identity` | — | Credential type, resolved principal, ADC project, impersonation target. Never a token. | none (no GCP API call) |
| `gcp_list_permitted_projects` | — | Projects from `GCP_PROJECT_ALLOWLIST`, or discovered via `search_projects` if unset. | `resourcemanager.projects.get`/`.list` |
| `gcp_list_networks` | `project_id?` | VPC networks — auto/custom mode, MTU, peering names, firewall policy association. | `compute.networks.list` |
| `gcp_list_subnetworks` | `project_id?` | Subnetworks across every region — CIDR, secondary ranges, Private Google Access, flow logs. | `compute.subnetworks.list` |
| `gcp_list_routes` | `project_id?` | Routes with next-hop type derived from whichever `next_hop_*` field GCP populated. | `compute.routes.list` |
| `gcp_list_firewall_rules` | `project_id?`, `include_implied=true` | Firewall rules, plus (by default) GCP's two unlisted implied default rules per network. | `compute.firewalls.list` |
| `gcp_list_hierarchical_firewall_policies` | `parent_id` (required — org/folder ID) | Hierarchical Firewall Policies and their attachment associations. | `compute.firewallPolicies.list` (org/folder-scoped) |
| `gcp_list_network_firewall_policies` | `project_id?` | Network-scoped Firewall Policies and their attachment associations. | `compute.networkFirewallPolicies.list` |
| `gcp_list_instance_network_interfaces` | `project_id?` | Instance connectivity metadata across every zone — interfaces, addresses, tags, service accounts. | `compute.instances.list` |
| `gcp_list_addresses` | `project_id?` | Reserved IP addresses, regional and global. | `compute.addresses.list`, `compute.globalAddresses.list` |
| `gcp_list_forwarding_rules` | `project_id?` | Forwarding rules, regional and global. | `compute.forwardingRules.list`, `compute.globalForwardingRules.list` |
| `gcp_list_target_proxies` | `project_id?` | Target HTTP(S) proxies. | `compute.targetHttpProxies.list`, `compute.targetHttpsProxies.list` |
| `gcp_list_backend_services` | `project_id?`, `include_health=true` | Backend services, regional and global, with a per-backend-group health summary. | `compute.backendServices.list`, `compute.regionBackendServices.list` |
| `gcp_list_routers` | `project_id?` | Cloud Routers with embedded Cloud NAT gateway config. | `compute.routers.list` |
| `gcp_list_network_peerings` | `project_id?` | VPC Network Peerings (embedded on each network). | `compute.networks.list` |
| `gcp_get_shared_vpc_host_status` | `project_id?` | Whether a project is a Shared VPC host, service, or standalone project. | `compute.projects.get` |
| `gcp_list_shared_vpc_service_projects` | `project_id?` (host project) | Service projects attached to a Shared VPC host. | `compute.projects.get` |
| `gcp_get_vpc_topology` | `project_id?` | Deterministic node/edge graph joining networks, subnetworks, instance interfaces, routers, and peerings. | union of the above |

## Notes

- **`gcp_list_backend_services(include_health=false)`** skips the
  per-backend-group `get_health` fan-out entirely (bounded at
  `MAX_HEALTH_FANOUT` groups per service either way) — useful when only
  the inventory, not live health, is needed.
- **`gcp_list_firewall_rules(include_implied=false)`** returns only
  rules GCP's API actually lists, without the two synthetic implied
  default rules every network carries.
- **Hierarchical vs. network firewall policies** use the *same*
  underlying `FirewallPolicy` type — GCP has no distinct
  `NetworkFirewallPolicy` message — distinguished here only by which
  tool (and therefore which client, `FirewallPoliciesClient` vs.
  `NetworkFirewallPoliciesClient`) fetched it; each normalized record
  carries a `scope` field (`"hierarchical"`/`"network"`) so a caller
  never has to guess.
- **`gcp_get_vpc_topology`** is the one tool that fans out across
  several other tools' underlying collections in a single call — see
  [architecture.md#topology-assembly](architecture.md#topology-assembly).
