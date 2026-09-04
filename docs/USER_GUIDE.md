# ComfyUI-Doctor User Guide

This guide keeps the detailed user-facing workflow out of the main README while preserving the practical operating notes for daily use.

## Runtime Diagnostics

Doctor starts with ComfyUI and passively monitors runtime output. When it sees a traceback or known failure pattern, it records the event, matches the best local suggestion, and updates the Doctor UI.

Captured context can include:

- Python traceback text.
- Matched JSON pattern ID and localized suggestion.
- Recent ComfyUI execution/progress event context.
- Validated node ID, node name, node class, subgraph lineage, and custom-node path when available.
- Prompt-validation details normalized into safe local display summaries when ComfyUI reports structured validation errors.
- System context useful for debugging, such as Python, PyTorch, CUDA, and package information.

When optional LLM analysis is enabled, Doctor builds the LLM prompt context from the same analysis pipeline. That structured context can include the sanitized traceback, failed-node details, recent execution logs, a pruned workflow subset, and canonical system information.
Known host validation failures use Doctor's local catalog copy and grouping so repeated validation/runtime reports are easier to scan. Current aggregate validation groups, missing model/media/swap-node states, and duplicate validation/runtime reports are normalized for display; account precondition failures are filtered from the runtime error list. Unknown validation types fall back to generic safe copy while preserving enough detail for local debugging.
For nested workflows, eligible input-level validation failures can be surfaced
to the visible outer subgraph when public raw errors and graph links prove the
boundary. The displayed error retains its concrete source execution ID and
input provenance, and ambiguous topology stays on the source node.

## Doctor Sidebar

Open the **Doctor** entry from ComfyUI's left sidebar.

### Chat Tab

The Chat tab shows the latest error context and supports optional LLM-assisted debugging.

Use it when:

- The built-in suggestion is not enough.
- You need a multi-turn explanation of a traceback.
- You want to compare likely causes across workflow, model, and environment context.

Cloud providers require a credential. Local providers such as Ollama and LMStudio can be used without a cloud credential.
Provider-specific request and response formats are normalized by Doctor's backend for chat, single-shot analysis, model listing, and connectivity checks.

### Statistics Tab

The Statistics tab groups operational views:

- Recent error counts and trend windows.
- Top matched patterns and category breakdown.
- Resolution status controls for the latest error.
- Local diagnostics and intent signature checks.
- Trust and health report for Doctor runtime, plugin state, and supported nonfatal host fallback guidance.
- Optional local telemetry controls.
- Quick Community Feedback preview and submit tools.

When current ComfyUI reports that automatic DynamicVRAM fell back to the
legacy model patcher, Trust & Health can show fixed local guidance. Automatic
DynamicVRAM requires PyTorch 2.8 or later and working `comfy-aimdo`; this does
not change ComfyUI's base PyTorch 2.7 support. ComfyUI recommends PyTorch 2.12
or later for DynamicVRAM. Doctor does not turn these exact fallback warnings
into a runtime error or send the raw host message to an LLM/provider.

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
All Doctor-owned frontend settings explicitly disable the host frontend's
setting-change telemetry. This is separate from Doctor's own local, opt-in
telemetry controls in the Statistics tab.

## Right-Side Latest Diagnosis Panel

Doctor can show a compact right-side panel when a new error is detected. It displays:

- Current health indicator.
- Latest error summary.
- Local suggestion.
- Timestamp.
- Node context when available.
- A locate action when the related node can be found on the canvas.

The auto-open behavior is controlled in **Doctor -> Settings**.
When host canvas APIs are available, locate actions focus the resolved node
bounds and can switch into the relevant graph or real subgraph for nested
execution IDs. Executable group IDs continue to focus their group host rather
than being treated as subgraphs.

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
OpenAI-compatible providers, Anthropic, and Ollama use dedicated backend adapters so request payloads, non-stream responses, streaming chunks, and model lists are parsed consistently.

## Privacy Modes

Privacy mode controls how much sensitive context is removed before sending an LLM request.

| Mode | Use Case | Behavior |
| --- | --- | --- |
| `none` | Verified local LLM only | Preserves debugging context, but always redacts named sensitive headers. |
| `basic` | Default cloud-provider use | Removes common local paths, credential-looking values, emails, private IPs, and URL credentials. |
| `strict` | Shared or compliance-sensitive use | Applies stronger masking for additional network and identity-like values. |

Error messages, node names, model names, and workflow structure may remain because they are often required to diagnose the issue.

## Diagnostics and Signature Packs

Diagnostics can run without an LLM call. Built-in JSON signature packs provide deterministic checks for common workflow and environment problems, including:

- Model path anomalies.
- Current ComfyUI model asset folder and loader expectations sourced from the
  live host model registry when available, including custom registered roots
  and extensions such as `.pt2` and `.sft`.
- Exact `SAM3DBody_Loader` model-file resolution against the registered
  `detection` root, without accepting a checkpoints copy when detection is
  unavailable.
- Bounded nested `definitions.subgraphs` scanning for promoted and
  non-promoted model references with visible-host and source-node provenance.
- First-party promoted image, video, output-image, and audio checks that keep
  the visible host as the user-facing target while retaining the concrete
  source loader. Unknown custom upload loaders are not guessed from filename
  extensions when authoritative node-definition flags are unavailable.
- Contained first-party input media/caption-pair folders and registered
  training dataset folders. Doctor checks the folder itself without reading
  or enumerating dataset content.
- Real-path containment that rejects external, traversal, cross-drive,
  null-byte, and symlink-escape candidates before any asset probe.
- Missing assets or placeholder values.
- Node configuration anti-patterns.
- Environment mismatch hints, including Python 3.10+ support and conservative
  PyTorch-below-2.7 guidance when the version is parseable.

Diagnostic matches include confidence and provenance metadata so results can be reviewed without treating them as a security or malware verdict.
The diagnostics registry only runs concrete production checks; obsolete placeholder checks are not included in health reports.

Frontend error and credential-store status messages are displayed as literal
text. Backend or exception strings are not treated as trusted markup.

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

Doctor resolves runtime state paths through ComfyUI's private system-user
directory when the host exposes that API. Older `user/ComfyUI-Doctor` layouts
remain readable through fallback and migration behavior. Runtime identity is
reported separately from storage selection, so a managed ComfyUI Desktop
`.venv` remains identified as Desktop while its Doctor state stays in the
private system-user path. The health endpoint exposes both identity and
storage-source diagnostics for standard, portable, and Desktop layouts.

Runtime-generated timestamps are serialized as UTC with a trailing `Z`. Older persisted records with naive timestamps remain readable for compatibility.
