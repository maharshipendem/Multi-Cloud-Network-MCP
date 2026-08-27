# Milestone 1 Status Report — aws-cloudops-mcp

```
Milestone: 1 — AWS MCP Server Foundation (read-only)
Status: Complete
Date: 2026-08-27
```

## Implemented

- **MCP server foundation**: `src/aws_cloudops_mcp/server.py` builds and
  runs an `mcp.server.mcpserver.MCPServer` (the official MCP Python SDK,
  v2.x) over the stdio transport.
- **Layered architecture**: MCP tool layer → security guardrails → AWS
  service layer → AWS client factory → authentication → boto3/AWS APIs.
  See `docs/architecture.md`. No tool module constructs a boto3 client or
  calls botocore directly.
- **AWS SDK integration**: centralized `ClientFactory`
  (`src/aws_cloudops_mcp/aws/client_factory.py`) is the sole construction
  point for boto3 clients; applies region selection, retry (`standard`
  mode, configurable `max_attempts`), and connect/read timeout
  configuration consistently.
- **Authentication / session management**
  (`src/aws_cloudops_mcp/auth/`): standard boto3 credential chain (env
  vars, shared config/credentials files, SSO profiles, IAM roles),
  optional `sts:AssumeRole` for a configured `AWS_ROLE_ARN` with automatic,
  margin-based credential refresh (`SessionManager`), never persisted to
  disk.
- **Multi-account-ready architecture**: `ClientFactory.get_client()` /
  `get_account_id()` accept a per-call `role_arn`, and `SessionManager`
  caches sessions per role ARN — a future cross-account tool needs no
  change to the auth/client layers. `tools/accounts.py` is reserved for
  that tool. AWS Organizations automation is explicitly out of scope.
- **Multi-region-ready architecture**: every service-layer function takes
  an explicit `region`; no global/default client is reused across regions.
- **Configuration management**: `pydantic-settings`-based `Settings`
  (`src/aws_cloudops_mcp/config.py`), `.env.example` provided, no real
  credentials anywhere in the repo.
- **Structured logging**: JSON logs to stderr with `timestamp`,
  `request_id`, `tool_name`, `account_id`, `region`, `duration_ms`,
  `status` (`src/aws_cloudops_mcp/logging/setup.py`); credentials and raw
  AWS payloads are never logged.
- **Correlation IDs**: a UUID4 request ID is generated per tool invocation
  (`tools/_shared.execute_tool`) and threaded through logs and the response
  envelope's `metadata.request_id`.
- **Error handling**: custom exception hierarchy
  (`src/aws_cloudops_mcp/exceptions.py`:
  `AuthenticationError`/`AuthorizationError`/`AWSServiceError`/
  `InvalidRegionError`/`InvalidConfigurationError`/`ToolExecutionError`/
  `GuardrailViolationError`) and botocore-error translation in
  `tools/_shared.py`; no raw stack traces or `ClientError` text ever
  reaches an MCP response.
- **Security guardrails**: `src/aws_cloudops_mcp/security/guardrails.py`
  funnels every AWS API call (paginated or not) through
  `assert_read_only_operation()`, rejecting anything that isn't
  `describe_*`/`get_*`/`list_*` or that contains a mutating keyword
  (`create`, `delete`, `modify`, `attach`, `terminate`, `put`,
  `authorize`, ... — full list in the module). Documented as
  defense-in-depth, not a substitute for IAM, in `docs/security.md`.
- **Five read-only MCP tools** (below), each mocked-AWS unit tested and
  exercised through the real `MCPServer.call_tool()` path in manual
  validation.
- **Unit tests**: 78 tests, `pytest --cov=aws_cloudops_mcp` → **95%**
  statement coverage, all AWS calls mocked via `moto` — no real
  credentials required.
- **Integration test framework**: `tests/integration/test_live_aws.py`,
  marked `@pytest.mark.integration`, excluded by default
  (`addopts = "-m 'not integration'"` in `pyproject.toml`); run explicitly
  with `pytest -m integration` and real AWS credentials.
