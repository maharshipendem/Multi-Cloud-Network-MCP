# Local Development

## Prerequisites

- Python 3.12+
- Docker (optional, for container testing)
- An Azure subscription/identity for manual and integration testing
  (optional — unit tests never require one)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` to point at a real (ideally read-only) Azure identity if you
want to exercise the server against a live subscription:

```bash
AZURE_TENANT_ID=<your-tenant-id>
AZURE_DEFAULT_SUBSCRIPTION_ID=<your-subscription-id>
```

`DefaultAzureCredential` also works with zero configuration against an
`az login` session — run `az login` before starting the server and leave
`AZURE_TENANT_ID`/`AZURE_CLIENT_ID` blank.

## Running the server

```bash
azure-network-mcp
```

The server speaks MCP over stdio. To exercise it manually, use any
MCP-compatible client (e.g. Claude Desktop, or the `mcp` Python SDK's own
client tooling) pointed at this command — see
[`mcp-client-config.example.json`](../mcp-client-config.example.json) for
a sample client configuration.

## Code quality

```bash
ruff check .
ruff format --check .      # use `ruff format .` to auto-fix
mypy src
pytest
```

All four must pass before a change is considered complete. `mypy` is
configured with `disallow_untyped_defs = true` and the `pydantic.mypy`
plugin — new functions need type hints, and `pydantic_settings.BaseSettings`
subclasses type-check correctly with pydantic-settings' private
constructor kwargs (`_env_file`, etc.) only with that plugin enabled.

## Tests

```bash
pytest                                          # unit tests only (default)
pytest -m integration                           # integration tests, requires real Azure creds
pytest --cov=src --cov-report=term-missing      # with coverage
```

Unit tests never touch real Azure credentials or subscriptions. Azure has
no moto-equivalent SDK mocking library, so every ARM SDK operation-group
method (`.list`, `.list_all`, `.get`, `begin_*`) is monkeypatched directly
via `unittest.mock.MagicMock`, shaped like the real SDK's `ItemPaged`/
`LROPoller` return types — see `tests/conftest.py::make_pageable` and the
`network_client`/`resource_client`/`subscription_client` fixtures. An
autouse fixture (`azure_credentials`) pins obviously-fake tenant/client
IDs into the environment for every unit test run.

`tests/unit/test_mcp_smoke.py` additionally exercises every tool through
the real `MCPServer.call_tool()` path (not just the ARM service layer
directly) by monkeypatching the SDK client *classes* themselves
(`NetworkManagementClient`, `ResourceManagementClient`,
`SubscriptionClient`) before `build_server()` constructs its own
`ClientFactory` — this catches a mismatched parameter name between a
tool's declared schema and the underlying service-layer function
signature, a class of bug the ARM-layer-only tests can't see.

Integration tests live in `tests/integration/`, are marked
`@pytest.mark.integration`, and are excluded by default via
`addopts = "-m 'not integration'"` in `pyproject.toml`. They require real,
read-only Azure credentials and make real (free-tier-safe `get`/`list`)
API calls.

## Project layout

See [docs/architecture.md](architecture.md) for the layered design and
the rationale behind every package under `src/azure_network_mcp/`.

## Adding a new tool

1. Add/extend a service-layer function under `azure_network_mcp.arm` that
   calls Azure via `ClientFactory.get_network_client(...)` /
   `get_resource_client(...)` / `get_subscription_client()` and either
   `arm.readonly.call_readonly(...)` (single call) or
   `arm.pagination.paginate(...)` (paginated call) — never call the Azure
   SDK directly from a tool.
2. Add a normalized model under `azure_network_mcp.models` (extend
   `AzureResource` if it's a top-level ARM resource; a plain `BaseModel`
   otherwise).
3. Register the MCP tool in `azure_network_mcp.tools`, delegating the
   body to `execute_tool` (fixed `subscription_id`) or
   `execute_tool_with_resolved_subscription` (optional `subscription_id`
   that falls back to `AZURE_DEFAULT_SUBSCRIPTION_ID`) — never build the
   response envelope by hand.
4. Wire the new tool module into `build_server()` in `server.py`.
5. Add unit tests: normalizer coverage in `tests/unit/test_<area>.py`,
   and add the tool name to `EXPECTED_TOOL_NAMES` in
   `tests/unit/test_server.py`.
6. If the new SDK method is `get`/`list`-prefixed, no guardrail change is
   needed. If it's a `begin_*` method that is genuinely read-only (like
   the two effective-* computations), it needs an explicit,
   individually-justified addition to `READ_ONLY_ACTIONS` in
   `security/guardrails.py` — never a loosening of `BLOCKED_KEYWORDS`.

## Building

```bash
python -m build
docker build -t azure-network-mcp:local .
```
