# ComfyUI-Doctor

[繁中](docs/readme/README.zh-TW.md) | [简中](docs/readme/README.zh-CN.md) | [日本語](docs/readme/README.ja.md) | [한국어](docs/readme/README.ko.md) | [Deutsch](docs/readme/README.de.md) | [Français](docs/readme/README.fr.md) | [Italiano](docs/readme/README.it.md) | [Español](docs/readme/README.es.md) | English |

<div align="center">
<img src="assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor is a real-time diagnostics and debugging assistant for ComfyUI. It captures runtime errors, identifies likely node context, shows actionable local suggestions, and can optionally use an LLM chat workflow for deeper troubleshooting.

<details>
<summary><h2>Latest Updates - Click to expand</h2></summary>

<details>
<summary><strong>Unified LLM Context, Provider Handling, and API Hardening</strong></summary>

- Routed LLM prompt context through the analysis pipeline so sanitized tracebacks, node context, recent logs, workflow snippets, and system details use one structured path.
- Centralized OpenAI-compatible, Anthropic, and Ollama request/response handling for chat, analysis, model listing, and provider connectivity checks.
- Standardized API error payloads with `success`, `error`, and `message` fields while preserving existing success response shapes.
- Improved node-context stability with immutable, validated node identity data used by analysis, locate actions, and prompt context.
- Removed obsolete no-op diagnostics output now that concrete local diagnostics checks are available.
- Hardened import fallback behavior and logger traceback reset handling for more reliable ComfyUI host loading and history clearing.

</details>

<details>
<summary><strong>Host Compatibility, Security Controls, and Coverage Baseline</strong></summary>

- Added host compatibility checks for the ComfyUI, ComfyUI frontend, and Desktop surfaces Doctor depends on.
- Updated frontend settings integration to prefer the current ComfyUI settings API while keeping legacy fallback behavior isolated.
- Improved execution-error lineage enrichment from recent execution/progress events.
- Added strict admin-token mode for shared-server deployments and clearer loopback-mode warnings.
- Documented encrypted server-side credential storage metadata and the current encrypt-then-MAC design.
- Added an optional coverage baseline lane; the default full local validation flow remains unchanged.

</details>
</details>

## Core Features

- Real-time ComfyUI console/error capture from startup.
- Built-in suggestions from 58 JSON-based error patterns, including 22 core patterns and 36 community-extension patterns.
- Validated node context extraction for recent workflow execution errors when ComfyUI provides enough event data.
- Doctor sidebar with Chat, Statistics, and Settings tabs.
- Optional LLM analysis through OpenAI-compatible services, Anthropic, Gemini, xAI, OpenRouter, Ollama, and LMStudio, with unified provider request/response handling.
- Privacy controls for outbound LLM requests, including path/key/email/IP sanitization modes.
- Optional server-side credential store with admin guarding and encryption-at-rest support.
- Local diagnostics, statistics, plugin trust report, telemetry controls, and community feedback preview/submit tools.
- Consistent JSON error envelopes for Doctor API failures.
- Full UI and suggestion language support for English, Traditional Chinese, Simplified Chinese, Japanese, Korean, German, French, Italian, and Spanish.

## Screenshots

<div align="center">
<img src="assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## Installation

### ComfyUI-Manager

1. Open ComfyUI and click **Manager**.
2. Select **Install Custom Nodes**.
3. Search for `ComfyUI-Doctor`.
4. Install and restart ComfyUI.

### Manual Install

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Restart ComfyUI after cloning. Doctor should print its startup diagnostics and register the `Doctor` sidebar entry.

## Basic Usage

### Automatic Diagnostics

After installation, Doctor passively records ComfyUI runtime output, detects tracebacks, matches known error patterns, and shows the latest diagnosis in the sidebar and optional right-side report panel.
When optional LLM analysis is used, Doctor builds prompt context from the same structured pipeline that handles sanitization, node context, execution logs, workflow pruning, and system information.

### Doctor Sidebar

Open **Doctor** in ComfyUI's left sidebar:

- **Chat**: review latest error context and ask follow-up debugging questions.
- **Statistics**: inspect recent error trends, diagnostics, trust/health information, telemetry controls, and feedback tools.
- **Settings**: choose language, LLM provider, base URL, model, privacy mode, auto-open behavior, and optional server-side credential storage.

### Smart Debug Node

Right-click the canvas, add **Smart Debug Node**, and place it inline to inspect passing data without changing workflow output.

## Optional LLM Setup

Cloud providers require a credential supplied through the session-only UI field, environment variables, or the optional admin-gated server store. Local providers such as Ollama and LMStudio can run without a cloud credential.
Doctor normalizes provider-specific request and response formats for OpenAI-compatible APIs, Anthropic, and Ollama so chat, single-shot analysis, model listing, and connectivity checks share the same backend behavior.

Recommended defaults:

- Use **Privacy Mode: Basic** or **Strict** for cloud providers.
- Use environment variables for shared or production-like environments.
- Set `DOCTOR_ADMIN_TOKEN` and `DOCTOR_REQUIRE_ADMIN_TOKEN=1` on shared servers.
- Keep local-only loopback convenience mode for single-user desktop use only.

## Documentation

- [User Guide](docs/USER_GUIDE.md): UI walkthrough, diagnostics, privacy modes, LLM setup, and feedback flow.
- [Configuration and Security](docs/CONFIGURATION_SECURITY.md): environment variables, admin guard behavior, credential storage, outbound safety, telemetry, and CSP notes.
- [API Reference](docs/API_REFERENCE.md): public Doctor and debugger endpoints.
- [Validation Guide](docs/VALIDATION.md): local full-gate commands and optional compatibility/coverage lanes.
- [Plugin Guide](docs/PLUGIN_GUIDE.md): community plugin trust model and plugin authoring notes.
- [Plugin Migration](docs/PLUGIN_MIGRATION.md): migration tooling for plugin manifests and allowlists.
- [Outbound Safety](docs/OUTBOUND_SAFETY.md): static checker and outbound request safety rules.

## Supported Error Patterns

Patterns are stored as JSON files under `patterns/` and can be updated without code changes.

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

Community packs currently cover common ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, checkpoint, sampler, scheduler, and CLIP failure modes.

## Validation

For local CI-parity validation, use the project full-test script:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

The full gate covers secrets detection, pre-commit hooks, host-like startup validation, backend unit tests, and frontend Playwright E2E tests. See [Validation Guide](docs/VALIDATION.md) for the explicit staged commands and optional lanes.

## Requirements

- ComfyUI custom-node environment.
- Python 3.10 or newer.
- Node.js 18 or newer for frontend E2E validation only.
- No runtime Python package dependency is required beyond ComfyUI's bundled environment and Python standard library.

## License

MIT License

## Contributing

Pattern and documentation contributions are welcome. For code changes, run the full validation gate before opening a pull request and avoid committing generated local state, logs, credentials, or internal planning files.
