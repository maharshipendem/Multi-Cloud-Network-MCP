from __future__ import annotations

import pytest

from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings
from gcp_network_mcp.exceptions import InvalidConfigurationError, ProjectNotAllowedError


def test_allowlist_properties_parse_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        gcp_project_allowlist="proj-a, proj-b,proj-c",
        gcp_folder_allowlist="111,222",
        gcp_organization_allowlist="999",
    )
    assert settings.project_allowlist == ["proj-a", "proj-b", "proj-c"]
    assert settings.folder_allowlist == ["111", "222"]
    assert settings.organization_allowlist == ["999"]


def test_unset_allowlist_is_none() -> None:
    settings = Settings(_env_file=None)
    assert settings.project_allowlist is None
    assert settings.folder_allowlist is None
    assert settings.organization_allowlist is None


def test_resolve_project_id_uses_explicit_value() -> None:
    ctx = ResourceContext(Settings(_env_file=None, gcp_default_project_id="default-proj"))
    assert ctx.resolve_project_id("explicit-proj") == "explicit-proj"


def test_resolve_project_id_falls_back_to_default() -> None:
    ctx = ResourceContext(Settings(_env_file=None, gcp_default_project_id="default-proj"))
    assert ctx.resolve_project_id(None) == "default-proj"


def test_resolve_project_id_raises_without_default_or_explicit() -> None:
    ctx = ResourceContext(Settings(_env_file=None))
    with pytest.raises(InvalidConfigurationError):
        ctx.resolve_project_id(None)


def test_resolve_project_id_enforces_allowlist() -> None:
    ctx = ResourceContext(Settings(_env_file=None, gcp_project_allowlist="allowed-proj"))
    assert ctx.resolve_project_id("allowed-proj") == "allowed-proj"
    with pytest.raises(ProjectNotAllowedError):
        ctx.resolve_project_id("other-proj")


def test_assert_folder_and_organization_allowed() -> None:
    ctx = ResourceContext(
        Settings(_env_file=None, gcp_folder_allowlist="111", gcp_organization_allowlist="999")
    )
    ctx.assert_folder_allowed("111")
    ctx.assert_organization_allowed("999")
    with pytest.raises(ProjectNotAllowedError):
        ctx.assert_folder_allowed("222")
    with pytest.raises(ProjectNotAllowedError):
        ctx.assert_organization_allowed("888")


def test_unset_allowlist_permits_anything() -> None:
    ctx = ResourceContext(Settings(_env_file=None))
    ctx.assert_project_allowed("any-project")
    ctx.assert_folder_allowed("any-folder")
    ctx.assert_organization_allowed("any-org")
