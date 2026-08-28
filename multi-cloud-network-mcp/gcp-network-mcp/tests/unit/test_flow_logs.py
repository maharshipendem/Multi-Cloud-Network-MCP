from __future__ import annotations

from types import SimpleNamespace

from google.cloud import network_management_v1 as nm
from tests.conftest import PROJECT_ID, FakePager

from gcp_network_mcp.gcp.flow_logs import (
    _target,
    list_vpc_flow_logs_configs,
    normalize_flow_logs_config,
)

_CONFIG_NAME = f"projects/{PROJECT_ID}/locations/global/vpcFlowLogsConfigs/cfg-1"


def _flow_logs_pager(configs: list[nm.VpcFlowLogsConfig], *, unreachable=None) -> FakePager:
    """Fake pager matching ``paginate_with_unreachable``'s expected page
    shape for `list_vpc_flow_logs_configs` (``items_field="vpc_flow_logs_configs"``),
    which doesn't match the generic ``items`` attribute name that
    ``tests.conftest.make_unreachable_pager`` hard-codes."""
    page = SimpleNamespace(vpc_flow_logs_configs=configs, unreachable=unreachable or [])
    return FakePager([page])


def test_target_returns_subnet_branch() -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        subnet=f"projects/{PROJECT_ID}/regions/us-central1/subnetworks/sub-1",
    )
    target_type, target_resource = _target(config)
    assert target_type == "subnet"
    assert target_resource == f"projects/{PROJECT_ID}/regions/us-central1/subnetworks/sub-1"


def test_target_returns_interconnect_attachment_branch() -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        interconnect_attachment=f"projects/{PROJECT_ID}/regions/us-central1/interconnectAttachments/ic-1",
    )
    target_type, target_resource = _target(config)
    assert target_type == "interconnect_attachment"
    assert (
        target_resource == f"projects/{PROJECT_ID}/regions/us-central1/interconnectAttachments/ic-1"
    )


def test_target_returns_vpn_tunnel_branch() -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        vpn_tunnel=f"projects/{PROJECT_ID}/regions/us-central1/vpnTunnels/tun-1",
    )
    target_type, target_resource = _target(config)
    assert target_type == "vpn_tunnel"
    assert target_resource == f"projects/{PROJECT_ID}/regions/us-central1/vpnTunnels/tun-1"


def test_target_returns_unknown_when_none_of_the_three_fields_set() -> None:
    # `network` is a valid oneof member of `target_resource` too, but
    # `_target` intentionally only recognizes subnet/interconnect_attachment/
    # vpn_tunnel (see module docstring: project-level configs target one of
    # those three) -- a network-scoped config falls through to "unknown".
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        network=f"projects/{PROJECT_ID}/global/networks/vpc-1",
    )
    target_type, target_resource = _target(config)
    assert target_type == "unknown"
    assert target_resource is None


def test_target_returns_unknown_when_nothing_set() -> None:
    config = nm.VpcFlowLogsConfig(name=_CONFIG_NAME)
    target_type, target_resource = _target(config)
    assert target_type == "unknown"
    assert target_resource is None


def test_normalize_flow_logs_config_maps_fields() -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        state=nm.VpcFlowLogsConfig.State.ENABLED,
        subnet=f"projects/{PROJECT_ID}/regions/us-central1/subnetworks/sub-1",
        aggregation_interval=nm.VpcFlowLogsConfig.AggregationInterval.INTERVAL_1_MIN,
        flow_sampling=0.5,
        filter_expr='logName="projects/p/logs/x"',
        description="a flow logs config",
        cross_project_metadata=nm.VpcFlowLogsConfig.CrossProjectMetadata.CROSS_PROJECT_METADATA_ENABLED,
    )

    result = normalize_flow_logs_config(config)

    assert result.name == _CONFIG_NAME
    assert result.state == "ENABLED"
    assert result.target_type == "subnet"
    assert result.target_resource == f"projects/{PROJECT_ID}/regions/us-central1/subnetworks/sub-1"
    assert result.aggregation_interval == "INTERVAL_1_MIN"
    assert result.flow_sampling == 0.5
    assert result.filter_expr == 'logName="projects/p/logs/x"'
    assert result.description == "a flow logs config"
    assert result.cross_project_metadata == "CROSS_PROJECT_METADATA_ENABLED"
    assert result.observed_at


def test_normalize_flow_logs_config_leaves_unset_oneof_fields_none() -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        vpn_tunnel=f"projects/{PROJECT_ID}/regions/us-central1/vpnTunnels/tun-1",
    )

    result = normalize_flow_logs_config(config)

    assert result.target_type == "vpn_tunnel"
    assert result.aggregation_interval is None
    assert result.cross_project_metadata is None
    assert result.flow_sampling is None
    assert result.filter_expr is None
    assert result.description is None


def test_list_vpc_flow_logs_configs_returns_normalized_data_and_warnings(client_factory) -> None:
    config = nm.VpcFlowLogsConfig(
        name=_CONFIG_NAME,
        state=nm.VpcFlowLogsConfig.State.ENABLED,
        subnet=f"projects/{PROJECT_ID}/regions/us-central1/subnetworks/sub-1",
    )
    client_factory.vpc_flow_logs().list_vpc_flow_logs_configs.return_value = _flow_logs_pager(
        [config], unreachable=["locations/asia-east1"]
    )

    result = list_vpc_flow_logs_configs(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    assert result.data[0].name == _CONFIG_NAME
    assert result.data[0].target_type == "subnet"
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "UNREACHABLE"
    assert result.warnings[0].scope == "locations/asia-east1"


def test_list_vpc_flow_logs_configs_empty(client_factory) -> None:
    client_factory.vpc_flow_logs().list_vpc_flow_logs_configs.return_value = _flow_logs_pager([])

    result = list_vpc_flow_logs_configs(client_factory, project_id=PROJECT_ID)

    assert result.data == []
    assert result.warnings == []
