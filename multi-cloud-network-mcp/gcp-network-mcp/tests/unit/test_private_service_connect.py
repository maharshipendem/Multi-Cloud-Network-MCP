from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager

from gcp_network_mcp.gcp.private_service_connect import (
    list_psc_endpoints,
    list_service_attachments,
    normalize_service_attachment,
)


def test_normalize_service_attachment_maps_fields() -> None:
    attachment = compute_v1.ServiceAttachment(
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/serviceAttachments/svc-1"
        ),
        id=123,
        name="svc-1",
        region=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1",
        target_service=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/backendServices/producer-svc"
        ),
        connection_preference="ACCEPT_AUTOMATIC",
        producer_forwarding_rule=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/forwardingRules/producer-fr"
        ),
        nat_subnets=["nat-subnet-a", "nat-subnet-b"],
        enable_proxy_protocol=True,
        consumer_accept_lists=[
            compute_v1.ServiceAttachmentConsumerProjectLimit(
                project_id_or_num="consumer-project",
                connection_limit=10,
                network_url="https://www.googleapis.com/compute/v1/projects/consumer-project/global/networks/vpc-1",
            )
        ],
        consumer_reject_lists=["rejected-project"],
        connected_endpoints=[
            compute_v1.ServiceAttachmentConnectedEndpoint(
                endpoint="https://www.googleapis.com/compute/v1/projects/consumer-project/regions/us-central1/forwardingRules/consumer-fr",
                status="ACCEPTED",
                psc_connection_id=999,
                consumer_network="https://www.googleapis.com/compute/v1/projects/consumer-project/global/networks/vpc-1",
            )
        ],
        domain_names=["p.example.com."],
    )

    result = normalize_service_attachment(attachment, project_id=PROJECT_ID)

    assert result.name == "svc-1"
    assert result.id == "123"
    assert result.project_id == PROJECT_ID
    assert result.region == "us-central1"
    assert result.target_service == attachment.target_service
    assert result.connection_preference == "ACCEPT_AUTOMATIC"
    assert result.producer_forwarding_rule == attachment.producer_forwarding_rule
    assert result.nat_subnet_self_links == ["nat-subnet-a", "nat-subnet-b"]
    assert result.enable_proxy_protocol is True
    assert len(result.consumer_accept_lists) == 1
    assert result.consumer_accept_lists[0].project_id_or_num == "consumer-project"
    assert result.consumer_accept_lists[0].connection_limit == 10
    assert result.consumer_reject_lists == ["rejected-project"]
    assert len(result.connected_endpoints) == 1
    assert result.connected_endpoints[0].status == "ACCEPTED"
    assert result.connected_endpoints[0].psc_connection_id == "999"
    assert result.domain_names == ["p.example.com."]
    assert result.source_api == "ServiceAttachmentsClient.aggregated_list"


def test_normalize_service_attachment_defaults_on_empty_fields() -> None:
    attachment = compute_v1.ServiceAttachment(name="svc-empty")

    result = normalize_service_attachment(attachment, project_id=PROJECT_ID)

    assert result.self_link is None
    assert result.id is None
    assert result.region is None
    assert result.target_service is None
    assert result.nat_subnet_self_links == []
    assert result.consumer_accept_lists == []
    assert result.consumer_reject_lists == []
    assert result.connected_endpoints == []
    assert result.domain_names == []


def test_list_service_attachments_flattens_aggregated_scopes(client_factory) -> None:
    attachment = compute_v1.ServiceAttachment(
        name="svc-1",
        region=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1",
    )
    client_factory.service_attachments().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [attachment]}, items_field="service_attachments"
    )

    result = list_service_attachments(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    assert result.data[0].name == "svc-1"
    assert result.warnings == []


def test_list_service_attachments_empty(client_factory) -> None:
    client_factory.service_attachments().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="service_attachments"
    )

    result = list_service_attachments(client_factory, project_id=PROJECT_ID)

    assert result.data == []


def _forwarding_rule(
    *, name: str, target: str | None, region: str = "us-central1"
) -> compute_v1.ForwardingRule:
    return compute_v1.ForwardingRule(
        name=name,
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            f"{region}/forwardingRules/{name}"
        ),
        I_p_address="10.0.0.5",
        network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
        subnetwork=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            f"{region}/subnetworks/subnet-1"
        ),
        target=target,
        psc_connection_status="ACCEPTED" if target and "serviceAttachments" in target else None,
    )


def test_list_psc_endpoints_filters_out_non_psc_targets(client_factory) -> None:
    psc_rule = _forwarding_rule(
        name="psc-consumer-fr",
        target=(
            "https://www.googleapis.com/compute/v1/projects/producer-project/regions/"
            "us-central1/serviceAttachments/svc-1"
        ),
    )
    backend_rule = _forwarding_rule(
        name="ilb-fr",
        target=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/targetPools/pool-1"
        ),
    )
    no_target_rule = _forwarding_rule(name="no-target-fr", target=None)

    client_factory.forwarding_rules().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [psc_rule, backend_rule, no_target_rule]},
        items_field="forwarding_rules",
    )

    result = list_psc_endpoints(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    endpoint = result.data[0]
    assert endpoint.name == "psc-consumer-fr"
    assert endpoint.service_attachment_target == psc_rule.target
    assert endpoint.psc_connection_status == "ACCEPTED"
    assert endpoint.region == "us-central1"


def test_list_psc_endpoints_empty_when_no_forwarding_rules(client_factory) -> None:
    client_factory.forwarding_rules().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="forwarding_rules"
    )

    result = list_psc_endpoints(client_factory, project_id=PROJECT_ID)

    assert result.data == []


def test_list_psc_endpoints_empty_when_no_rule_targets_a_service_attachment(
    client_factory,
) -> None:
    backend_rule = _forwarding_rule(
        name="ilb-fr",
        target=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/targetPools/pool-1"
        ),
    )
    client_factory.forwarding_rules().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [backend_rule]}, items_field="forwarding_rules"
    )

    result = list_psc_endpoints(client_factory, project_id=PROJECT_ID)

    assert result.data == []
