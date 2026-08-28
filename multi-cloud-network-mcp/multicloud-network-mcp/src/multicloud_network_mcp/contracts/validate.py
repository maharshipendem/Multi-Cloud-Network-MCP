"""The engine behind ``python -m multicloud_network_mcp.contracts validate``.

Validates every example file under a target directory two ways, not
just one: (1) structural JSON Schema validity against the matching
generated schema, and (2) that the same example parses into the
matching Pydantic model without error. A file could pass one check and
fail the other -- e.g. valid-per-schema but missing a field the model
requires with no default, or vice versa if a schema and its model have
drifted -- so both are required for a file to count as passing, which
is exactly the guarantee that keeps "schemas are generated from models"
true in practice, not just at generation time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel, ValidationError

from multicloud_network_mcp.contracts.models import (
    Address,
    Attachment,
    CollectionWarning,
    DnsResolver,
    DnsRule,
    DnsZone,
    Endpoint,
    Finding,
    FirewallRule,
    Gateway,
    Interconnect,
    InterconnectAttachment,
    LoadBalancer,
    Network,
    NetworkInterface,
    ObservabilityReference,
    PathExplanation,
    Peering,
    ProviderCapabilityManifest,
    ResponseEnvelope,
    Route,
    RouteTable,
    Subnet,
    TopologyGraph,
    TransitHub,
    VpnGateway,
    VpnTunnel,
)
from multicloud_network_mcp.contracts.version import SCHEMA_ID_VERSION

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas" / f"v{SCHEMA_ID_VERSION}"

# Maps an example directory's/file's leading resource-type slug (before
# the first "." in the filename, e.g. "network.aws-vpc.json" -> "network")
# to (schema stem, model class). Kept in one place so `validate.py` and
# `scripts/generate_schemas.py` agree on the same slug<->model mapping.
_TYPE_TABLE: dict[str, tuple[str, type[BaseModel]]] = {
    "network": ("network", Network),
    "subnet": ("subnet", Subnet),
    "network-interface": ("network-interface", NetworkInterface),
    "address": ("address", Address),
    "route-table": ("route-table", RouteTable),
    "route": ("route", Route),
    "firewall-rule": ("firewall-rule", FirewallRule),
    "gateway": ("gateway", Gateway),
    "transit-hub": ("transit-hub", TransitHub),
    "attachment": ("attachment", Attachment),
    "peering": ("peering", Peering),
    "vpn-gateway": ("vpn-gateway", VpnGateway),
    "vpn-tunnel": ("vpn-tunnel", VpnTunnel),
    "interconnect": ("interconnect", Interconnect),
    "interconnect-attachment": ("interconnect-attachment", InterconnectAttachment),
    "dns-zone": ("dns-zone", DnsZone),
    "dns-resolver": ("dns-resolver", DnsResolver),
    "dns-rule": ("dns-rule", DnsRule),
    "load-balancer": ("load-balancer", LoadBalancer),
    "endpoint": ("endpoint", Endpoint),
    "observability-reference": ("observability-reference", ObservabilityReference),
    "topology-graph": ("topology-graph", TopologyGraph),
    "finding": ("finding", Finding),
    "path-explanation": ("path-explanation", PathExplanation),
    "response-envelope": ("response-envelope", ResponseEnvelope),
    "collection-warning": ("collection-warning", CollectionWarning),
    "provider-capability-manifest": (
        "provider-capability-manifest",
        ProviderCapabilityManifest,
    ),
}


@dataclass
class ExampleResult:
    path: Path
    resource_type_slug: str
    schema_valid: bool
    model_valid: bool
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.schema_valid and self.model_valid


@dataclass
class ValidationReport:
    results: list[ExampleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[ExampleResult]:
        return [r for r in self.results if not r.passed]


def _resource_type_slug_for(path: Path) -> str | None:
    """An example filename's convention is
    ``<resource-type-slug>.<provider>-<description>.json`` (e.g.
    ``network.aws-vpc-prod.json``) -- the slug is everything before the
    first ``.``."""
    stem = path.name.split(".", 1)[0]
    return stem if stem in _TYPE_TABLE else None


def _load_schema(schema_stem: str) -> dict[str, Any]:
    schema_path = _SCHEMA_DIR / f"{schema_stem}.schema.json"
    return json.loads(schema_path.read_text())


def validate_example_file(path: Path) -> ExampleResult:
    slug = _resource_type_slug_for(path)
    if slug is None:
        return ExampleResult(
            path=path,
            resource_type_slug="<unknown>",
            schema_valid=False,
            model_valid=False,
            errors=[
                f"filename {path.name!r} doesn't start with a known resource-type slug "
                f"(expected one of {sorted(_TYPE_TABLE)}, followed by '.')"
            ],
        )

    schema_stem, model_cls = _TYPE_TABLE[slug]
    data = json.loads(path.read_text())

    errors: list[str] = []
    schema_valid = True
    try:
        schema = _load_schema(schema_stem)
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        schema_valid = False
        errors.append(f"schema validation failed: {exc.message} (at {list(exc.absolute_path)})")
    except FileNotFoundError:
        schema_valid = False
        errors.append(f"no generated schema file found for {schema_stem!r}")

    model_valid = True
    try:
        model_cls.model_validate(data)
    except ValidationError as exc:
        model_valid = False
        errors.append(f"model validation failed: {exc}")

    return ExampleResult(
        path=path,
        resource_type_slug=slug,
        schema_valid=schema_valid,
        model_valid=model_valid,
        errors=errors,
    )


def validate_directory(directory: Path) -> ValidationReport:
    """Validate every ``*.json`` file directly under ``directory`` and
    any of its subdirectories (so ``contracts/examples/aws/``,
    ``.../azure/``, ``.../gcp/`` are all covered by one call against
    ``contracts/examples``)."""
    report = ValidationReport()
    for path in sorted(directory.rglob("*.json")):
        report.results.append(validate_example_file(path))
    return report


__all__ = [
    "ExampleResult",
    "ValidationReport",
    "validate_directory",
    "validate_example_file",
]
