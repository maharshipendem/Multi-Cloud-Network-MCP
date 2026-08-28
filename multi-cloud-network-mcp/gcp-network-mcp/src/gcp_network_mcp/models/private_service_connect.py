"""Normalized models for Private Service Connect (PSC): published
services (producer side) and consumer endpoints/NAT subnet relationships.

A PSC consumer endpoint is not a distinct GCP resource type -- it's a
regular ``ForwardingRule`` whose ``target`` is a Service Attachment URL
(see ``gcp/private_service_connect.py::list_psc_endpoints``, which
filters ``gcp.load_balancing.list_forwarding_rules``'s output rather
than duplicating collection logic).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class ServiceAttachmentConsumerAcceptList(BaseModel):
    project_id_or_num: str | None = None
    connection_limit: int | None = None
    network_url: str | None = None


class ServiceAttachmentConnectedEndpoint(BaseModel):
    """One consumer already connected to a published service, from
    ``ServiceAttachment.connected_endpoints`` -- embedded, not a separate
    list call."""

    endpoint: str | None = None
    status: str | None = None
    psc_connection_id: str | None = None
    consumer_network: str | None = None


class ServiceAttachment(GcpResource):
    """Normalized entry from ``ServiceAttachmentsClient.list``/
    ``aggregated_list``/``get`` -- a published service (PSC producer
    side)."""

    target_service: str | None = None
    connection_preference: str | None = None
    producer_forwarding_rule: str | None = None
    nat_subnet_self_links: list[str] = Field(default_factory=list)
    enable_proxy_protocol: bool | None = None
    consumer_accept_lists: list[ServiceAttachmentConsumerAcceptList] = Field(default_factory=list)
    consumer_reject_lists: list[str] = Field(default_factory=list)
    connected_endpoints: list[ServiceAttachmentConnectedEndpoint] = Field(default_factory=list)
    domain_names: list[str] = Field(default_factory=list)


class PscEndpoint(BaseModel):
    """A PSC consumer endpoint -- a ``ForwardingRule`` whose target is a
    Service Attachment, reported here in its own PSC-specific vocabulary
    rather than the general-purpose ``ForwardingRuleSummary`` shape."""

    forwarding_rule_self_link: str
    name: str
    project_id: str
    region: str | None = None
    ip_address: str | None = None
    network_self_link: str | None = None
    subnetwork_self_link: str | None = None
    service_attachment_target: str
    psc_connection_status: str | None = None


__all__ = [
    "PscEndpoint",
    "ServiceAttachment",
    "ServiceAttachmentConnectedEndpoint",
    "ServiceAttachmentConsumerAcceptList",
]
