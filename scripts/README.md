# Development Scripts

This directory contains development and maintenance scripts for ComfyUI-Doctor.

## Full Test Automation

### run_full_tests_windows.ps1

Runs the required end-to-end validation sequence in one command on Windows:

1. `detect-secrets`
2. all `pre-commit` hooks
3. host-like package/startup validation
4. backend unit tests
5. frontend E2E

The script always uses the project-local `.venv` interpreter for Python tooling and tests (Windows track).

**Usage**:
```powershell
powershell -File scripts/run_full_tests_windows.ps1

# Optional: skip dependency bootstrap
powershell -File scripts/run_full_tests_windows.ps1 -SkipBootstrap

# Optional: skip E2E stage
powershell -File scripts/run_full_tests_windows.ps1 -SkipE2E
```

### run_full_tests_linux.sh

Linux/WSL equivalent of the full-test automation flow with OS-aware venv selection:

- WSL: `.venv-wsl`
- native Linux: `.venv`

**Usage**:
```bash
bash scripts/run_full_tests_linux.sh

# Optional: skip dependency bootstrap
bash scripts/run_full_tests_linux.sh --skip-bootstrap

# Optional: skip E2E stage
bash scripts/run_full_tests_linux.sh --skip-e2e
```

### pre_push_checks.sh

Repository-managed pre-push gate entrypoint. It runs the same mandatory full test flow and exits non-zero on any failure, which blocks `git push` when hook is enabled.

**Usage**:
```bash
bash scripts/pre_push_checks.sh
```

Enable the hook once:
```bash
git config core.hooksPath .githooks
```

---

## Focused Release Gate

### phase2_gate.py

Runs the focused security, contract, and E2E regression gate locally. This is a targeted lane, not a replacement for the full local gate above.

**Usage**:
```bash
# Full gate (Python + E2E tests)
python scripts/phase2_gate.py

# Fast mode (Python tests only, < 2 minutes)
python scripts/phase2_gate.py --fast

# E2E tests only
python scripts/phase2_gate.py --e2e
```

**What it checks**:
- Plugin security (allowlist, trust states, DoS limits)
- Metadata contract (schema validation)
- Dependency policy (requires/provides)
- Outbound payload safety (sanitization)
- E2E regression (UI stability)

**Exit codes**:
- `0` = All passed
- `1` = Python tests failed
- `2` = E2E tests failed
- `3` = Both failed

### phase2_gate.sh

Bash alternative to `phase2_gate.py` for Unix environments.

**Usage**:
```bash
# Full gate
./scripts/phase2_gate.sh

# Fast mode (Python only)
./scripts/phase2_gate.sh --fast

# E2E only
./scripts/phase2_gate.sh --e2e
```

---

## Outbound Safety Checker

### check_outbound_safety.py

Static analysis tool to prevent bypass of outbound sanitization funnel.

**Usage**:
```bash
# Run all checks
python scripts/check_outbound_safety.py
```

**What it detects**:
- Raw context fields in outbound payloads
- Missing `sanitize_outbound_payload()` calls
- Dangerous fallback patterns (`sanitized_X or X`)
- `json.dumps()` on sensitive data

**Exit codes**:
- `0` = All checks passed
- `1` = Violations detected
- `2` = Script error

---

## Plugin Migration Tooling

### plugin_manifest.py

Generates plugin manifest JSON files with computed SHA256 hashes.

**Usage**:
```bash
# Dry-run (print to stdout, no writes)
python scripts/plugin_manifest.py pipeline/plugins/community/example.py

# Write manifest
python scripts/plugin_manifest.py pipeline/plugins/community/example.py --write

# Batch process
python scripts/plugin_manifest.py pipeline/plugins/community/*.py --write
```

### plugin_allowlist.py

Scans plugins and generates allowlist config snippet.

**Usage**:
```bash
# Scan and suggest allowlist
python scripts/plugin_allowlist.py

# Include trust report
python scripts/plugin_allowlist.py --report
```

### plugin_validator.py

Validates plugin manifests and configuration.

**Usage**:
```bash
# Validate all plugins
python scripts/plugin_validator.py

# Validate specific plugin
python scripts/plugin_validator.py community.example

# Check allowlist consistency
python scripts/plugin_validator.py --check-config
```

### plugin_hmac_sign.py (Optional)

Generates HMAC-SHA256 signatures for plugins.

**Usage**:
```bash
# Interactive mode
python scripts/plugin_hmac_sign.py pipeline/plugins/community/example.py

# Environment variable mode
DOCTOR_PLUGIN_HMAC_KEY="secret" python scripts/plugin_hmac_sign.py example.py
```

---

## Other Scripts

### run-playwright.mjs

Wrapper for running Playwright E2E tests with proper environment setup.

**Usage**:
```bash
npm test  # Calls this script automatically
```

### preflight-js.mjs

Pre-flight checks for JavaScript/E2E tests.

---

## CI Integration

These scripts mirror the GitHub Actions workflows:

- `phase2_gate.py` ↔ `.github/workflows/phase2-release-gate.yml`
- `check_outbound_safety.py` ↔ `.github/workflows/outbound-safety.yml`

Run scripts locally before pushing to catch issues early.
