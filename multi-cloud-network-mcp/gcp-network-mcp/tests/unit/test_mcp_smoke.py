"""End-to-end MCP smoke tests: exercises the real ``MCPServer.call_tool()``
path (not just the GCP service layer directly), including tool-layer
project resolution and response-envelope serialization every other test
file bypasses by calling service functions directly.

``google.auth.default`` is monkeypatched (a real GCP client library
constructor requires *some* credentials object, even a fake one) and the
``compute_v1``/``resourcemanager_v3`` client classes are monkeypatched at
construction time (rather than mocking individual ``ClientFactory``
instances, since ``build_server`` owns construction of its own
``ClientFactory`` internally) so ``build_server()`` -> tool registration
-> ``call_tool()`` all run through real, unmodified code.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from tests.conftest import PROJECT_ID, make_pager

from gcp_network_mcp.auth.credentials import _cached_credentials
from gcp_network_mcp.config import Settings
from gcp_network_mcp.server import build_server


@pytest.fixture
def mcp_settings() -> Settings:
    return Settings(_env_file=None, gcp_default_project_id=PROJECT_ID)


@pytest.fixture(autouse=True)
def _fake_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    _cached_credentials.cache_clear()
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(MagicMock(), "adc-project")))
    yield
    _cached_credentials.cache_clear()


@pytest.fixture
def mock_networks_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def patched_clients(mock_networks_client: MagicMock, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "gcp_network_mcp.gcp.client_factory.compute_v1.NetworksClient",
        MagicMock(return_value=mock_networks_client),
    )
    return mock_networks_client


async def test_initialize_and_list_tools(mcp_settings: Settings) -> None:
    server = build_server(mcp_settings)
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert "gcp_get_caller_identity" in tool_names
    assert "gcp_list_networks" in tool_names
    assert "gcp_get_vpc_topology" in tool_names
    # every tool this server exposes must declare itself read-only
    for tool in tools:
        assert tool.meta is not None
        assert tool.meta["read_only"] is True
        assert tool.meta["cloud"] == "gcp"


async def test_call_tool_list_networks_returns_envelope(
    mcp_settings: Settings, patched_clients: MagicMock
) -> None:
    from google.cloud import compute_v1

    patched_clients.list.return_value = make_pager(
        [compute_v1.Network(name="vpc-1", auto_create_subnetworks=True)]
    )
    server = build_server(mcp_settings)
    result = await server.call_tool("gcp_list_networks", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["project_id"] == PROJECT_ID
    assert payload["data"][0]["name"] == "vpc-1"
    assert payload["metadata"]["count"] == 1


async def test_call_tool_surfaces_authentication_error_without_crashing(
    mcp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import google.auth.exceptions as auth_exceptions

    monkeypatch.setattr(
        "google.auth.default",
        MagicMock(side_effect=auth_exceptions.DefaultCredentialsError("no adc")),
    )
    server = build_server(mcp_settings)
    result = await server.call_tool("gcp_get_caller_identity", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["type"] == "AUTHENTICATION_ERROR"


async def test_call_tool_with_unallowed_project_returns_structured_error() -> None:
    settings = Settings(_env_file=None, gcp_project_allowlist="only-this-project")
    server = build_server(settings)
    result = await server.call_tool("gcp_list_networks", {"project_id": "other-project"})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["type"] == "PROJECT_NOT_ALLOWED"


async def test_server_exposes_no_write_capable_tools(mcp_settings: Settings) -> None:
    """Structural guarantee: every registered tool name follows this
    server's get/list-only naming convention -- nothing named create/
    delete/update/patch/set/enable/disable slips into the tool registry."""
    server = build_server(mcp_settings)
    tools = await server.list_tools()
    blocked_markers = ("create", "delete", "update", "patch", "set_", "enable", "disable", "insert")
    for tool in tools:
        lowered = tool.name.lower()
        assert not any(marker in lowered for marker in blocked_markers), tool.name