- **Documentation**: `README.md`, `docs/architecture.md`,
  `docs/security.md`, `docs/tools.md`, `docs/development.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- **Local development environment**: `.env.example`, `pyproject.toml`
  (`ruff`, `mypy`, `pytest` configured), editable install via
  `pip install -e ".[dev]"`.
- **Containerization**: `Dockerfile` (slim Python 3.12 base, non-root
  user, no credentials baked in, credentials injected at runtime) and
  `docker-compose.yml` for local development.

## MCP Tools

| Tool | AWS API | Required IAM permission |
|---|---|---|
| `aws_get_caller_identity` | `sts:GetCallerIdentity` | `sts:GetCallerIdentity` |
| `aws_list_regions` | `ec2:DescribeRegions` | `ec2:DescribeRegions` |
| `aws_list_vpcs` | `ec2:DescribeVpcs` (paginated) | `ec2:DescribeVpcs` |
| `aws_list_subnets` | `ec2:DescribeSubnets` (paginated) | `ec2:DescribeSubnets` |
| `aws_list_route_tables` | `ec2:DescribeRouteTables` (paginated) | `ec2:DescribeRouteTables` |

Full input/output schemas, example requests/responses, and the example
least-privilege IAM policy are in `docs/tools.md`.

## Security Controls

1. MCP tool allowlist — exactly 5 tools exist; none accept mutation
   semantics.
2. Application guardrails — `security.guardrails.assert_read_only_operation`,
   enforced centrally via `aws.readonly.call_readonly()` and
   `aws.pagination.paginate()` (every AWS call goes through one of these
   two).
3. Documented, authoritative IAM boundary — example least-privilege policy
   in `docs/tools.md`, explicitly recommending against
   `AdministratorAccess`/`PowerUserAccess`.
4. Credential hygiene — no hard-coded credentials, no credential logging,
   in-memory-only assumed-role credential caching with proactive refresh.
5. Client-safe error translation — AWS/botocore errors are mapped to a
   fixed set of error types before reaching an MCP response; full details
   logged server-side only.

Full threat model and future approval-gate design in `docs/security.md`.

## Test Results

Environment: this repository lives in a git worktree that is **not** an
AWS-configured machine, and no real AWS credentials were available. All
results below are from mocked-AWS unit tests (`moto`) and a manual
end-to-end script driving the real `MCPServer.call_tool()` interface
against `moto`. Real-AWS integration tests were written but **not
executed** — see "Deferred Items".

```
$ ruff check .
All checks passed!

$ ruff format --check .
49 files already formatted

$ mypy src
Success: no issues found in 28 source files

