from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core import exceptions as gax
from tests.conftest import make_aggregated_pager, make_pager

from gcp_network_mcp.exceptions import ApiNotEnabledError
from gcp_network_mcp.gcp.collection import track_calls
from gcp_network_mcp.gcp.pagination import paginate, paginate_aggregated
from gcp_network_mcp.models.common import parse_self_link

# --- parse_self_link -----------------------------------------------------


def test_parse_self_link_global_resource() -> None:
    parsed = parse_self_link(
        "https://www.googleapis.com/compute/v1/projects/my-proj/global/networks/my-vpc"
    )
    assert parsed.project_id == "my-proj"
    assert parsed.scope == "global"
    assert parsed.region is None
    assert parsed.zone is None
    assert parsed.resource_type == "networks"
    assert parsed.resource_name == "my-vpc"


def test_parse_self_link_regional_resource() -> None:
    parsed = parse_self_link(
        "https://www.googleapis.com/compute/v1/projects/my-proj/regions/us-central1/"
        "subnetworks/my-subnet"
    )
    assert parsed.scope == "regions/us-central1"
    assert parsed.region == "us-central1"
    assert parsed.zone is None
    assert parsed.resource_type == "subnetworks"
    assert parsed.resource_name == "my-subnet"


def test_parse_self_link_zonal_resource() -> None:
    parsed = parse_self_link(
        "https://www.googleapis.com/compute/v1/projects/my-proj/zones/us-central1-a/instances/my-vm"
    )
    assert parsed.scope == "zones/us-central1-a"
    assert parsed.zone == "us-central1-a"
    assert parsed.region is None


def test_parse_self_link_malformed_degrades_to_all_none() -> None:
    parsed = parse_self_link("not-a-self-link")
    assert parsed.project_id is None
    assert parsed.scope is None
    assert parsed.resource_type is None


# --- paginate --------------------------------------------------------------


def test_paginate_flattens_pages_and_counts_calls() -> None:
    client = MagicMock()
    client.list.return_value = make_pager(["a", "b", "c", "d", "e"], page_size=2)

    with track_calls() as counter:
        items = paginate(client, "list", resource_type="thing", project="p1")

    assert items == ["a", "b", "c", "d", "e"]
    assert counter.count == 3  # 5 items / page_size 2 -> 3 pages


def test_paginate_respects_max_items_cap() -> None:
    client = MagicMock()
    client.list.return_value = make_pager(list(range(10)), page_size=3)

    items = paginate(client, "list", resource_type="thing", project="p1", max_items=4)
    assert items == [0, 1, 2, 3]


def test_paginate_rejects_mutating_method_name() -> None:
    from gcp_network_mcp.exceptions import GuardrailViolationError

    client = MagicMock()
    with pytest.raises(GuardrailViolationError):
        paginate(client, "delete", resource_type="thing", project="p1")
    client.delete.assert_not_called()


def test_paginate_translates_google_api_call_error() -> None:
    client = MagicMock()
    client.list.side_effect = gax.Forbidden(
        "Compute Engine API has not been used in project p1 before or it is disabled."
    )
    with pytest.raises(ApiNotEnabledError):
        paginate(client, "list", resource_type="thing", project_id="p1", project="p1")


def test_paginate_supports_custom_items_field() -> None:
    """``get_xpn_resources`` responses use ``"resources"``, not the
    default ``"items"`` -- the field name every other List response uses."""
    from types import SimpleNamespace

    client = MagicMock()
    page = SimpleNamespace(resources=["r1", "r2"])
    pager = MagicMock()
    pager.pages = [page]
    client.get_xpn_resources.return_value = pager

    items = paginate(
        client, "get_xpn_resources", resource_type="thing", items_field="resources", project="p1"
    )
    assert items == ["r1", "r2"]


# --- paginate_aggregated ----------------------------------------------------


def test_paginate_aggregated_flattens_across_scopes() -> None:
    client = MagicMock()
    client.aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": ["s1"], "regions/europe-west1": ["s2", "s3"]},
        items_field="subnetworks",
    )
    items, warnings = paginate_aggregated(
        client,
        "aggregated_list",
        items_field="subnetworks",
        resource_type="subnetwork",
        project="p1",
    )
    assert sorted(items) == ["s1", "s2", "s3"]
    assert warnings == []


def test_paginate_aggregated_filters_no_results_on_page_as_benign() -> None:
    client = MagicMock()
    client.aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": []},
        items_field="subnetworks",
        scope_warnings={"regions/us-central1": ("NO_RESULTS_ON_PAGE", "no results")},
    )
    items, warnings = paginate_aggregated(
        client,
        "aggregated_list",
        items_field="subnetworks",
        resource_type="subnetwork",
        project="p1",
    )
    assert items == []
    assert warnings == []


def test_paginate_aggregated_surfaces_non_benign_scope_warning() -> None:
    client = MagicMock()
    client.aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": []},
        items_field="subnetworks",
        scope_warnings={"regions/us-central1": ("UNREACHABLE", "scope degraded")},
    )
    items, warnings = paginate_aggregated(
        client,
        "aggregated_list",
        items_field="subnetworks",
        resource_type="subnetwork",
        project_id="p1",
        project="p1",
    )
    assert items == []
    assert len(warnings) == 1
    assert warnings[0].code == "UNREACHABLE"
    assert warnings[0].scope == "regions/us-central1"
    assert warnings[0].project_id == "p1"


def test_paginate_aggregated_surfaces_unreachable_scopes() -> None:
    client = MagicMock()
    client.aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": ["s1"]},
        items_field="subnetworks",
        unreachables=["zones/us-central1-a"],
    )
    items, warnings = paginate_aggregated(
        client,
        "aggregated_list",
        items_field="subnetworks",
        resource_type="subnetwork",
        project="p1",
    )
    assert items == ["s1"]
    assert len(warnings) == 1
    assert warnings[0].code == "UNREACHABLE"
    assert "zones/us-central1-a" in warnings[0].message


def test_paginate_aggregated_translates_error() -> None:
    client = MagicMock()
    client.aggregated_list.side_effect = gax.NotFound("gone")
    from gcp_network_mcp.exceptions import ResourceNotFoundError

    with pytest.raises(ResourceNotFoundError):
        paginate_aggregated(
            client,
            "aggregated_list",
            items_field="subnetworks",
            resource_type="subnetwork",
            project="p1",
        )
