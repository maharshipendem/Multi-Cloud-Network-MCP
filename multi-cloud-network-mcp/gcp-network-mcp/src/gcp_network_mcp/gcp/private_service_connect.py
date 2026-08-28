"""Service-layer functions for Private Service Connect (PSC): published
services (producer side, ``ServiceAttachmentsClient``) and consumer
endpoints (derived from ``gcp.load_balancing.list_forwarding_rules``'s
output, not a separate collection path -- see models module docstring)."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.load_balancing import list_forwarding_rules
from gcp_network_mcp.gcp.pagination import paginate_aggregated
from gcp_network_mcp.models.private_service_connect import (
    PscEndpoint,
    ServiceAttachment,
    ServiceAttachmentConnectedEndpoint,
    ServiceAttachmentConsumerAcceptList,
)

# A forwarding rule's `target` is a PSC consumer endpoint when it points
# at a service attachment, identified by this URL path segment.
_SERVICE_ATTACHMENT_PATH_MARKER = "/serviceAttachments/"


def normalize_service_attachment(
    attachment: compute_v1.ServiceAttachment, *, project_id: str
) -> ServiceAttachment:
    return ServiceAttachment(
        self_link=attachment.self_link or None,
        id=str(attachment.id) if attachment.id else None,
        name=attachment.name,
        project_id=project_id,
        region=attachment.region.rsplit("/", 1)[-1] if attachment.region else None,
        target_service=attachment.target_service or None,
        connection_preference=attachment.connection_preference or None,
        producer_forwarding_rule=attachment.producer_forwarding_rule or None,
        nat_subnet_self_links=list(attachment.nat_subnets),
        enable_proxy_protocol=attachment.enable_proxy_protocol,
        consumer_accept_lists=[
            ServiceAttachmentConsumerAcceptList(
                project_id_or_num=a.project_id_or_num or None,
                connection_limit=a.connection_limit or None,
                network_url=a.network_url or None,
            )
            for a in attachment.consumer_accept_lists
        ],
        consumer_reject_lists=list(attachment.consumer_reject_lists),
        connected_endpoints=[
            ServiceAttachmentConnectedEndpoint(
                endpoint=e.endpoint or None,
                status=e.status or None,
                psc_connection_id=str(e.psc_connection_id) if e.psc_connection_id else None,
                consumer_network=e.consumer_network or None,
            )
            for e in attachment.connected_endpoints
        ],
        domain_names=list(attachment.domain_names),
        observed_at=now_iso(),
        source_api="ServiceAttachmentsClient.aggregated_list",
    )


def list_service_attachments(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.service_attachments(),
        "aggregated_list",
        items_field="service_attachments",
        resource_type="service_attachment",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_service_attachment(a, project_id=project_id) for a in raw],
        warnings=warnings,
    )


def list_psc_endpoints(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    """PSC consumer endpoints are regular forwarding rules whose target is
    a service attachment -- filtered from the general forwarding-rule
    inventory rather than collected separately."""
    forwarding_rules = list_forwarding_rules(client_factory, project_id=project_id)
    endpoints = [
        PscEndpoint(
            forwarding_rule_self_link=rule.self_link or f"{project_id}/{rule.name}",
            name=rule.name,
            project_id=project_id,
            region=rule.region,
            ip_address=rule.ip_address,
            network_self_link=rule.network_self_link,
            subnetwork_self_link=rule.subnetwork_self_link,
            service_attachment_target=rule.target,
            psc_connection_status=rule.psc_connection_status,
        )
        for rule in forwarding_rules.data
        if rule.target and _SERVICE_ATTACHMENT_PATH_MARKER in rule.target
    ]
    return CollectionResult(data=endpoints, warnings=forwarding_rules.warnings)


__all__ = ["list_psc_endpoints", "list_service_attachments", "normalize_service_attachment"]
