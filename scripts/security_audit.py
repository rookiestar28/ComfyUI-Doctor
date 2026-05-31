#!/usr/bin/env python3
"""Generate a sanitized quarterly security audit report template."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path


VALID_QUARTERS = {"Q1", "Q2", "Q3", "Q4"}


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc


def _quarter_for(month: int) -> str:
    if month <= 3:
        return "Q1"
    if month <= 6:
        return "Q2"
    if month <= 9:
        return "Q3"
    return "Q4"


def build_report(*, audit_date: date, quarter: str | None = None) -> str:
    """Build a deterministic markdown report template."""
    selected_quarter = (quarter or _quarter_for(audit_date.month)).upper()
    if selected_quarter not in VALID_QUARTERS:
        msg = f"quarter must be one of {', '.join(sorted(VALID_QUARTERS))}"
        raise ValueError(msg)

    title = f"{audit_date:%Y} {selected_quarter} Security Audit"
    return f"""# {title}

Date: {audit_date.isoformat()}
Scope: ComfyUI-Doctor repository, ComfyUI custom-node runtime boundaries, local validation tooling, and public documentation.

## Audit Rules

- Do not include secrets, tokens, cookies, private URLs, private hostnames, user data, local state contents, generated reports with sensitive paths, or workstation-specific details.
- Record only sanitized command summaries, pass/fail status, affected public file paths, and public-safe remediation notes.
- Keep raw scanner output and target-specific evidence in maintainer-private storage.
- Run active or passive DAST only against targets you own or are explicitly authorized to test.

## Automated Checks

| Check | Command or Source | Status | Notes |
| --- | --- | --- | --- |
| Supply-chain scanner | `python scripts/check_supply_chain.py --skip-install-trees` | Pending | Required repo-local gate |
| Outbound safety | `python scripts/check_outbound_safety.py` | Pending | Required repo-local gate |
| Focused security gate | `python scripts/focused_gate.py --fast` | Pending | Plugin, metadata, dependency-policy, outbound-payload checks |
| Full local acceptance gate | `scripts/run_full_tests_windows.ps1` or `scripts/run_full_tests_linux.sh` | Pending | Required before accepting remediation changes |
| Semgrep SAST | `semgrep scan` in scheduled workflow | Pending | Optional when Semgrep install/network is available |
| Snyk dependency scan | `snyk test` in scheduled workflow | Pending | Optional when `SNYK_TOKEN` is configured |
| ZAP baseline scan | `zap-baseline.py` in scheduled workflow | Pending | Optional; requires authorized target URL |

## Manual Security Scenarios

| Scenario | Coverage Target | Status | Sanitized Result |
| --- | --- | --- | --- |
| SSRF metadata endpoint attempts | Provider base URL validation and redirect handling | Pending |  |
| SSRF private/internal IP attempts | DNS resolution and private-target blocking | Pending |  |
| XSS chat input attempts | Chat rendering and message sanitization | Pending |  |
| XSS settings field attempts | Settings rendering and saved field handling | Pending |  |
| Path traversal attempts | File/path inputs, report/history access, plugin trust scanning | Pending |  |
| Admin bypass attempts | Write-sensitive endpoints and strict-token mode | Pending |  |
| Credential exposure attempts | Server-side key store, status APIs, logs, and UI state | Pending |  |
| Telemetry privacy review | Local-only opt-in buffer, export, clear, and toggle behavior | Pending |  |

## Compliance Mapping

| Framework | Review Focus | Status | Notes |
| --- | --- | --- | --- |
| OWASP Top 10 | Injection, broken access control, SSRF, security logging, vulnerable components | Pending |  |
| CWE Top 25 | Input validation, path traversal, XSS, credential handling, command execution | Pending |  |
| Privacy/GDPR readiness | Data minimization, local telemetry, credential handling, deletion/export expectations | Pending |  |

## Findings

| ID | Severity | Area | Public-Safe Summary | Remediation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## Remediation Validation

| Finding ID | Targeted Regression | Full Gate Result | Status |
| --- | --- | --- | --- |
|  |  |  |  |

## Sign-Off

- Auditor:
- Reviewer:
- Follow-up due date:
- Public release note needed: Yes / No
"""


def _write_output(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a sanitized quarterly security audit report template."
    )
    parser.add_argument("--date", type=_parse_date, default=None, help="Audit date in YYYY-MM-DD.")
    parser.add_argument("--quarter", choices=sorted(VALID_QUARTERS), help="Audit quarter.")
    parser.add_argument("--output", help="Write report to this path instead of stdout.")
    parser.add_argument("--force", action="store_true", help="Overwrite --output if it exists.")
    args = parser.parse_args(argv)

    audit_date = args.date or date.today()
    try:
        report = build_report(audit_date=audit_date, quarter=args.quarter)
    except ValueError as exc:
        parser.error(str(exc))

    if args.output:
        try:
            _write_output(Path(args.output), report, force=args.force)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
