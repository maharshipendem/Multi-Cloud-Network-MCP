from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from tests.conftest import make_pageable

from azure_network_mcp.arm.collection import track_calls
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.exceptions import GuardrailViolationError


def test_paginate_flattens_items_across_pages() -> None:
    operation_group = MagicMock()
    operation_group.list_all.return_value = make_pageable(list(range(10)), page_size=3)

    items = paginate(operation_group, "list_all", max_items=1000)

    assert items == list(range(10))


def test_paginate_stops_at_max_items() -> None:
    operation_group = MagicMock()
    operation_group.list_all.return_value = make_pageable(list(range(10)), page_size=3)

    items = paginate(operation_group, "list_all", max_items=5)

    assert items == [0, 1, 2, 3, 4]


def test_paginate_rejects_mutating_method_names() -> None:
    operation_group = MagicMock()
    with pytest.raises(GuardrailViolationError):
        paginate(operation_group, "begin_delete")
    operation_group.begin_delete.assert_not_called()


def test_paginate_records_one_call_per_page_when_tracked() -> None:
    operation_group = MagicMock()
    # 10 items at 3 per page -> 4 pages (3, 3, 3, 1)
    operation_group.list_all.return_value = make_pageable(list(range(10)), page_size=3)

    with track_calls() as counter:
        paginate(operation_group, "list_all", max_items=1000)

    assert counter.count == 4


def test_paginate_does_not_record_calls_outside_track_calls() -> None:
    operation_group = MagicMock()
    operation_group.list_all.return_value = make_pageable(list(range(3)), page_size=3)
    paginate(operation_group, "list_all")  # must not raise with no active counter


def test_paginate_passes_through_kwargs() -> None:
    operation_group = MagicMock()
    operation_group.list.return_value = make_pageable([])
    paginate(operation_group, "list", resource_group_name="rg-1", virtual_network_name="vnet-1")
    operation_group.list.assert_called_once_with(
        resource_group_name="rg-1", virtual_network_name="vnet-1"
    )
