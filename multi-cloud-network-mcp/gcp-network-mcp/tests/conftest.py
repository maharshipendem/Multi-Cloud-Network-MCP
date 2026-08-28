"""Shared pytest fixtures.

Unit tests never touch real GCP credentials or projects: every
service-layer function is exercised by monkeypatching the GCP client
library's operation-group methods (``.list``, ``.aggregated_list``,
``.get``, ...) directly on a ``ClientFactory``-produced client, so
``google.auth.default()`` is never asked to actually resolve ADC.
Integration tests that need real credentials live under
``tests/integration`` and are marked ``@pytest.mark.integration``,
excluded by default (see pyproject.toml's ``addopts``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from gcp_network_mcp.auth.credentials import _cached_credentials
from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.client_factory import ClientFactory

PROJECT_ID = "test-project-1"


@pytest.fixture(autouse=True)
def no_real_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no test can accidentally reach real ADC: every test either
    never resolves credentials (operation-group methods are always
    monkeypatched directly) or explicitly patches ``google.auth.default``
    itself. This makes an accidental real ADC call fail loudly instead of
    silently succeeding against a developer's local `gcloud` login.

    Also clears ``get_shared_credentials``' ``lru_cache`` before and after
    every test -- otherwise a test earlier in the same session that
    resolved (and cached) credentials for a given config would make a
    later test's ``google.auth.default`` monkeypatch silently never fire.
    """
    _cached_credentials.cache_clear()

    def _fail(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a test attempted to resolve real Application Default Credentials")

    monkeypatch.setattr("google.auth.default", _fail)
    yield
    _cached_credentials.cache_clear()


class FakeListPage:
    """One page of a plain (non-aggregated) ``List*`` response."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items


class FakePager:
    """Mimics a ``compute_v1`` ``ListPager``/pager with a ``.pages`` attribute."""

    def __init__(self, pages: list[Any]) -> None:
        self.pages = pages


def make_pager(items: list[Any], *, page_size: int = 100) -> FakePager:
    """Build a fake pager for a plain ``list``-shaped call, split into
    ``page_size``-sized pages so ``paginate()``'s per-page call counting
    can be exercised."""
    chunks = [items[i : i + page_size] for i in range(0, len(items), page_size)] or [[]]
    return FakePager([FakeListPage(chunk) for chunk in chunks])


class FakeAggregatedPage:
    def __init__(
        self, items_by_scope: dict[str, Any], unreachables: list[str] | None = None
    ) -> None:
        self.items = items_by_scope
        self.unreachables = unreachables or []


def make_aggregated_pager(
    items_by_scope: dict[str, list[Any]],
    *,
    items_field: str,
    unreachables: list[str] | None = None,
    scope_warnings: dict[str, tuple[str, str]] | None = None,
) -> FakePager:
    """Build a fake pager for an ``aggregated_list``-shaped call.

    ``items_by_scope`` maps a scope key (e.g. ``"regions/us-central1"``)
    to that scope's raw items; ``items_field`` names the field on each
    scope's ``*ScopedList`` (e.g. ``"subnetworks"``). ``scope_warnings``
    optionally maps a scope key to a ``(code, message)`` pair to attach
    as that scope's warning.
    """
    scope_warnings = scope_warnings or {}
    scoped = {}
    for scope, items in items_by_scope.items():
        code, message = scope_warnings.get(scope, ("", ""))
        scoped[scope] = SimpleNamespace(
            **{items_field: items}, warning=SimpleNamespace(code=code, message=message)
        )
    return FakePager([FakeAggregatedPage(scoped, unreachables)])


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, gcp_default_project_id=PROJECT_ID)


@pytest.fixture
def resource_context(settings: Settings) -> ResourceContext:
    return ResourceContext(settings)


@pytest.fixture
def client_factory(settings: Settings, resource_context: ResourceContext) -> ClientFactory:
    factory = ClientFactory(settings, resource_context)
    # Pre-seed the client cache with MagicMocks for every client class this
    # factory knows how to build, so `_resolved_credentials()` (and
    # therefore `google.auth.default`) is never reached by a test.
    for method_name in (
        "networks",
        "subnetworks",
        "routes",
        "firewalls",
        "firewall_policies",
        "network_firewall_policies",
        "instances",
        "addresses",
        "global_addresses",
        "forwarding_rules",
        "global_forwarding_rules",
        "target_http_proxies",
        "target_https_proxies",
        "backend_services",
        "region_backend_services",
        "routers",
        "compute_projects",
        "resource_manager_projects",
        "resource_manager_folders",
        "resource_manager_organizations",
    ):
        mock_client = MagicMock(name=f"mock_{method_name}")
        setattr(factory, method_name, lambda m=mock_client: m)
    return factory