$ pytest --cov=aws_cloudops_mcp --cov-report=term-missing
78 passed, 5 deselected in 1.53s
TOTAL coverage: 95% (465 statements, 24 missed)
```

Unit tests cover (per Milestone 1 spec §19): configuration
(`test_config.py`), the AWS client factory (`test_client_factory.py`), the
STS identity tool / service function (`test_accounts.py`), region listing +
validation (`test_regions.py`), VPC/subnet/route-table listing
(`test_networking.py`), tag normalization (`test_tags.py`), pagination
(`test_pagination.py`), error translation
(`test_execute_tool.py`), read-only guardrails (`test_guardrails.py`),
AssumeRole session caching/refresh (`test_session.py`), and MCP tool
registration (`test_server.py`).

## Manual Validation

Real AWS credentials were not available in this environment. Instead, a
manual validation script drove the actual `MCPServer.call_tool()` path
(the same code path a real MCP client uses) end-to-end against `moto`-
mocked AWS. **All 10 scenarios passed:**

| Scenario | Result |
|---|---|
| `aws_get_caller_identity` | PASS |
| `aws_list_regions` | PASS (38 regions) |
| `aws_list_vpcs` — valid region | PASS |
| `aws_list_vpcs` — **invalid region** | PASS → `INVALID_REGION` envelope, no exception leaked |
| `aws_list_subnets` — VPC-filtered | PASS |
| `aws_list_subnets` — **empty results** (nonexistent VPC filter) | PASS → `data: [], count: 0`, `success: true` |
| `aws_list_route_tables` | PASS |
| `aws_list_vpcs` — **insufficient IAM permissions** (simulated `UnauthorizedOperation`) | PASS → `AUTHORIZATION_ERROR` envelope |
| `aws_list_vpcs` — **pagination** (6 VPCs across pages) | PASS → all 6+ returned, not just the first page |
| `aws_get_caller_identity` — **missing credentials** (env/files cleared) | PASS → `AUTHENTICATION_ERROR` envelope |

Structured JSON logs were verified during this run to contain
`timestamp`/`request_id`/`tool_name`/`account_id`/`region`/`duration_ms`/
`status` on every invocation, and to contain no credential material.

**Not performed** (would require real AWS access, unavailable here):
running the five tools against a live AWS account/region; Docker image
build and run (Docker daemon was not running in this sandbox); a real
`sts:AssumeRole` cross-account call; testing against a genuinely
under-permissioned real IAM role.

## Known Limitations

- Region validation (`aws/regions.py:validate_region_format`) is a format
  check (regex against the `xx-name-N` shape), not a live lookup against
  AWS's actual enabled-region list — a syntactically valid but
  nonexistent/disabled region will fail later, as a normal AWS API/
  connection error, not as `INVALID_REGION` at validation time.
- `aws_list_regions`/`aws_get_caller_identity` do not take a `role_arn`
  tool input; cross-account queries currently rely on the server-wide
  `AWS_ROLE_ARN` setting. Per-call `role_arn` is already supported at the
  `ClientFactory`/service-layer level (see `docs/architecture.md`) and is
  expected to be exposed as a tool input alongside a future multi-account
  discovery tool.
- `SessionManager`'s assumed-role cache is a plain in-process dict with no
  upper bound on the number of distinct role ARNs cached; fine for
  Milestone 1's single-role usage, worth revisiting once multi-account
  tools are added.
- No rate limiting/throttling protection beyond botocore's own retry
  config; a client that calls tools in a tight loop is not throttled by
  this server.

## Files Created

```
aws-cloudops-mcp/
├── README.md
├── LICENSE (Apache-2.0)
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── MILESTONE1_STATUS.md
├── pyproject.toml
├── .gitignore
├── .dockerignore
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── tools.md
│   └── development.md
├── src/aws_cloudops_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── config.py
│   ├── exceptions.py
│   ├── auth/{__init__.py, credentials.py, session.py}
│   ├── aws/{__init__.py, client_factory.py, accounts.py, regions.py,
│   │        networking.py, pagination.py, readonly.py, tags.py}
│   ├── tools/{__init__.py, _shared.py, identity.py, regions.py,
│   │          inventory.py, accounts.py}
│   ├── models/{__init__.py, common.py, responses.py}
│   ├── security/{__init__.py, guardrails.py}
│   └── logging/{__init__.py, setup.py}
└── tests/
    ├── conftest.py
    ├── unit/ (11 test modules, 78 tests)
    └── integration/test_live_aws.py
```

`aws/networking.py`, `aws/pagination.py`, `aws/readonly.py`, `aws/tags.py`,
and `tools/_shared.py` are additions beyond the spec's suggested structure;
the reasoning for each is documented in `docs/architecture.md` under
"Deviations from the suggested repository structure."

## Commands Used

```bash
python -m venv .venv                 # Python 3.14 used locally (see Technical Decisions)
pip install -e ".[dev]"
ruff check .
ruff format .
mypy src
pytest --cov=aws_cloudops_mcp --cov-report=term-missing
python manual_validation.py          # scratch script, not committed
docker build -t aws-cloudops-mcp .   # attempted; Docker daemon unavailable
```

## Issues Found (and fixed during validation)

- `ruff check` initially flagged one line-too-long and one duplicate-set-
  member (`"revoke"` listed twice in `BLOCKED_KEYWORDS`) — both fixed.
- `mypy` initially failed on two boto3-stubs typing issues: (1)
  `boto3.Session(**kwargs)` with a homogeneous `dict[str, str]` didn't
  type-check against `Session.__init__`'s heterogeneous keyword parameters
  — fixed by passing `profile_name=`/`region_name=` explicitly instead of
  `**kwargs`; (2) `session.client(service, ...)` with `service: str`
  cannot match boto3-stubs' per-service `Literal` overloads by
  construction, since `ClientFactory` is intentionally generic across
  services — resolved with a documented, targeted
  `# type: ignore[call-overload]`.
- One unit test asserted `client.meta.config.retries["max_attempts"]`,
  but botocore normalizes that into `total_max_attempts` (=
  `max_attempts + 1`) once a retry `mode` is set — fixed the assertion,
  not the product code.
- The installed MCP Python SDK is v2.x, where `FastMCP` was renamed to
  `MCPServer` (`mcp.server.mcpserver.MCPServer`) with a compatible
  decorator-based API. All code was written against the current
  `MCPServer` API rather than pinning `mcp<2` for the older name.

## Technical Decisions

