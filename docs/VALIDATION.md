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

1. `pre-commit run detect-secrets --all-files`
2. `pre-commit run --all-files --show-diff-on-failure`
3. Host-like package/startup validation.
4. Backend unit tests.
5. Frontend Playwright E2E tests.

## Explicit Staged Commands

Use this flow when debugging one validation stage at a time.

```bash
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

After refreshing local ComfyUI, ComfyUI frontend, or Desktop checkouts under `reference/`, run:

```bash
python scripts/check_host_compatibility.py
```

This lane checks the host API surfaces Doctor currently depends on.

## Coverage Baseline Lane

Coverage is currently an informational baseline, not a default acceptance threshold:

```bash
python scripts/run_coverage_baseline.py --xml coverage.xml
```

Use this lane to track test coverage movement without changing the default full gate.

## Frontend E2E Requirements

Frontend E2E requires Node.js 18 or newer.

```bash
node -v
npm install
npx playwright install chromium
npm test
```

When running under WSL from a mounted Windows path, use a writable temp directory and a `python` shim if only `python3` is available. The full Linux script handles these common cases.
