"""Every canonical model round-trips through JSON without loss:
``model_validate_json(model.model_dump_json())`` reproduces an
identical object, for every one of the 21 resource types plus the
topology/diagnostics/envelope/capability models."""

from __future__ import annotations

from multicloud_network_mcp.contracts.models import (
    Address,
    Attachment,
    CloudScope,
    CollectionWarning,
    DnsResolver,
    DnsRule,
    DnsZone,
    Endpoint,
    Finding,
    FirewallRule,
    Gateway,
    Interconnect,
    InterconnectAttachment,
    LoadBalancer,
    Network,
    NetworkInterface,
    ObservabilityReference,
    PartialResultMetadata,
    PathExplanation,
    Peering,
    Provider,
    ProviderCapabilityManifest,
    ResourceTypeSupport,
    ResponseEnvelope,
    Route,
    RouteTable,
    Subnet,
    TopologyEdge,
    TopologyGraph,
    TopologyNode,
    TransitHub,
    VpnGateway,
    VpnTunnel,
)
from multicloud_network_mcp.contracts.models.enums import NodeKind
from multicloud_network_mcp.contracts.urn import build_urn

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _urn(native_id: str) -> str:
    return build_urn(
        provider="aws",
        scope={"account_id": "1", "region": "us-east-1"},
        resource_type="network",
        native_id=native_id,
    )


def _roundtrip(model) -> None:
    dumped = model.model_dump_json()
    reloaded = type(model).model_validate_json(dumped)
    assert reloaded == model
    # And the dict form round-trips identically too.
    assert type(model).model_validate(model.model_dump()) == model


def _base_kwargs(scope: CloudScope, native_id: str, resource_type: str) -> dict:
    return {
        "urn": _urn(native_id),
        "native_id": native_id,
        "resource_type": resource_type,
        "provider": scope.provider,
        "scope": scope,
        "observed_at": FRESHNESS,
    }


def test_network_roundtrip(aws_scope) -> None:
    _roundtrip(
        Network(
            **_base_kwargs(aws_scope, "vpc-1", "network"),
            cidr_blocks=["10.0.0.0/16"],
            state="available",
        )
    )


def test_subnet_roundtrip(aws_scope) -> None:
    _roundtrip(
        Subnet(
            **_base_kwargs(aws_scope, "subnet-1", "subnet"),
            cidr_block="10.0.1.0/24",
            network_urn=_urn("vpc-1"),
            state="available",
        )
    )


def test_network_interface_roundtrip(aws_scope) -> None:
    _roundtrip(
        NetworkInterface(
            **_base_kwargs(aws_scope, "eni-1", "network-interface"),
            private_ip_addresses=["10.0.1.5"],
            state="in-use",
        )
    )


def test_address_roundtrip(aws_scope) -> None:
    _roundtrip(
        Address(
            **_base_kwargs(aws_scope, "eipalloc-1", "address"),
            ip_address="203.0.113.5",
            ip_version="ipv4",
            allocation_method="static",
            is_public=True,
        )
    )


def test_route_table_roundtrip(aws_scope) -> None:
    _roundtrip(
        RouteTable(**_base_kwargs(aws_scope, "rtb-1", "route-table"), network_urn=_urn("vpc-1"))
    )


def test_route_roundtrip(aws_scope) -> None:
    _roundtrip(
        Route(
            **_base_kwargs(aws_scope, "rtb-1-route-1", "route"),
            destination_cidr="0.0.0.0/0",
            next_hop_type="internet-gateway",
            origin="system",
            state="active",
        )
    )


def test_firewall_rule_roundtrip(aws_scope) -> None:
    _roundtrip(
        FirewallRule(
            **_base_kwargs(aws_scope, "sgr-1", "firewall-rule"),
            direction="ingress",
            action="allow",
            protocol="tcp",
            port_range="22",
            source_ranges=["10.0.0.0/8"],
            stateful=True,
        )
    )


def test_gateway_roundtrip(aws_scope) -> None:
    _roundtrip(
        Gateway(
            **_base_kwargs(aws_scope, "igw-1", "gateway"), gateway_type="internet", state="attached"
        )
    )


def test_transit_hub_roundtrip(aws_scope) -> None:
    _roundtrip(TransitHub(**_base_kwargs(aws_scope, "tgw-1", "transit-hub"), state="available"))


def test_attachment_roundtrip(aws_scope) -> None:
    _roundtrip(
        Attachment(
            **_base_kwargs(aws_scope, "tgw-attach-1", "attachment"),
            transit_hub_urn=_urn("tgw-1"),
            attached_resource_type="network",
            state="available",
        )
    )


def test_peering_roundtrip(aws_scope) -> None:
    _roundtrip(
        Peering(
            **_base_kwargs(aws_scope, "pcx-1", "peering"),
            local_network_urn=_urn("vpc-1"),
            state="active",
        )
    )


def test_vpn_gateway_roundtrip(aws_scope) -> None:
    _roundtrip(
        VpnGateway(
            **_base_kwargs(aws_scope, "vgw-1", "vpn-gateway"), is_ha=False, state="available"
        )
    )