- **`mcp.server.mcpserver.MCPServer`, not `FastMCP`.** The spec calls for
  "the official MCP Python SDK"; the latest published release (2.1.1) is
  what `pip install mcp` resolves to, and it renamed `FastMCP` →
  `MCPServer`. Building against the current API (rather than pinning an
  older major version to preserve a familiar class name) keeps the
  foundation aligned with the SDK's current direction. The decorator-based
  `.tool()` API, `.list_tools()`, `.call_tool()`, and `.run()` are
  functionally equivalent to what `FastMCP` offered.
- **Repository placement.** This worktree's existing git history belongs
  to an unrelated project ("Claude Trading", an Alpaca paper-trading bot)
  — not an AWS MCP server. Rather than overwrite or intermix with that
  code, `aws-cloudops-mcp/` was created as its own top-level directory
  here, matching the spec's required repository name and structure
  without touching the pre-existing unrelated code.
- **`aws/networking.py` combines VPC/Subnet/RouteTable logic** in one
  module instead of three, since they share tag/route normalization and
  are naturally read together (see `docs/architecture.md`).
- **`aws/pagination.py` + `aws/readonly.py`** centralize *every* AWS API
  call-site (paginated or not) through the guardrail check, rather than
  each service-layer function remembering to call the guardrail itself.
- **`tools/_shared.execute_tool()`** centralizes logging, correlation IDs,
  account-id enrichment, and error-envelope construction so five (and
  later, many more) tool modules don't each reimplement it.
- **Account ID enrichment is best-effort and cached.** `execute_tool()`
  resolves `account_id` via `ClientFactory.get_account_id()` (memoized
  per role ARN) for every tool's response envelope; a failure to resolve
  it does not block the actual tool call — only the real operation's own
  outcome determines success/failure. This avoids one redundant STS call
  per invocation while keeping the envelope informative.
- **AssumeRole is exempt from the read-only guardrail check** — it is
  authentication, not a resource-mutating AWS API call. Documented
  explicitly in `docs/security.md` so this isn't mistaken for a guardrail
  bypass.
- **Region validation is a format check, not a live lookup**, to avoid an
  extra AWS round-trip and keep the check available without credentials;
  see "Known Limitations."
- **Python 3.12 required per spec** (`pyproject.toml: requires-python =
  ">=3.12"`); local validation in this sandbox used Python 3.14 because
  the machine's only `python3.12` binary was a broken symlink
  (`/usr/local/bin/python3.12 -> .../Library/Frameworks/...` pointing at a
  missing framework install) and no other 3.12 interpreter was available.
  3.14 satisfies `>=3.12` and all tooling (ruff/mypy/pytest/moto) ran
  cleanly on it; nothing in the code depends on a 3.14-only feature.

## Deferred Items

- Running against a **real AWS account**: all 5 tools against live AWS,
  the integration test suite (`pytest -m integration`), a real
  `sts:AssumeRole` cross-account call, and testing with an intentionally
  under-permissioned real IAM role.
- **Docker image build/run**: Docker daemon was not running in this
  sandbox; the Dockerfile and docker-compose.yml were written and reviewed
  but not executed. Recommended before Milestone 2: `docker build -t
  aws-cloudops-mcp . && docker run --rm -i -e AWS_ACCESS_KEY_ID -e
  AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_DEFAULT_REGION
  aws-cloudops-mcp`.
- Connecting a **real MCP client** (e.g. Claude Desktop) to the running
  server over stdio — validated here via the SDK's own `call_tool()` API
  in-process instead.
- Everything explicitly out of scope per the spec: Security Groups, NACLs,
  Internet/NAT Gateways, Transit Gateway, VPN, Direct Connect, VPC
  Peering, Route 53, VPC Endpoints, Network Firewall, Load Balancers,
  CloudWatch, CloudTrail, AWS Config, Reachability Analyzer, Flow Logs,
  AWS Organizations/multi-account discovery, topology/path analysis,
  Aviatrix integration, any Azure/GCP functionality, and any
  infrastructure-mutating capability.

## Ready for Milestone 2: YES

The foundation (layered architecture, client factory, auth/session
management, guardrails, logging, error handling, response envelope,
pagination, tag normalization, tests, docs) is in place and validated as
thoroughly as this environment allows. The one open item before Milestone
2 work begins is running the deferred real-AWS and Docker validation
listed above, ideally in an environment with AWS credentials and a running
Docker daemon.

---

## Recommended Git Commit

```
feat: complete milestone 1 AWS MCP foundation
```
