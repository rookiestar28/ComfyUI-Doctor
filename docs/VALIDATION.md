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

## Supply-Chain Check

The supply-chain scanner is static and does not execute dependency lifecycle scripts. It checks repository manifests, lockfiles, workflow configuration, known high-risk dependency indicators, and install-tree indicators when enabled.

```bash
npm run supply-chain:check
```

The full-test scripts run this check before dependency installation so obvious dependency or workflow risk drift is caught early.

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
