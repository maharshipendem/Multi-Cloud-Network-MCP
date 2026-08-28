# Development

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Validation

Run all of these before opening a PR — CI runs the same commands:

```bash
ruff format --check .
ruff check .
mypy src
pytest -m "not integration" --cov=src --cov-report=term-missing
python -m build
docker build -t gcp-network-mcp:local .
```

## Testing conventions

- **Unit tests never touch real GCP credentials or projects.**
  `tests/conftest.py`'s `no_real_adc` fixture (autouse) monkeypatches
  `google.auth.default` to raise if any test path reaches it
  unexpectedly; every service-layer test instead monkeypatches the
  relevant `ClientFactory`-produced client's operation methods
  directly (`.list`, `.aggregated_list`, `.get`, ...).
- **`tests/conftest.py`'s `FakePager`/`make_pager`/`make_aggregated_pager`**
  mimic the real `compute_v1` pager shape (`.pages`, each page exposing
  `.items` for a plain list or `.items`-as-scope-dict plus
  `.unreachables` for an aggregated list) closely enough that
  `gcp/pagination.py`'s real pagination/warning-filtering logic runs
  unmodified against them.
- **Construct real `compute_v1`/`resourcemanager_v3` proto-plus message
  objects** in tests (`compute_v1.Network(...)`, `compute_v1.Firewall(...)`,
  etc.) rather than raw dicts — this exercises the exact field-name
  quirks the real SDK has (`I_p_protocol`, `I_pv4_range`, `network_i_p`,
  `type_`, ...), which a hand-rolled dict/mock would silently paper over.
- **`tests/unit/test_mcp_smoke.py`/`test_tools_registration.py`** exercise
  the real `MCPServer.build_server()` → `list_tools()`/`call_tool()`
  path, not just the service layer directly — they monkeypatch the GCP
  client *classes* at construction time (`compute_v1.NetworksClient`,
  etc.) so `build_server()`, tool registration, and response-envelope
  serialization all run through real, unmodified code.
- **`tests/unit/test_no_mutation_calls.py`** is a static (non-behavioral)
  guard: it scans `gcp/*.py` source for a hardcoded mutating method name
  or a client call bypassing the guardrail choke point.
- **Integration tests** (`tests/integration/`, marked
  `@pytest.mark.integration`, excluded by default via `pyproject.toml`'s
  `addopts`) need a real, explicitly-authorized read-only GCP identity.
  See `tests/integration/README.md`.

## Adding a new tool

1. Add the raw-response → normalized-model mapping in the relevant
   `models/*.py`.
2. Add the collection function in the relevant `gcp/*.py`, calling the
   GCP client exclusively via `gcp/pagination.py::paginate()`/
   `paginate_aggregated()` (or `gcp/readonly.py::call_readonly()` for a
   single non-paginated call) — never construct or call a client
   directly.
3. Register the MCP tool in the relevant `tools/*.py`, delegating to
   `tools/_shared.py::execute_tool()`/`execute_tool_with_resolved_project()`.
4. Wire `register()` into `server.py::build_server()`.
5. Add unit tests for the normalizer, the collection function, and (if
   the tool is new, not a variant of an existing one) a
   `test_tools_registration.py` entry.
