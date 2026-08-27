# Local Development

## Prerequisites

- Python 3.12+
- Docker (optional, for container testing)
- An AWS account/profile for manual and integration testing (optional —
  unit tests never require one)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` to point at a real (ideally read-only) AWS profile if you want
to exercise the server against live AWS:

```bash
AWS_PROFILE=my-readonly-profile
AWS_DEFAULT_REGION=us-east-1
```

## Running the server

```bash
aws-cloudops-mcp
```

The server speaks MCP over stdio. To exercise it manually, use any
MCP-compatible client (e.g. Claude Desktop, or the `mcp` Python SDK's own
client tooling) pointed at this command.

## Code quality

```bash
ruff check .
ruff format --check .      # use `ruff format .` to auto-fix
mypy src
pytest
```

All four must pass before a change is considered complete. `mypy` is
configured with `disallow_untyped_defs = true` — new functions need type
hints.

## Tests

```bash
pytest                        # unit tests only (default)
pytest -m integration         # integration tests, requires real AWS creds
pytest --cov=aws_cloudops_mcp --cov-report=term-missing
```

Unit tests mock AWS with [moto](https://github.com/getmoto/moto)'s
`mock_aws`. An autouse fixture in `tests/conftest.py` pins fake credentials
into the environment for every unit test run so a developer's real
`~/.aws` profile is never touched accidentally.

Integration tests live in `tests/integration/`, are marked
`@pytest.mark.integration`, and are excluded by default via
`addopts = "-m 'not integration'"` in `pyproject.toml`. They require real,
read-only AWS credentials and make real (free-tier-safe `Describe*`/`Get*`)
API calls.

## Project layout

See [docs/architecture.md](architecture.md) for the layered design and the
rationale behind every package under `src/aws_cloudops_mcp/`.

## Adding a new tool (guidance for later milestones)

1. Add/extend a service-layer function under `aws_cloudops_mcp.aws` that
   calls AWS via `ClientFactory.get_client(...)` and either
   `aws.readonly.call_readonly(...)` (single call) or
   `aws.pagination.paginate(...)` (paginated call) — never call botocore
   directly from a tool.
2. Normalize the response into a `pydantic` model in
   `aws_cloudops_mcp.models.common`.
3. Add a tool module (or function) under `aws_cloudops_mcp.tools` that
   defines the MCP-facing schema and delegates execution to
   `tools._shared.execute_tool(...)`.
4. Register the tool in `server.build_server()`.
5. Add unit tests mocking the new AWS call with moto.
6. Document the tool in `docs/tools.md`, including its required IAM
   permission — and add that permission to the example policy there.

If the new AWS operation is not read-only (`describe_*`/`get_*`/`list_*`),
stop — see the "Future approval gates" section of
[docs/security.md](security.md). Milestone 1 and its near-term successors
are read-only by design.
