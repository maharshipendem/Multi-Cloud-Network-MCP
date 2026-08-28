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

### Milestone 8: hybrid networking, DNS, observability, diagnostics

| Tool | Parameters | Returns | Key IAM permissions |
|---|---|---|---|
| `gcp_get_router_bgp_status` | `region`, `router_name`, `project_id?` | Per-peer BGP session state, learned-route counts, router's own best-route selections. | `compute.routers.getRouterStatus` |
| `gcp_list_ncc_hubs` | `project_id?` | Network Connectivity Center hubs, with summed spoke counts by state. | `networkconnectivity.hubs.list` |
| `gcp_list_ncc_spokes` | `project_id?` | NCC spokes across every location, with GCP's own inactive-state reasons. | `networkconnectivity.spokes.list` |
| `gcp_list_ncc_groups` | `hub_name`, `project_id?` | NCC groups under one hub. | `networkconnectivity.groups.list` |
| `gcp_list_ncc_route_tables` | `hub_name`, `project_id?` | NCC route tables under one hub. | `networkconnectivity.routeTables.list` |
| `gcp_list_ncc_routes` | `route_table_name`, `project_id?` | NCC routes in one route table, with next-hop URIs. | `networkconnectivity.routes.list` |
| `gcp_get_ncc_hub_status` | `hub_name` | Aggregated per-status-count rows, including PSC propagation status. | `networkconnectivity.hubs.getStatus` |
| `gcp_list_vpn_gateways` | `project_id?` | HA VPN gateways and their interfaces. | `compute.vpnGateways.list` |
| `gcp_get_vpn_gateway_status` | `region`, `gateway_name`, `project_id?` | Per-tunnel HA requirement/redundancy status. | `compute.vpnGateways.getStatus` |
| `gcp_list_vpn_tunnels` | `project_id?` | VPN tunnels — status, peer gateway, routing. Never carries the shared secret. | `compute.vpnTunnels.list` |
| `gcp_list_external_vpn_gateways` | `project_id?` | Classic VPN's on-premises/other-cloud peer gateway definitions. | `compute.externalVpnGateways.list` |
| `gcp_list_interconnects` | `project_id?` | Dedicated/Partner Interconnect circuits and their operational status. | `compute.interconnects.list` |
| `gcp_get_interconnect_diagnostics` | `interconnect_name`, `project_id?` | Live per-link diagnostics — operational status, optical power. | `compute.interconnects.getDiagnostics` |
| `gcp_list_interconnect_attachments` | `project_id?` | VLAN attachments — provisioning/operational state. Never carries the pairing key. | `compute.interconnectAttachments.list` |
| `gcp_list_interconnect_locations` | `project_id?` | Interconnect-eligible colocation facilities visible to this project. | `compute.interconnectLocations.list` |
| `gcp_list_service_attachments` | `project_id?` | Private Service Connect published services (producer side), every region. | `compute.serviceAttachments.list` |
| `gcp_list_psc_endpoints` | `project_id?` | PSC consumer endpoints (forwarding rules targeting a service attachment). | `compute.forwardingRules.list`, `compute.globalForwardingRules.list` |
| `gcp_list_private_service_access_ranges` | `project_id?` | Allocated ranges for private services access (VPC peering to Google-managed services). | `compute.globalAddresses.list` |
| `gcp_list_dns_zones` | `project_id?` | Cloud DNS managed zones and their assigned name servers. | `dns.managedZones.list` |
| `gcp_list_dns_zone_records` | `zone_name`, `project_id?` | Record set summaries for one managed zone. | `dns.resourceRecordSets.list` |
| `gcp_list_packet_mirroring_policies` | `project_id?` | Packet Mirroring policy configuration only — never mirrored packet content. | `compute.packetMirrorings.list` |
| `gcp_list_vpc_flow_logs_configs` | `project_id?` | VPC Flow Logs configuration (subnet/interconnect-attachment/VPN-tunnel scoped). | `networkmanagement.vpcFlowLogsConfigs.list` |
| `gcp_list_connectivity_tests` | `project_id?` | Existing Network Management Connectivity Tests and their last-computed result. Never creates one. | `networkmanagement.connectivitytests.list` |
| `gcp_get_connectivity_test` | `test_name`, `project_id?` | One Connectivity Test's full trace/reachability detail. | `networkmanagement.connectivitytests.get` |
| `gcp_query_logs` | `filter_expr` (required), `project_id?`, `hours?` | Bounded Cloud Logging read. Requires an explicit filter; capped at `Settings.max_log_entries`/`max_log_query_window_hours` regardless of input. | `logging.logEntries.list` |
| `gcp_query_metrics` | `filter_expr` (required), `project_id?`, `hours?` | Bounded Cloud Monitoring read. Capped at `Settings.max_time_series_points`/`max_metric_query_window_hours` regardless of input. | `monitoring.timeSeries.list` |
| `gcp_get_hybrid_topology` | `project_id?`, `hierarchical_firewall_parent_id?` | Node/edge graph spanning VPN/Interconnect/NCC on top of the M7 VPC topology. | union of the diagnostics snapshot's inputs |
| `gcp_explain_network_path` | `network_self_link`, `destination_ip`, `protocol="tcp"`, `destination_port?`, `project_id?`, `hierarchical_firewall_parent_id?` | Deterministic route + firewall (network + hierarchical) evaluation for one path. `overall_verdict` is `allowed`/`blocked`/`partially_evaluated`. | union of the diagnostics snapshot's inputs |
| `gcp_find_network_risks` | `project_id?`, `hierarchical_firewall_parent_id?` | Every finding from all 12 registered rules, including `confidence="indeterminate"` ones. | union of the diagnostics snapshot's inputs |
| `gcp_get_network_health` | `project_id?`, `hierarchical_firewall_parent_id?` | Finding counts by severity, resource inventory, overall status. | union of the diagnostics snapshot's inputs |

See [rule_catalog.md](rule_catalog.md) for what each of the 12 diagnostic
rules checks, and [limitations.md](limitations.md) for what the four
diagnostics tools above cannot see (DNS forwarding chains, private
services access *connections*, Performance Dashboard data).

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
- **`gcp_list_vpn_tunnels`/`gcp_list_interconnect_attachments`** never
  return `shared_secret`/`shared_secret_hash`/`pairing_key` — the
  normalizer never reads those fields from the raw SDK response.
  `redacted: true` on every returned record documents this, it is not a
  toggle.
- **`gcp_query_logs`/`gcp_query_metrics`** are the only two tools that
  require an explicit parameter beyond `project_id` (`filter_expr`) and
  the only two bounded by `Settings` regardless of what a caller
  requests — see [security.md](security.md#bounded-observability-reads).
- **The four diagnostics tools** (`gcp_get_hybrid_topology`,
  `gcp_explain_network_path`, `gcp_find_network_risks`,
  `gcp_get_network_health`) each collect one fresh
  `HybridNetworkSnapshot` internally — see
  [architecture.md#diagnostics-engine](architecture.md#diagnostics-engine).
  None of them ever creates, reruns, or modifies a Connectivity Test,
  router, VPN, firewall rule, or DNS record — every diagnosis is computed
  from already-collected read-only state.
