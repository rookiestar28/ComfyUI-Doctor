# API Reference

This document lists the public ComfyUI-Doctor HTTP endpoints. Exact response payloads can evolve, but the endpoint roles and admin-guard expectations are stable public behavior.

Machine-readable contract: [`openapi.json`](openapi.json).

## Route Forms and Host Aliases

The canonical Doctor route form is `/doctor/...`. Current ComfyUI hosts may also expose `/api/doctor/...` as a host-provided alias where ComfyUI route duplication applies.

Doctor documentation and examples use canonical `/doctor/...` paths. Clients running inside a current ComfyUI host may use `/api/doctor/...` when their integration layer expects the host API prefix, but Doctor does not own ComfyUI's global alias behavior.

## Prompt Usage-Source Policy

Doctor does not currently queue host prompts directly. If a future Doctor feature queues a host prompt, it should identify itself only with a non-secret source string such as `comfyui-doctor`.

Usage-source metadata must not include secrets, raw prompts, private paths, cookies, credentials, tokens, API keys, private URLs, or equivalent sensitive material.

## Admin-Gated Writes

Write-sensitive endpoints require admin authorization unless desktop loopback convenience mode applies. For shared servers, configure `DOCTOR_ADMIN_TOKEN` and `DOCTOR_REQUIRE_ADMIN_TOKEN=1`.

JSON error responses use a consistent envelope:

```json
{
  "success": false,
  "error": "machine_or_legacy_error_text",
  "message": "Human-readable error message"
}
```

Some endpoint-specific failure payloads may include additional fields such as `models`, `is_local`, `field_errors`, or `statistics`; existing success payloads keep their documented shapes.

Denied writes use:

- `401` for missing or invalid token authorization.
- `403` for policy-denied remote administration.

## Debugger Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/debugger/last_analysis` | Return current Doctor status, latest error, suggestion, language, and node context when available. |
| `GET` | `/debugger/history` | Return recent error-analysis history. |
| `POST` | `/debugger/set_language` | Change the suggestion language. |
| `POST` | `/debugger/clear_history` | Clear recorded error history. |

## LLM and Chat Endpoints

