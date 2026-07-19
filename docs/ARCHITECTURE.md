# Architecture

ComfyUI-Doctor is a ComfyUI custom node extension with three main surfaces:

- a Python package that loads inside ComfyUI and registers PromptServer routes
- browser-side JavaScript that renders the Doctor sidebar and panels
- development/test tooling that keeps host compatibility, API contracts, and UI behavior stable

For route-level details, use the machine-readable OpenAPI contract: [`openapi.json`](openapi.json).

## Host Startup

ComfyUI loads the package entry point from `__init__.py`. That file keeps host-facing responsibilities together:

- install or hand off the startup logger
- initialize the full `SmartLogger`
- configure LLM rate and concurrency limits
- create the API logger
- collect a system snapshot
- register PromptServer routes through `api_routes.py`
- expose node mappings and `WEB_DIRECTORY`

`prestartup_script.py` runs earlier in the ComfyUI startup lifecycle. It captures early terminal output before the full package import is available. The main package then hands off that logger so startup logs and runtime logs share one path.

## Backend Layout

The backend is organized around a small entry point and focused service modules:

| Area | Primary files | Responsibility |
| --- | --- | --- |
| Package entry | `__init__.py`, `nodes.py`, `prestartup_script.py` | ComfyUI loading, node export, startup logging |
| API routes | `api_routes.py`, `services/routes.py` | PromptServer HTTP route registration and route handlers |
| Analysis | `analyzer.py`, `pattern_loader.py`, `pipeline/`, `services/prompt_helpers.py` | Error categorization, pattern matching, prompt construction |
| LLM | `llm_client.py`, `session_manager.py`, `services/llm_provider_adapters.py`, `services/llm/` | Provider requests, retry, proxy policy, rate/concurrency limits |
| Security | `security.py`, `outbound.py`, `sanitizer.py`, `services/security/` | SSRF checks, outbound sanitization, admin guard, error envelopes |
| Storage | `services/doctor_paths.py`, `logger.py`, `history_store.py`, `services/secret_store.py` | Canonical data paths, logs, history, encrypted credential storage |
| Diagnostics | `services/diagnostics/`, `services/intent/` | Workflow, dependency, current host model asset folders/loaders, privacy, performance, and signature-pack checks |
| Community | `services/community_feedback.py`, `pipeline/plugins/` | Feedback preview/submission and scan-only plugin trust reporting |
| Telemetry | `telemetry.py`, `web/doctor_telemetry.js` | Local-only opt-in event buffer and UI controls |

The domain packages under `services/llm/`, `services/security/`, `services/infra/`, and `services/community/` provide stable import entry points for code that should not depend on individual implementation file paths.

## API Surface

`api_routes.py` registers the main Doctor and debugger endpoints. Smaller service-owned handlers live in `services/routes.py` and are attached by `api_routes.py`.

The public API groups are:

- debugger status, language, and history
- LLM analysis, chat, provider defaults, key verification, and model listing
- admin-gated server-side credential metadata and storage
- statistics, resolution state, and feedback
- runtime health, diagnostics, and plugin trust reports
- local telemetry controls
- resumable jobs and provider capability status

Write-sensitive routes use the Doctor admin guard. The API error shape is centralized through `services/api_response.py`, and the public contract is captured in `docs/openapi.json`.
Doctor-owned docs use canonical `/doctor/...` route paths. Current ComfyUI hosts may also expose `/api/doctor/...` aliases through host route duplication, but that global alias behavior belongs to the host.

## Data Flows

### Startup and Logging

1. `prestartup_script.py` captures early output.
2. `__init__.py` imports the package with ComfyUI-relative imports.
3. `SmartLogger.install()` takes over logging.
4. The API logger writes operational events to the Doctor data directory.
5. Route registration runs after ComfyUI `server` and `aiohttp` imports are available.

### Error Analysis

1. ComfyUI output is captured by `SmartLogger`.
2. The analyzer and pattern pipeline classify the error.
3. Node/workflow context is collected and pruned.
4. Prompt helpers build a provider-neutral request payload.
5. LLM calls go through adapter, retry, rate-limit, proxy, SSRF, and outbound-sanitization layers.
6. Results are stored in history and exposed to the frontend.

### Chat

1. The frontend sends error context, user messages, provider settings, privacy mode, and optional credentials.
2. Backend routes resolve credentials from request data, environment variables, local provider behavior, or the server-side store.
3. The provider adapter builds the request.
4. The route returns JSON or Server-Sent Events for streaming chat.

### Diagnostics

1. The frontend or caller posts workflow/context data to diagnostics endpoints.
2. `HealthCheckRequest` is parsed by the diagnostics runner.
3. Registered checks inspect workflow lint, dependencies, model assets,
   privacy/security, runtime performance, and signature packs.
4. Reports are saved by the diagnostics store and exposed through report/history endpoints.

