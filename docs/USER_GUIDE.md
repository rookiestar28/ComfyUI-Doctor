# ComfyUI-Doctor User Guide

This guide keeps the detailed user-facing workflow out of the main README while preserving the practical operating notes for daily use.

## Runtime Diagnostics

Doctor starts with ComfyUI and passively monitors runtime output. When it sees a traceback or known failure pattern, it records the event, matches the best local suggestion, and updates the Doctor UI.

Captured context can include:

- Python traceback text.
- Matched JSON pattern ID and localized suggestion.
- Recent ComfyUI execution/progress event context.
- Node ID, node name, node class, and custom-node path when available.
- System context useful for debugging, such as Python, PyTorch, CUDA, and package information.

## Doctor Sidebar

Open the **Doctor** entry from ComfyUI's left sidebar.

### Chat Tab

The Chat tab shows the latest error context and supports optional LLM-assisted debugging.

Use it when:

- The built-in suggestion is not enough.
- You need a multi-turn explanation of a traceback.
- You want to compare likely causes across workflow, model, and environment context.

Cloud providers require a credential. Local providers such as Ollama and LMStudio can be used without a cloud credential.

### Statistics Tab

The Statistics tab groups operational views:

- Recent error counts and trend windows.
- Top matched patterns and category breakdown.
- Resolution status controls for the latest error.
- Local diagnostics and intent signature checks.
- Trust and health report for Doctor runtime and plugin state.
- Optional local telemetry controls.
- Quick Community Feedback preview and submit tools.

### Settings Tab

Use Settings for routine configuration:

- UI and suggestion language.
- AI provider and base URL.
- Session-only credential input.
- Model selection or manual model entry.
- Privacy mode.
- Right-side latest-diagnosis auto-open behavior.
- Optional Advanced Key Store for server-side credential storage.

Doctor also registers compatibility defaults through the current ComfyUI frontend settings API so modern frontend builds retain expected defaults. The sidebar Settings tab remains the recommended surface for normal use.

## Right-Side Latest Diagnosis Panel

Doctor can show a compact right-side panel when a new error is detected. It displays:

- Current health indicator.
- Latest error summary.
- Local suggestion.
- Timestamp.
- Node context when available.
- A locate action when the related node can be found on the canvas.

The auto-open behavior is controlled in **Doctor -> Settings**.

## Smart Debug Node

The **Smart Debug Node** can be inserted inline with workflow connections. It passes data through unchanged and logs useful inspection details such as type, shape, dtype, device, and value statistics when available.

Use it for debugging data flow problems where a traceback does not clearly identify the bad intermediate value.

## LLM Providers

The Settings UI supports:

- OpenAI-compatible APIs.
- Anthropic.
- DeepSeek.
- Groq.
- Google Gemini.
- xAI.
- OpenRouter.
- Ollama.
- LMStudio.

Provider defaults are fetched from Doctor's backend. Ollama and LMStudio base URLs can be overridden with environment variables when Windows, WSL2, Docker, or remote-host layouts need explicit routing.

## Privacy Modes

Privacy mode controls how much sensitive context is removed before sending an LLM request.

| Mode | Use Case | Behavior |
| --- | --- | --- |
| `none` | Verified local LLM only | Sends raw context needed for debugging. |
| `basic` | Default cloud-provider use | Removes common local paths, credential-looking values, emails, private IPs, and URL credentials. |
| `strict` | Shared or compliance-sensitive use | Applies stronger masking for additional network and identity-like values. |

Error messages, node names, model names, and workflow structure may remain because they are often required to diagnose the issue.

## Diagnostics and Signature Packs

Diagnostics can run without an LLM call. Built-in JSON signature packs provide deterministic checks for common workflow and environment problems, including:

- Model path anomalies.
- Missing assets or placeholder values.
- Node configuration anti-patterns.
- Environment mismatch hints.

Diagnostic matches include confidence and provenance metadata so results can be reviewed without treating them as a security or malware verdict.

## Quick Community Feedback

The Statistics tab includes a feedback flow for preparing sanitized pattern suggestions.

Typical flow:

1. Open **Doctor -> Statistics**.
2. Review or edit the generated candidate.
3. Preview the sanitized payload.
4. Submit when server-side GitHub configuration and admin authorization are available.
5. Review the generated pull request on GitHub.

Submit actions are admin-gated. Preview is intended to help users inspect what will be sent before any write action occurs.

## Data Locations

Doctor resolves its runtime state paths for regular ComfyUI installs, portable layouts, and ComfyUI Desktop-style `.venv` installs. The health endpoint exposes path diagnostics for troubleshooting.

Runtime-generated timestamps are serialized as UTC with a trailing `Z`. Older persisted records with naive timestamps remain readable for compatibility.
