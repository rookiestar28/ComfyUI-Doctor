# Configuration and Security

This document summarizes public configuration and security behavior for ComfyUI-Doctor.

## LLM Credentials

Doctor resolves LLM credentials in this order:

1. Credential supplied with the current request from the session-only UI field.
2. Provider-specific environment variable.
3. Generic Doctor LLM environment variable.
4. Optional server-side credential store.

For shared, production-like, or compliance-sensitive environments, environment variables are the recommended default. The browser Settings field is session-only and cleared on reload.

## Provider Environment Variables

Common provider-specific variables:

- `DOCTOR_OPENAI_API_KEY`
- `DOCTOR_ANTHROPIC_API_KEY`
- `DOCTOR_DEEPSEEK_API_KEY`
- `DOCTOR_GROQ_API_KEY`
- `DOCTOR_GEMINI_API_KEY`
- `DOCTOR_XAI_API_KEY`
- `DOCTOR_OPENROUTER_API_KEY`
- `DOCTOR_LLM_API_KEY`

Local endpoint overrides:

- `OLLAMA_BASE_URL`
- `LMSTUDIO_BASE_URL`

Provider handling is centralized for OpenAI-compatible APIs, Anthropic, and Ollama. The backend adapter layer normalizes chat/analysis payloads, model-list parsing, non-stream responses, and streaming chunks while route handlers keep the security controls described below.

## Admin Guard

Write-sensitive endpoints are admin-gated.

Admin modes:

- Desktop loopback convenience mode: if no admin token is configured, local loopback requests are allowed for single-user desktop convenience.
- Token mode: set `DOCTOR_ADMIN_TOKEN` and pass it through an accepted admin-token channel.
- Shared-server strict mode: set `DOCTOR_REQUIRE_ADMIN_TOKEN=1` together with `DOCTOR_ADMIN_TOKEN` to fail closed when token auth is missing.
- Remote opt-in without token is only available when explicitly enabled and strict mode is not enabled.

Use strict token mode for any shared server, remote ComfyUI instance, tunnel, LAN exposure, or container exposed outside the local machine.

## Server-Side Credential Store

The Advanced Key Store is optional. It is intended for trusted/admin-controlled environments that need server-side persistence.

Runtime controls:

- `DOCTOR_SECRET_STORE_ENCRYPTION_KEY`: enables encryption-at-rest for the server store.
- `DOCTOR_SECRET_STORE_ENCRYPTION_REQUIRED`: fails closed when encryption is required but key material is missing.
- `DOCTOR_SECRET_STORE_WARN_INSECURE`: controls plaintext-mode warning logs.
- `DOCTOR_SECRET_STORE_WINDOWS_ACL_HARDEN`: controls best-effort Windows ACL hardening.

The current zero-dependency encrypted format derives encryption and MAC keys with PBKDF2-HMAC-SHA256, encrypts with an HMAC-SHA256-derived XOR stream, and authenticates `nonce + ciphertext` with HMAC-SHA256 before decrypting.

## Runtime State Location

Doctor stores runtime state under ComfyUI's private system-user directory when
the host provides that API. This keeps Doctor's generated state aligned with
current ComfyUI and Desktop user-data boundaries.

Older `user/ComfyUI-Doctor` layouts remain supported through fallback and best-effort migration. The health endpoint exposes path diagnostics so users can confirm which host directory is active without exposing secret values.
Runtime identity is independent from storage selection. A managed Desktop
`.venv` can therefore report Desktop identity while
`storage_source=folder_paths.get_system_user_directory` keeps state in the
private host directory. Explicit portable or repository-local `.venv` layouts
remain non-Desktop.

## Outbound Safety

Doctor applies outbound safety checks before sending provider-bound data:

- Privacy sanitization for cloud LLM requests.
- Unconditional case-insensitive redaction of `Authorization` and `X-API-Key`
  values in text, mappings, lists, request/response headers, outbound payloads,
  and recent log-buffer reads. This boundary remains active in privacy mode
  `none`.
- SSRF-oriented URL validation.
- Redirect restrictions for sensitive outbound checks.
- DNS/private-target checks for hostname-based private or metadata targets.
- Redacted audit records for external enrichment submit actions.

LLM prompt context is assembled through the analysis pipeline after sanitization. The provider adapter layer should receive already-sanitized payloads from route handlers.

See [Outbound Safety](OUTBOUND_SAFETY.md) for the static checker and contribution rules around outbound request paths.

## Supply-Chain Validation

The repository includes a static supply-chain scanner for dependency manifests, lockfiles, GitHub Actions workflows, and known high-risk package or payload indicators. The full local validation scripts run this scanner before dependency installation.

```bash
npm run supply-chain:check
```

The scanner is a local validation aid; it does not replace normal dependency review, package-manager audit output, or workstation incident response if an external advisory reports a compromised dependency.

## Quarterly Security Audit

Maintainers can run the recurring audit template generator and scheduled security-audit workflow for quarterly review:

```bash
python scripts/security_audit.py --date 2026-05-31 --quarter Q2
```

See [Security Audit](SECURITY_AUDIT.md) for manual SSRF, XSS, path traversal, admin-bypass, credential-exposure, telemetry, and optional Semgrep/Snyk/ZAP review guidance.

## External Enrichment and Resumable Jobs

Optional external enrichment uses a fail-closed provider policy model:

- Read/query actions are allowed only for safe enrichment paths.
- Submit/upload actions are blocked by default and require explicit provider capability and policy enablement.
- Submit/upload actions require confirmation.
- Long-running work uses checkpointed job state with status, resume, and cancel APIs.
- Audit records are redacted and avoid raw payload content.

## Telemetry

Telemetry is local-only and opt-in. It can be toggled, viewed, cleared, and exported from the Doctor Statistics tab. It is not enabled by default.

This Doctor-local telemetry is separate from ComfyUI frontend setting-change
telemetry. Every Doctor-owned frontend setting registers
`telemetry: { trackChanges: false }`, so setting values are not submitted to
the host setting-change telemetry registry.

## CSP Compatibility

Doctor frontend assets are served locally from the extension directory. External CDN use is not required for normal operation.

For restricted environments:

- Keep ComfyUI and Doctor assets served from local extension paths.
- Use local LLM providers when outbound internet access is unavailable.
- Keep cloud-provider credentials in environment variables rather than browser settings or checked-in files.
