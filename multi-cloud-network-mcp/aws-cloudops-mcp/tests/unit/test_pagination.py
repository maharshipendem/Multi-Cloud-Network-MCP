from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import OperationNotPageableError

from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.exceptions import GuardrailViolationError


class _FakePaginator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._pages


class _FakeClient:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages

    def get_paginator(self, operation_name: str) -> _FakePaginator:
        return _FakePaginator(self._pages)


class _NonPageableClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def get_paginator(self, operation_name: str) -> Any:
        raise OperationNotPageableError(operation_name=operation_name)

    def describe_widgets(self, **kwargs: Any) -> dict[str, Any]:
        return self._response


def test_paginate_aggregates_all_pages() -> None:
    pages = [
        {"Vpcs": [{"VpcId": "vpc-1"}, {"VpcId": "vpc-2"}]},
        {"Vpcs": [{"VpcId": "vpc-3"}]},
    ]
    client = _FakeClient(pages)
    result = paginate(client, "describe_vpcs", "Vpcs")
    assert [v["VpcId"] for v in result] == ["vpc-1", "vpc-2", "vpc-3"]


def test_paginate_applies_max_items_cap() -> None:
    pages = [
        {"Vpcs": [{"VpcId": "vpc-1"}, {"VpcId": "vpc-2"}]},
        {"Vpcs": [{"VpcId": "vpc-3"}]},
    ]
    client = _FakeClient(pages)
    result = paginate(client, "describe_vpcs", "Vpcs", max_items=2)
    assert len(result) == 2
    assert [v["VpcId"] for v in result] == ["vpc-1", "vpc-2"]


def test_paginate_handles_empty_pages() -> None:
    client = _FakeClient([{"Vpcs": []}])
    assert paginate(client, "describe_vpcs", "Vpcs") == []


def test_paginate_rejects_mutating_operation_before_calling_client() -> None:
    client = _FakeClient([])
    with pytest.raises(GuardrailViolationError):
        paginate(client, "delete_vpc", "Vpcs")


def test_paginate_falls_back_for_non_pageable_operations() -> None:
    client = _NonPageableClient({"Widgets": [{"Id": "w-1"}, {"Id": "w-2"}]})
    result = paginate(client, "describe_widgets", "Widgets")
    assert [w["Id"] for w in result] == ["w-1", "w-2"]
