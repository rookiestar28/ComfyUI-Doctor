# Security Audit

This document defines the recurring security-audit workflow for ComfyUI-Doctor maintainers and contributors.

## Cadence

Run a security audit once per calendar quarter and after any high-impact security change. The scheduled GitHub Actions workflow runs on the first day of January, April, July, and October, and can also be started manually.

Use `scripts/security_audit.py` to create a sanitized report template:

```powershell
python scripts/security_audit.py --date 2026-05-31 --quarter Q2
```

The generated template is safe to use as a starting point, but raw scanner output, target-specific details, private URLs, local state contents, and sensitive evidence must stay in maintainer-private storage.

## Automated Checks

The quarterly workflow runs these repository-local checks:

- `python scripts/check_supply_chain.py --skip-install-trees`
- `python scripts/check_outbound_safety.py`
- `python scripts/focused_gate.py --fast`
- `python scripts/security_audit.py --output security-audit-template.md`

The workflow also supports optional external scanner lanes:

- Semgrep SAST with tokenless `semgrep scan` when install/network access is available.
- Snyk dependency scanning when `SNYK_TOKEN` is configured and the manual `run_snyk` input is enabled.
- OWASP ZAP baseline scanning when a manual `zap_target_url` input is provided for a target the maintainer is authorized to test.

Optional external scanners supplement local gates. They do not replace `tests/TEST_SOP.md` validation before accepting code changes.

## Manual Checks

Each quarterly audit should include public-safe summaries for these scenarios:

- SSRF attempts against metadata endpoints and private/internal IP ranges.
- Redirect-based SSRF bypass attempts.
- XSS attempts through chat inputs, rendered model responses, settings fields, and diagnostic text.
- Path traversal attempts through any path-like input or report/history access path.
- Model-asset traversal, absolute external path, cross-drive, null-byte, and
  symlink-escape attempts; verify no rejected candidate is opened or returned
  as evidence.
- Admin bypass attempts against write-sensitive endpoints.
- Credential exposure checks for status APIs, server-side key metadata, logs, and browser state.
- Case-insensitive `Authorization` and `X-API-Key` redaction across text,
  structured payloads, outbound data, and recent logs, including privacy mode
  `none`.
- Telemetry privacy review for opt-in state, export, clear, and local-only behavior.
- Host setting-change telemetry review confirming every Doctor-owned frontend
  setting opts out and no credential setting is registered.
- Plugin trust scanning review without importing third-party plugin code.

Active or passive DAST must only run against targets you own or are explicitly authorized to test.

## Compliance Mapping

Map findings and test coverage to:

- OWASP Top 10: injection, broken access control, SSRF, security logging, vulnerable components, and misconfiguration.
- CWE Top 25: input validation, path traversal, XSS, credential handling, unsafe command execution, and improper authorization.
- Privacy/GDPR readiness: data minimization, local-only telemetry, credential handling, deletion/export expectations, and safe evidence handling.

## Report Handling

Audit reports must be sanitized before sharing:

- Do not include secrets, tokens, cookies, private URLs, private hostnames, private logs, local state contents, workstation-specific paths, screenshots containing sensitive data, or raw scanner dumps.
- Use public file paths, rule IDs, severity, concise impact, remediation, and validation status.
- Keep raw evidence and target-specific scanner output in maintainer-private storage.
- If a finding leads to a code change, add targeted regression coverage and run the full acceptance gate from `tests/TEST_SOP.md`.

## References

- OWASP ZAP baseline scan: <https://www.zaproxy.org/docs/docker/baseline-scan/>
- OWASP ZAP Automation Framework: <https://www.zaproxy.org/docs/automate/automation-framework/>
- Semgrep CLI reference: <https://semgrep.dev/docs/cli-reference>
- Snyk GitHub Actions: <https://docs.snyk.io/developer-tools/snyk-ci-cd-integrations/github-actions-for-snyk-setup-and-checking-for-vulnerabilities>
