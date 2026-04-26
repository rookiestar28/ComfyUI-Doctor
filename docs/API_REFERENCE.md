# API Reference

This document lists the public ComfyUI-Doctor HTTP endpoints. Exact response payloads can evolve, but the endpoint roles and admin-guard expectations are stable public behavior.

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

Doctor normalizes provider-specific behavior for OpenAI-compatible APIs, Anthropic, and Ollama behind a shared backend adapter layer. The route endpoints still enforce SSRF checks, credential resolution, privacy sanitization, retry/concurrency limits, and streaming response handling.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/provider_defaults` | Return provider default base URLs. |
| `POST` | `/doctor/analyze` | Run single-shot LLM analysis for an error context. |
| `POST` | `/doctor/chat` | Run the interactive chat flow, including SSE streaming when requested. |
| `POST` | `/doctor/verify_key` | Validate provider connectivity and credential availability. |
| `POST` | `/doctor/list_models` | List models from the selected provider when supported. |
| `GET` | `/doctor/ui_text` | Return localized UI text for the frontend. |

LLM failure responses use the standard JSON error envelope. The chat streaming path reports stream connection or provider errors as terminal SSE events.

## Credential Store Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/secrets/status` | Return provider credential source status without exposing secret values. |
| `PUT` | `/doctor/secrets` | Save a provider credential to the optional server-side store. |
| `DELETE` | `/doctor/secrets/{provider}` | Delete a stored provider credential. |

## Statistics, Feedback, and Health Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/doctor/statistics` | Return error statistics for the dashboard. |
| `POST` | `/doctor/statistics/reset` | Clear statistics/history data. |
| `POST` | `/doctor/mark_resolved` | Mark the latest matching error as resolved, unresolved, or ignored. |
| `POST` | `/doctor/feedback/preview` | Build and sanitize a community feedback preview. |
| `POST` | `/doctor/feedback/submit` | Submit sanitized feedback through the configured GitHub flow. |
| `GET` | `/doctor/health` | Return Doctor runtime health and path diagnostics. |
| `GET` | `/doctor/plugins` | Return scan-only plugin trust information. |

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