def test_vpn_tunnel_roundtrip(aws_scope) -> None:
    tunnel = VpnTunnel(
        **_base_kwargs(aws_scope, "vpn-1-tunnel-1", "vpn-tunnel"),
        gateway_urn=_urn("vgw-1"),
        status="up",
        native_status="UP",
    )
    assert tunnel.redacted is True
    _roundtrip(tunnel)


def test_interconnect_roundtrip(aws_scope) -> None:
    ic = Interconnect(**_base_kwargs(aws_scope, "dxcon-1", "interconnect"), state="available")
    assert ic.redacted is True
    _roundtrip(ic)


def test_interconnect_attachment_roundtrip(aws_scope) -> None:
    attach = InterconnectAttachment(
        **_base_kwargs(aws_scope, "dxvif-1", "interconnect-attachment"),
        interconnect_urn=_urn("dxcon-1"),
        state="available",
    )
    assert attach.redacted is True
    _roundtrip(attach)


def test_dns_zone_roundtrip(aws_scope) -> None:
    _roundtrip(
        DnsZone(
            **_base_kwargs(aws_scope, "Z123", "dns-zone"), dns_name="example.com.", is_private=False
        )
    )


def test_dns_resolver_roundtrip(azure_scope) -> None:
    _roundtrip(
        DnsResolver(**_base_kwargs(azure_scope, "resolver-1", "dns-resolver"), state="available")
    )


def test_dns_rule_roundtrip(azure_scope) -> None:
    _roundtrip(DnsRule(**_base_kwargs(azure_scope, "rule-1", "dns-rule"), state="available"))


def test_load_balancer_roundtrip(aws_scope) -> None:
    _roundtrip(
        LoadBalancer(
            **_base_kwargs(aws_scope, "lb-1", "load-balancer"),
            scheme="external",
            listener_ports=[443],
            state="active",
        )
    )


def test_endpoint_roundtrip(aws_scope) -> None:
    _roundtrip(
        Endpoint(
            **_base_kwargs(aws_scope, "vpce-1", "endpoint"),
            endpoint_type="consumer",
            state="available",
        )
    )


def test_observability_reference_roundtrip(aws_scope) -> None:
    _roundtrip(
        ObservabilityReference(
            **_base_kwargs(aws_scope, "fl-1", "observability-reference"),
            observability_type="flow-log",
        )
    )


def test_topology_graph_roundtrip(aws_scope) -> None:
    node = TopologyNode(
        urn=_urn("vpc-1"),
        native_id="vpc-1",
        kind=NodeKind.RESOURCE,
        resource_type="network",
        label="prod-vpc",
        scope=aws_scope,
    )
    edge = TopologyEdge(
        source_urn=_urn("subnet-1"),
        target_urn=_urn("vpc-1"),
        relationship="member_of",
        evidence=[{"source": "subnet:subnet-1", "detail": "vpc_id=vpc-1"}],
    )
    _roundtrip(TopologyGraph(scope=aws_scope, nodes=[node], edges=[edge]))


def test_finding_roundtrip() -> None:
    _roundtrip(
        Finding(
            rule_id="TEST-001",
            rule_version="1.0.0",
            provider="aws",
            severity="high",
            confidence="high",
            summary="test finding",
            freshness=FRESHNESS,
        )
    )


def test_path_explanation_roundtrip() -> None:
    _roundtrip(
        PathExplanation(
            provider="aws",
            source="10.0.1.5",
            destination="10.0.2.5",
            overall_verdict="allowed",
            freshness=FRESHNESS,
        )
    )


def test_response_envelope_roundtrip(aws_scope) -> None:
    _roundtrip(
        ResponseEnvelope.ok(
            tool="aws_export_normalized_topology",
            contract_version="1.0.0",
            request_id="req-1",
            scope=aws_scope,
            data={"nodes": []},
        )
    )


def test_response_envelope_fail_roundtrip(aws_scope) -> None:
    from multicloud_network_mcp.contracts.models import ErrorDetail

    _roundtrip(
        ResponseEnvelope.fail(
            tool="aws_export_normalized_topology",
            contract_version="1.0.0",
            request_id="req-1",
            scope=aws_scope,
            error=ErrorDetail(type="AuthorizationError", message="denied"),
        )
    )


def test_collection_warning_roundtrip() -> None:
    _roundtrip(CollectionWarning(resource_type="network", code="COLLECTION_FAILED", message="boom"))


def test_partial_result_metadata_roundtrip() -> None:
    _roundtrip(
        PartialResultMetadata(
            completeness="partial",
            warnings=[CollectionWarning(resource_type="network", code="X", message="y")],
        )
    )


def test_provider_capability_manifest_roundtrip() -> None:
    _roundtrip(
        ProviderCapabilityManifest(
            provider=Provider.AWS,
            adapter_package="aws-cloudops-mcp",
            adapter_version="0.4.0",
            contract_version="1.0.0",
            min_supported_contract_version="1.0.0",
            urn_grammar_version=1,
            supported_resource_types=[
                ResourceTypeSupport(
                    resource_type="network", export_tool="aws_export_normalized_topology"
                )
            ],
            supports_topology=True,
            generated_at=FRESHNESS,
        )
    )
