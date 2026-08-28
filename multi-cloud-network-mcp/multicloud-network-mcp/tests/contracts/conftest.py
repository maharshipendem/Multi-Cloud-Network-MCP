from __future__ import annotations

import pytest

from multicloud_network_mcp.contracts.models import CloudScope, Provider

FRESHNESS = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def aws_scope() -> CloudScope:
    return CloudScope(
        provider=Provider.AWS,
        account_id="123456789012",
        region="us-east-1",
        collected_at=FRESHNESS,
    )


@pytest.fixture
def azure_scope() -> CloudScope:
    return CloudScope(
        provider=Provider.AZURE,
        subscription_id="1e2d3c4b-5a69-4788-9f01-234567890abc",
        resource_group="rg-networking",
        location="eastus",
        collected_at=FRESHNESS,
    )


@pytest.fixture
def gcp_scope() -> CloudScope:
    return CloudScope(
        provider=Provider.GCP,
        project_id="acme-prod-networking-123456",
        region="us-central1",
        collected_at=FRESHNESS,
    )