Doctor normalizes provider-specific behavior for OpenAI-compatible APIs, Anthropic, and Ollama behind a shared backend adapter layer. The route endpoints still enforce the operator-approved destination list (requests for any other base URL return `destination_not_allowed`; see [Configuration and Security](CONFIGURATION_SECURITY.md#llm-destinations)), credential resolution, privacy sanitization, retry/concurrency limits, and streaming response handling.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/provider_defaults` | Return provider default base URLs. |
| `POST` | `/doctor/analyze` | Run single-shot LLM analysis for an error context. |
| `POST` | `/doctor/chat` | Run the interactive chat flow, including SSE streaming when requested. |
| `POST` | `/doctor/verify_key` | Validate provider connectivity and credential availability. |
| `POST` | `/doctor/list_models` | List models from the selected provider when supported. |
| `GET` | `/doctor/ui_text` | Return localized UI text for the frontend. |

LLM failure responses use the standard JSON error envelope. The chat streaming path reports stream connection or provider errors as terminal SSE events.

`/doctor/chat` and `/doctor/analyze` accept an optional workflow as a JSON string or an object, either in the
host's serialized-graph shape (`{"nodes": [...], "links": [...]}`) or as an API prompt keyed by node id. The
failed node is looked up by its exact execution id first (for example `12:3`) and then by its last segment;
a workflow in which it cannot be found, or one that is not valid JSON, never fails the request: the prompt is
built from the error text alone. A workflow longer than the request budget is shortened to the failed node and
its connected neighbors (the largest neighborhood that fits), or cut to the budget when even the node alone does
not fit.

The shipped sidebar sends no workflow with `/doctor/chat` by default. When the user turns on
"Send the workflow with chat questions" (off by default) it adds the serialized root graph as
`error_context.workflow`, a JSON string; a graph longer than 256,000 characters is left out whole rather than cut.
The workflow text is sanitized with the rest of the request according to the request's privacy mode, like any
other outbound text.

### Chat stream events

A streaming `/doctor/chat` reply is a Server-Sent Events stream. Every event is one `data:` line that holds a JSON object:

| Event | Shape | Meaning |
| --- | --- | --- |
| Content | `{"delta": "<text>", "done": false}` | A fragment of the reply, in order. |
| End | `{"delta": "", "done": true}` | The provider finished the reply. |
| Error | `{"error": "<message>", "code": "<code>", "done": true}` | The stream failed; this is the terminal event. |
| Fix suggestion | `{"type": "fix_suggestion", "data": {"fixes": [...]}}` | Optional, at most once, after the `done` event. |

When the complete reply contains a fenced `json` block with a `fixes` list in which every entry is an object with the keys `node_id`, `widget`, `from`, `to` and `reason`, the route writes one `fix_suggestion` event after the `done` event. Its `data` is that block's parsed JSON; only the first matching block is used. Nothing is written when the block is missing, is not valid JSON, or fails that check. The event has neither `delta` nor `done`, so a client that stops reading at `done` never sees it. The shipped sidebar reads only `delta`, `done` and `error` and ignores it. Non-streaming replies never carry it.

## Credential Store Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/secrets/status` | Return provider credential source status without exposing secret values. |
| `PUT` | `/doctor/secrets` | Save a provider credential to the optional server-side store. |
| `DELETE` | `/doctor/secrets/{provider}` | Delete a stored provider credential. |

`GET /doctor/secrets/status` also reports `store.state` (`ok`, `empty`, `locked_key_required`, `locked_key_mismatch` or `corrupt`). While an encrypted store is locked, `PUT` and `DELETE` return HTTP 409 with error code `secret_store_locked` and leave the store file unchanged.

## Statistics, Feedback, and Health Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/statistics` | Return error statistics for the dashboard. |
| `POST` | `/doctor/statistics/reset` | Clear statistics/history data. |
| `POST` | `/doctor/mark_resolved` | Mark the latest matching error as resolved, unresolved, or ignored. |
| `POST` | `/doctor/feedback/preview` | Build and sanitize a community feedback preview. |
| `POST` | `/doctor/feedback/submit` | Submit sanitized feedback through the configured GitHub flow. |
| `GET` | `/doctor/health` | Return Doctor runtime health, path diagnostics, and bounded nonfatal host advisories. |
| `GET` | `/doctor/plugins` | Return scan-only plugin trust information. |

Path diagnostics in `/doctor/health` report runtime identity separately from
storage evidence. For example, a managed Desktop runtime can report
`install_mode=desktop` while `storage_source` identifies ComfyUI's private
system-user API.

The optional `dynamic_vram_advisory` member is `{"active": false}` when no
supported fallback warning has been observed. When active, it contains only
allowlisted reason codes, fixed nonfatal guidance, a bounded repeat count, and
UTC timestamps. It is triggered only by three exact supported ComfyUI
DynamicVRAM source messages: the prior/current PyTorch fallback forms and the
`comfy-aimdo` fallback. It does not expose the raw host log line, infer
activation from a version or device name alone, or replace
`/debugger/last_analysis`.

## Telemetry Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/telemetry/status` | Return telemetry enabled/disabled state. |
| `GET` | `/doctor/telemetry/buffer` | Return local telemetry buffer contents. |
| `POST` | `/doctor/telemetry/track` | Add a telemetry event when telemetry is enabled. |
| `POST` | `/doctor/telemetry/clear` | Clear telemetry buffer. |
| `GET` | `/doctor/telemetry/export` | Export local telemetry buffer. |
| `POST` | `/doctor/telemetry/toggle` | Enable or disable telemetry. |

## Jobs and External Provider Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/jobs/{job_id}` | Return resumable job state. |
| `POST` | `/doctor/jobs/{job_id}/resume` | Resume an eligible failed, cancelled, or pending job. |
| `POST` | `/doctor/jobs/{job_id}/cancel` | Cancel an eligible job. |
| `GET` | `/doctor/providers/{provider_id}/status` | Return external enrichment provider capability status. |

## Diagnostics Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/doctor/health_check` | Run local diagnostics for a workflow/context payload. |
| `GET` | `/doctor/health_report` | Return the latest diagnostics report. |
| `GET` | `/doctor/health_history` | Return diagnostics history. |
| `POST` | `/doctor/health_ack` | Acknowledge, ignore, or resolve diagnostics issues. |

Diagnostics reports are produced by concrete local checks such as workflow linting, dependency checks, model asset checks, privacy/security checks, runtime performance checks, and signature-pack checks.

An issue target's `node_id` may be a nonnegative safe integer or an opaque string of up to 1024
Unicode code points. Strings preserve their exact spelling, including colons and leading zeros;
surrounding whitespace, control characters and unpaired surrogates are rejected. The backend and the
sidebar use one list of surrounding-whitespace characters (space, U+0085, U+00A0, U+1680, U+2000-U+200A,
U+2028, U+2029, U+202F, U+205F, U+3000 and U+FEFF), so an ID one side accepts is accepted by the other.
Intent-signal evidence (`node_ids`) lists IDs exactly as the workflow spells them, and an ID that is not
valid is ignored. Clients must not
cast these IDs to integers or split them on colons. A target may be absent when no safe target is
available. Ambiguous targets cannot authorize a fix. A workflow node whose ID is malformed or shared
with another node keeps its findings, but they carry no `node_id` and are described by their position
in the workflow (for example `unidentified node at nodes[2]`), so a client cannot locate or fix the
wrong node. Each group of nodes that share an ID is reported once as a `Duplicate Node ID` warning.

Model asset diagnostics use the current host's registered model roots and
extensions when available, including custom folders and `.pt2`/`.sft`
artifacts. They also inspect bounded nested subgraph definitions while
preserving visible-host and concrete source-loader provenance for promoted
first-party model, image, video, output-image, and audio values. Positional
widget values remain authoritative and uniquely matched named values are
fallback only. Input media/caption-pair and registered dataset folders are
contained without content enumeration. Unknown custom upload-loader semantics
are not guessed without authoritative node-definition flags. Older hosts
retain bounded legacy folder fallbacks, and every filesystem candidate must
remain contained within an authoritative root before it is probed.
The exact first-party `SAM3DBody_Loader` resolves `model_file` through the
registered `detection` category and never substitutes checkpoints when that
category is unavailable.
