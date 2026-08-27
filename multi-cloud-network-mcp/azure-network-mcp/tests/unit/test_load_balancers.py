from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.load_balancers import list_application_gateways, list_load_balancers


def _load_balancer() -> SimpleNamespace:
    return SimpleNamespace(
        id="lb-id",
        name="lb-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        sku=SimpleNamespace(name="Standard", tier="Regional"),
        frontend_ip_configurations=[
            SimpleNamespace(
                name="fe-1",
                private_ip_address=None,
                public_ip_address=SimpleNamespace(id="pip-1"),
                subnet=None,
            )
        ],
        backend_address_pools=[
            SimpleNamespace(name="bap-1", backend_ip_configurations=[SimpleNamespace(id="ipc-1")])
        ],
        load_balancing_rules=[
            SimpleNamespace(
                name="rule-1",
                protocol="Tcp",
                frontend_port=443,
                backend_port=443,
                frontend_ip_configuration=SimpleNamespace(id="fe-1-id"),
                backend_address_pool=SimpleNamespace(id="bap-1-id"),
            )
        ],
        probes=[
            SimpleNamespace(name="probe-1", protocol="Https", port=443, request_path="/healthz")
        ],
    )


def _app_gateway(*, use_http_listeners: bool) -> SimpleNamespace:
    listener = SimpleNamespace(
        name="listener-1",
        protocol="Https",
        frontend_ip_configuration=SimpleNamespace(id="fe-1"),
        frontend_port=SimpleNamespace(id="port-1"),
    )
    return SimpleNamespace(
        id="agw-id",
        name="agw-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        sku=SimpleNamespace(name="WAF_v2", tier="WAF_v2", capacity=2),
        operational_state="Running",
        http_listeners=[listener] if use_http_listeners else None,
        listeners=[] if use_http_listeners else [listener],
        backend_address_pools=[SimpleNamespace(name="pool-1")],
    )


def test_list_load_balancers_normalizes_rules_pools_and_probes(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.load_balancers.list_all.return_value = make_pageable([_load_balancer()])

    result = list_load_balancers(client_factory, subscription_id=SUBSCRIPTION_ID)

    lb = result[0]
    assert lb.sku_name == "Standard"
    assert lb.frontend_ip_configurations[0].public_ip_address_id == "pip-1"
    assert lb.backend_address_pools[0].backend_ip_configuration_ids == ["ipc-1"]
    assert lb.load_balancing_rules[0].frontend_port == 443
    assert lb.probes[0].request_path == "/healthz"


def test_list_application_gateways_distinguishes_provisioning_and_operational_state(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.application_gateways.list_all.return_value = make_pageable(
        [_app_gateway(use_http_listeners=True)]
    )

    result = list_application_gateways(client_factory, subscription_id=SUBSCRIPTION_ID)

    gw = result[0]
    assert gw.provisioning_state == "Succeeded"
    assert gw.operational_state == "Running"
    assert gw.listeners[0].name == "listener-1"


def test_list_application_gateways_falls_back_to_listeners_field(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.application_gateways.list_all.return_value = make_pageable(
        [_app_gateway(use_http_listeners=False)]
    )

    result = list_application_gateways(client_factory, subscription_id=SUBSCRIPTION_ID)

    assert result[0].listeners[0].name == "listener-1"
