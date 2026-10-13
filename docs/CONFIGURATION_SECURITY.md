# Configuration and Security

This document summarizes public configuration and security behavior for ComfyUI-Doctor.

## LLM Credentials

Doctor resolves LLM credentials in this order:

1. Credential supplied with the current request from the session-only UI field.
2. Provider-specific environment variable.
3. Generic Doctor LLM environment variable.
4. Optional server-side credential store.

For shared, production-like, or compliance-sensitive environments, environment variables are the recommended default. The browser Settings field is session-only and cleared on reload.

Credentials held by the server (environment variables and the server-side credential store) are
only sent to the destination they are bound to. The binding is decided from the approved
destination (see [LLM Destinations](#llm-destinations)); the provider selected in the request
cannot change it.

| Destination | Server-held credential used |
| --- | --- |
| Official provider (for example `https://api.openai.com/v1`) | That provider's key, then the generic key |
| The URL set in `DOCTOR_LLM_BASE_URL` (custom endpoint) | Generic key only (`DOCTOR_LLM_API_KEY` or the store's generic entry) |
| URLs listed only in `DOCTOR_LLM_ALLOWED_BASE_URLS` | None — enter a key in Settings |
| Local Ollama / LM Studio and `OLLAMA_BASE_URL` / `LMSTUDIO_BASE_URL` | None (keyless) |

A key entered in Settings is sent to whichever approved destination is selected. If no credential
is available, the request fails with `missing_api_key` and nothing is sent.

Migrating a custom endpoint that used the server's generic key: set it as `DOCTOR_LLM_BASE_URL`
(this also approves it as a destination) or enter a key in Settings.

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

## LLM Destinations

The server only sends LLM requests (analysis, chat, key verification and model listing) to
destinations approved on the machine that runs ComfyUI. The Base URL in Doctor settings, the
provider quick switch and API request bodies can only select one of these destinations; they cannot
add a new one or change its host, port, path, query or scheme.

Approved without configuration:

- Official providers: `https://api.openai.com/v1`, `https://api.anthropic.com`,
  `https://api.deepseek.com/v1`, `https://api.groq.com/openai/v1`,
  `https://generativelanguage.googleapis.com/v1beta/openai`, `https://api.x.ai/v1`,
  `https://openrouter.ai/api/v1`. `https://api.openai.com` and `https://api.deepseek.com` are
  accepted as the same destinations as their `/v1` forms, and `https://api.anthropic.com/v1` as
  `https://api.anthropic.com`.
- Local services on this machine: Ollama at `http://127.0.0.1:11434`, `http://localhost:11434`
  or `http://[::1]:11434`, and LM Studio at the same hosts on port `1234` (`/v1`).

Approved by the server operator through environment variables read at startup:

- `OLLAMA_BASE_URL`, `LMSTUDIO_BASE_URL` and `DOCTOR_LLM_BASE_URL` (each value is approved
  exactly as written).
- `DOCTOR_LLM_ALLOWED_BASE_URLS`: a comma-separated list of exact base URLs, for example
  `https://llm-gateway.example.com/v1,http://192.168.1.20:11434`.

Matching rules:

- A request must use one approved base URL exactly. Letter case, a trailing slash, a trailing dot
  on the host and an explicit default port are normalized; everything else must match.
- Base URLs with user information, a query, a fragment, a backslash, whitespace, percent-encoding,
  `.`/`..` path segments or a non-HTTP(S) scheme are never approved.
- Values that cannot be parsed, metadata or link-local addresses, and extra paths on official
  provider hosts are ignored at startup with a log warning.
- A request for any other destination is refused with the error code `destination_not_allowed`
  before any DNS lookup or network connection. The Doctor settings panel shows this as
  operator guidance.

Connection checks:

- Addresses are checked when the connection is made, on the exact addresses that will be used.
- Official providers must resolve only to public internet addresses.
- Built-in local services, and approved entries whose host is `localhost` or a loopback address,
  must resolve only to loopback addresses.
- Other operator-approved hosts (for example a LAN address, a Docker service name such as
  `my_ollama`, or `host.docker.internal`) may resolve to private or public addresses, but never to
  loopback, link-local, cloud metadata, unspecified or multicast addresses. IPv6 forms that embed
  one of these IPv4 addresses (NAT64, 6to4, IPv4-compatible or IPv4-mapped) are refused as well.
- Redirects are never followed, and any `3xx` answer is treated as a failure.
- Error responses use fixed messages: provider error bodies, resolved addresses and network error
  details are written to the server log only.

When `DOCTOR_OUTBOUND_PROXY_POLICY=inherit_env` is set, requests that go through the proxy rely on
the proxy for address checks; approved hosts reached directly (for example through `NO_PROXY`)
are still checked. The proxy itself, including a proxy on this machine such as
`http://localhost:7890`, is connected to as configured. Local loopback destinations never use a
proxy.

The approved list is fixed when ComfyUI loads Doctor; restart ComfyUI after changing these
environment variables.

Migrating a custom endpoint: if a custom Base URL (self-hosted gateway, Azure OpenAI, remote
Ollama or LM Studio, or a Docker host address) stops working with `destination_not_allowed`, add
the exact URL to `DOCTOR_LLM_ALLOWED_BASE_URLS` (or to `OLLAMA_BASE_URL`/`LMSTUDIO_BASE_URL`) in
the environment that starts ComfyUI, restart ComfyUI, and use the same URL in Doctor settings.

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

An encrypted store is locked when it cannot be opened with the configured key:

- `locked_key_required`: the store is encrypted but `DOCTOR_SECRET_STORE_ENCRYPTION_KEY` is not set.
- `locked_key_mismatch`: the configured key does not authenticate the store (for example, the key was changed).

While locked, the store file is never rewritten, downgraded to plaintext, or moved aside. Stored credentials read as not configured, `GET /doctor/secrets/status` reports the state in `store.state`, and `PUT /doctor/secrets` and `DELETE /doctor/secrets/{provider}` return HTTP 409 with error code `secret_store_locked`. The server logs the locked state once per change, without key material or credential values.

To recover, restore the original `DOCTOR_SECRET_STORE_ENCRYPTION_KEY` and restart ComfyUI. To deliberately start over instead, move the store file aside and save the credentials again. A store file that is structurally unreadable (not valid JSON or invalid encoding) is still moved aside as `<name>.corrupt-<timestamp>` so a new store can be created.

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
- Operator-approved LLM destinations with connect-time address checks (see
  [LLM Destinations](#llm-destinations)).
- Redirects are never followed on outbound requests.
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

The chat markdown and code-highlighting libraries load only from the extension's own `web/lib/` directory, whatever the custom-node folder is named; there is no CDN fallback for them. If those files are missing, chat replies are shown as plain text.

For restricted environments:

- Keep ComfyUI and Doctor assets served from local extension paths.
- Use local LLM providers when outbound internet access is unavailable.
- Keep cloud-provider credentials in environment variables rather than browser settings or checked-in files.
