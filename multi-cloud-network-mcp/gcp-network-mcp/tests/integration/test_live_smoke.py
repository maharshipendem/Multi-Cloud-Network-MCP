"""Opt-in live smoke tests against a real GCP project.

Excluded by default (see pyproject.toml's addopts). Run explicitly with
`pytest -m integration` after reading tests/integration/README.md --
these need real, explicitly-authorized read-only ADC and a real project.
"""

from __future__ import annotations

import os

import pytest

from gcp_network_mcp.config import Settings
from gcp_network_mcp.server import build_server

pytestmark = pytest.mark.integration


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not set -- see tests/integration/README.md")
    return value


async def test_list_networks_against_a_real_project() -> None:
    project_id = _require_env("GCP_DEFAULT_PROJECT_ID")
    server = build_server(Settings())
    result = await server.call_tool("gcp_list_networks", {"project_id": project_id})
    assert result.structured_content["success"] is True


async def test_get_caller_identity_never_returns_token_material() -> None:
    server = build_server(Settings())
    result = await server.call_tool("gcp_get_caller_identity", {})
    payload = result.structured_content
    assert payload["success"] is True
    assert "token" not in str(payload).lower()
