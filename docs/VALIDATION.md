# Validation Guide

This guide keeps validation details out of the main README.

## Full Local Gate

Use the one-command script for your operating system when possible.

Windows PowerShell:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux or WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

The full gate runs:

1. Supply-chain dependency and workflow risk checks.
2. `pre-commit run detect-secrets --all-files`
3. `pre-commit run --all-files --show-diff-on-failure`
4. Host-like package/startup validation.
5. Backend unit tests.
6. Frontend Playwright E2E tests.

Backend collection keeps the canonical production `__init__.py` in place. The
host-like stage separately validates ComfyUI-shaped package loading; test
tooling must not rename, remove, or substitute a backup package entry point.

## Explicit Staged Commands

Use this flow when debugging one validation stage at a time.

```bash
python scripts/check_supply_chain.py --skip-install-trees
pre-commit run detect-secrets --all-files
pre-commit run --all-files --show-diff-on-failure
python scripts/validate_host_load.py
DOCTOR_STATE_DIR="$(pwd)/doctor_state/_local_unit" python scripts/run_unittests.py --start-dir tests --pattern "test_*.py"
node -v
npm install
npx playwright install chromium
npm test
```

Windows users can run the equivalent commands from PowerShell with the project `.venv` active.

## Host Compatibility Lane

After refreshing local ComfyUI, ComfyUI frontend, or Desktop host checkouts used for development compatibility review, run:

```bash
python scripts/check_host_compatibility.py
```

This lane checks the host API surfaces Doctor currently depends on.
Checks are version-aware and report separate applicability lanes for the
ComfyUI Desktop bundled frontend, ComfyUI's pinned frontend package, and the
standalone frontend source. Current contracts cover prompt queue source
metadata, frontend queue source attribution, execution event payload shape,
output asset enrichment tolerance, host package/version anchors, the live
model registry and extensions, nested/promoted subgraph serialization,
positional/named widget restore policy, first-party promoted media ownership,
the current PyTorch minimum, frontend raw/surfaced validation errors,
setting-change telemetry controls, real subgraph shape, system statistics
metadata, Desktop layout, ComfyUI job-cancel routes, and frontend queue/cancel
adoption.

The compatibility script reads source files only. It does not import, install,
build, or execute code from the host reference repositories.

## Supply-Chain Check

The supply-chain scanner is static and does not execute dependency lifecycle scripts. It checks repository manifests, lockfiles, workflow configuration, known high-risk dependency indicators, and install-tree indicators when enabled.

```bash
npm run supply-chain:check
```

The full-test scripts run this check before dependency installation so obvious dependency or workflow risk drift is caught early.

## Focused Security / Contract Lane

The focused gate is a supplemental lane for security and contract regressions. It does not replace the full local gate.

```bash
python scripts/focused_gate.py --fast
```

Run the full focused lane, including E2E, when changing frontend behavior in the same work:

```bash
python scripts/focused_gate.py
```

The old `scripts/phase2_gate.py` and `scripts/phase2_gate.sh` entrypoints remain compatibility wrappers only. New docs and automation should use the focused-gate names.

## E2E Integration and Stress Lanes

The default `npm test` run excludes `@integration` and `@stress` specs. Use the opt-in lanes when validating telemetry endpoint behavior beyond the default UI harness.

```bash
npm run test:integration
npm run test:stress
```

`npm run test:integration` uses the Playwright harness backend by default. Set `COMFYUI_URL` only when you intentionally want to run the same telemetry assertions against a live ComfyUI backend.

`npm run test:stress` uses the harness backend and exercises telemetry burst/state behavior.

## Coverage Baseline Lane

Coverage is currently an informational baseline, not a default acceptance threshold:

```bash
python scripts/run_coverage_baseline.py --xml coverage.xml
```

Use this lane to track test coverage movement without changing the default full gate.

## Quarterly Security Audit Lane

Use the security audit generator and scheduled workflow for recurring review. Generated templates are public-safe starting points; private target details and raw scanner output should stay in maintainer-private storage.

```bash
python scripts/security_audit.py --date 2026-05-31 --quarter Q2
```

See [Security Audit](SECURITY_AUDIT.md) for the quarterly cadence, manual SSRF/XSS/path traversal checks, optional Semgrep/Snyk/ZAP lanes, and report-handling rules.

## Frontend E2E Requirements

Frontend E2E requires Node.js `>=18 <26`.

```bash
node -v
npm install
npx playwright install chromium
npm test
```

Node 26+ is blocked until Doctor's Playwright harness and package metadata are explicitly validated against that runtime.

When running under WSL from a mounted Windows path, use a writable temp directory and a `python` shim if only `python3` is available. The full Linux script handles these common cases.
