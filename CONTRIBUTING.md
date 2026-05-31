# Contributing

Thanks for helping improve ComfyUI-Doctor. This project is a ComfyUI custom node, so changes must preserve both normal Python package behavior and ComfyUI host-loading behavior.

## Before You Start

Required local tools:

- Python 3.10 or newer
- Node.js 18 or newer
- npm 9 or newer
- Git

Recommended local setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm install
```

Use one Python interpreter consistently for setup, tests, and validation. On Windows, the repository full-test script uses `.venv` as the project-local environment.

## Repository Orientation

Start with these public docs:

- [Architecture](docs/ARCHITECTURE.md) for package startup, backend services, frontend modules, security boundaries, and test lanes.
- [API reference](docs/API_REFERENCE.md) and [OpenAPI contract](docs/openapi.json) for route-level behavior.
- [Validation guide](docs/VALIDATION.md) for supported validation workflows.
- [Configuration and security](docs/CONFIGURATION_SECURITY.md) for credential, admin, and deployment safety notes.
- [Outbound safety](docs/OUTBOUND_SAFETY.md) for network-boundary expectations.

Key source areas:

- `__init__.py`, `prestartup_script.py`, and `nodes.py` handle ComfyUI package loading.
- `api_routes.py` and `services/routes.py` register and implement HTTP routes.
- `services/llm/`, `services/security/`, `services/infra/`, and `services/community/` provide stable service-domain entry points.
- `web/` contains the ComfyUI browser extension, sidebar UI, Preact islands, and vanilla fallbacks.
- `tests/` contains backend, host-load, and Playwright coverage.

## Development Workflow

1. Keep changes scoped to the feature or fix.
2. Preserve existing compatibility boundaries unless the change explicitly updates them.
3. Add or update tests for the bug class or behavior being changed.
4. Keep public documentation synchronized when user-facing behavior, API routes, setup, or validation flow changes.
5. Run targeted tests first, then the full local gate before submitting a pull request.

For route changes, update `docs/openapi.json` and add or update route/spec drift coverage. For frontend changes, prefer user-visible assertions in Playwright over checks that only prove the page loaded.

## Testing Requirements

Follow the repository test SOPs in this order:

1. [Test SOP](tests/TEST_SOP.md)
2. [E2E testing notice](tests/E2E_TESTING_NOTICE.md)
3. [E2E testing SOP](tests/E2E_TESTING_SOP.md)

Preferred full local validation on Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_full_tests_windows.ps1
```

Preferred full local validation on Linux or WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

The full gate covers dependency safety checks, detect-secrets, pre-commit hooks, host-like package/startup validation, backend tests, and default Playwright E2E.

Supplemental lanes:

- `npm run test:integration` runs opt-in integration-tagged telemetry tests. It uses the Playwright harness backend by default unless `COMFYUI_URL` is set.
- `npm run test:stress` runs opt-in stress-tagged telemetry burst/state tests.
- `python scripts/focused_gate.py` runs focused security, contract, and regression checks. It supplements the full gate and does not replace it.

## Documentation Expectations

Documentation should be public-safe, user-oriented, and synchronized with behavior:

- Update architecture docs when module boundaries, startup behavior, test lanes, or compatibility assumptions change.
- Update API docs and OpenAPI when routes, methods, request payloads, response payloads, or admin requirements change.
- Update setup and validation docs when tooling, prerequisites, or command flows change.
- Keep examples free of real tokens, private URLs, private hostnames, local state paths, and user-specific data.

## Security and Privacy Boundaries

Never commit secrets, credentials, cookies, tokens, local state, generated reports, private host data, or workstation-specific files.

Security-sensitive changes should account for:

- admin-token enforcement on write-sensitive endpoints
- SSRF and private-network protections for outbound provider URLs
- outbound sanitization and privacy modes before remote LLM calls
- server-side credential storage behavior
- local-only telemetry expectations
- plugin trust scanning without importing third-party plugin code

If a change touches these boundaries, include focused tests for the failure mode and run the full validation gate.

## Pull Request Readiness

Before opening a pull request:

- Rebase or merge current upstream changes as appropriate for your branch.
- Confirm public docs match the behavior being submitted.
- Run targeted tests for the changed area.
- Run the full local validation gate.
- Review staged files to ensure only intended public-safe files are included.
- Use a concise Conventional Commit style subject for commits.

Keep pull requests narrow enough to review. When a change spans backend, frontend, tests, and docs, describe the user-visible behavior and the validation commands that passed.