Model asset checks use ComfyUI's live `folder_names_and_paths` registry as the
authoritative source when available, including custom roots and registered
extensions. Older hosts retain a bounded fixed fallback. Workflow traversal
also inspects bounded `definitions.subgraphs` content and preserves visible
host plus concrete source provenance for nested assets. Every candidate is
real-path-contained within a registered root before any filesystem probe.

### Telemetry

Telemetry is local-only and disabled by default. When enabled, accepted events are validated against an allowlist and written to the local telemetry buffer. The browser UI can view, export, clear, and toggle telemetry through Doctor endpoints. The integration and stress test lanes use the Playwright harness backend for deterministic telemetry endpoint behavior.

## Frontend Layout

ComfyUI loads frontend assets from `web/`.

| Area | Primary files | Responsibility |
| --- | --- | --- |
| Extension registration | `web/doctor.js`, `web/comfyui_frontend_compat.js` | ComfyUI extension setup and host API compatibility |
| State and API | `web/doctor_state.js`, `web/doctor_api.js`, `web/doctor_actions.js` | UI state, backend requests, user actions |
| Shell UI | `web/doctor_ui.js`, `web/doctor_right_panel.js`, `web/doctor_rendering.js`, `web/doctor_selectors.js` | Sidebar shell, right panel, rendering helpers, selectors |
| Chat | `web/doctor_chat.js`, `web/chat-island.js`, `web/tabs/chat_tab.js`, `web/llm_provider_quick_switch.js` | Chat UI, Preact island, vanilla fallback, provider switch |
| Statistics and diagnostics | `web/statistics-island.js`, `web/tabs/stats_tab.js`, `web/doctor_telemetry.js` | Stats dashboard, health/trust, feedback, telemetry |
| Settings | `web/tabs/settings_tab.js`, `web/llm_key_store.js`, `web/privacy_utils.js` | Provider settings, credential handling, privacy mode |
| Resilience | `web/preact-loader.js`, `web/island_registry.js`, `web/ErrorBoundary.js`, `web/global_error_handler.js` | Local Preact loading, island fallback, error boundaries |

Preact islands improve the Chat and Statistics surfaces, but each island has a vanilla fallback so the sidebar remains usable if the island loader fails.
Validation-error display is normalized in the frontend so known
prompt-validation failures use stable local catalog text and grouping
metadata. Public raw errors and graph links can surface eligible input-level
errors to a visible subgraph boundary while retaining source provenance;
unknown or unproven topology falls back safely without private store access or
breaking runtime error reporting.

## Security and Storage Boundaries

Security-sensitive behavior is centralized:

- SSRF validation guards provider base URLs.
- Outbound sanitization prevents raw private context from leaving the process;
  `Authorization` and `X-API-Key` values are always redacted in text and
  structured payloads, regardless of privacy mode.
- Privacy modes control how much local context can be sent to remote providers.
- Write-sensitive endpoints use the admin guard.
- Server-side credentials use the secret store and are never exposed through status APIs.
- Community plugins are scanned for trust metadata without importing plugin code.
- Telemetry is local-only and opt-in.
- Doctor-owned frontend settings opt out of the host frontend's independent
  setting-change telemetry.

Storage should go through `services/doctor_paths.py` so Desktop, portable, and
standard ComfyUI installations resolve Doctor data consistently. Runtime
identity and storage evidence are separate: a managed Desktop interpreter can
remain classified as Desktop while the data directory comes from ComfyUI's
private system-user API.

## Testing Architecture

The full local acceptance gate is `scripts/run_full_tests_windows.ps1` on Windows or `scripts/run_full_tests_linux.sh` on Linux/WSL. It covers:

1. supply-chain dependency scan
2. detect-secrets
3. pre-commit hooks
4. host-like package/startup validation
5. backend unit tests
6. default Playwright E2E

Additional focused lanes:

- `npm run test:integration` runs `@integration` telemetry tests against the harness backend by default, or a live backend when `COMFYUI_URL` is set.
- `npm run test:stress` runs opt-in `@stress` telemetry burst/state tests against the harness backend.
- `python scripts/focused_gate.py` runs the supplemental focused security/contract/E2E regression lane. It is not a replacement for the full acceptance gate.
- `python scripts/check_host_compatibility.py` evaluates source-linked
  contracts with separate frontend runtime lanes for the Desktop bundle,
  ComfyUI package pin, and standalone frontend source.

## Compatibility Principles

- Keep package imports compatible with ComfyUI custom-node loading.
- Keep frontend registration compatible with current and deprecated host sidebar APIs where support exists.
- Keep host compatibility checks version-aware and aligned with prompt queue
  source metadata, execution event payloads, model registries, nested workflow
  serialization, validation-error state, setting telemetry, Desktop layout,
  system statistics metadata, job-cancel contracts, and frontend queue/cancel
  adoption.
- Keep public route changes reflected in `docs/openapi.json`.
- Keep local harness tests deterministic; live backend tests must be explicit opt-in.
