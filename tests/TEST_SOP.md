# Test SOP

### Problem-First Test Design Rule (Mandatory)

All test scripts, test harnesses, and validation flows must be designed first to reproduce real failures and catch bugs early.

The purpose of testing is to expose defects, regressions, drift, and broken assumptions before users hit them. Tests must not be designed merely to produce a green validation result, satisfy a checklist, or prove that a happy path still passes. Do not waste validation time on pass-only checks that cannot fail for the bug class under review.

Every bugfix or high-risk change must start from the question: "Which test would have caught this before release?" If the existing gate missed the bug, update the targeted test or SOP flow so the same class of bug fails deterministically next time.
This document defines the **mandatory test workflow** for this repo. Run it **before every push** (unless you explicitly document why you’re skipping).

## Acceptance Rule (SOP)

Every implementation plan must include the **full test validation procedure** in its final stage. A plan is **not accepted** until all tests in this SOP pass **without errors** and the results are recorded (date + environment + command log reference).

## Prerequisites

- Python 3.10+ (CI uses 3.10/3.11)
- Node.js 18+ (CI uses 20)
- `pre-commit` installed: `python -m pip install pre-commit`
- Backend test deps available in the same interpreter (`numpy`, `pillow`, `aiohttp`)
- Frontend deps installed: `npm install`

## Environment Sanity (Required Guardrails)

- **Python interpreter must be consistent** for all test commands.
  - Verify: `python -c "import sys; print(sys.executable)"`
  - If you use conda or venv, ensure the same interpreter runs unit tests and connector tests.
- **Project venv recommended**: use an OS-specific local venv to avoid mixed dependencies.
  - Linux/WSL recommended path: `.venv-wsl` (especially when Windows also uses `.venv` in the same repo)
  - Other environments: `.venv`
  - Create: `python -m venv .venv-wsl` (WSL) or `python -m venv .venv`
  - Activate (bash): `source .venv-wsl/bin/activate` (or `.venv/bin/activate`)
  - Activate (pwsh): `.\.venv\Scripts\Activate.ps1`
  - If tests fail due to missing deps in CI parity, rerun in the project venv used by scripts and record that in the implementation record.
- **Node version must be 18+** before E2E:
  - Verify: `node -v`
  - If mismatch in WSL, use the Node 18 path specified below.

## Environment Parity Guardrails (CI Safety)

To avoid local vs CI mismatches:

- **Do not hard-import optional deps in tests** (e.g. `aiohttp`) unless the test explicitly installs them.
- If a test needs a module that may be missing in CI, **use a stub** (e.g. `sys.modules["services.foo"]=stub`) or patch the **module-level import location** used by the code under test.
- If a test truly requires an optional dependency, mark it with a **clear skip** when the dep is unavailable.
- Record the environment in the implementation record (OS, Python, Node, and any extras installed) so mismatches are visible.

## Offline / Restricted Network Pre-commit (Fail Fast)

If your environment cannot reach GitHub, `pre-commit` may hang while installing hook repos.
Use **one** of the following, and record it in the implementation record:

1) **Preferred**: run once with network to populate the cache
   - `pre-commit install --install-hooks`
   - Subsequent runs will use cache without network.
2) **Proxy**: configure `https_proxy` / `http_proxy` for GitHub access.
3) **Fail-fast guard**: if GitHub access is blocked, stop and fix connectivity or use cached hooks.
   - Do not mark pre-commit as "passed" unless the hooks complete successfully.

Do **not** switch hooks to `repo: local` unless CI is updated to match, or you will reintroduce local/CI divergence.

## Pre-commit Cache Repair (If Cache Is Corrupt)

Symptoms:
- `InvalidManifestError` or missing `.pre-commit-hooks.yaml`
- partial venv in pre-commit cache
- repeated install failures even after network is restored

Fix (choose one):

1) **Clear cache and re-install hooks (recommended)**
   - Linux/WSL:
     - `rm -rf ~/.cache/pre-commit`
     - `pre-commit install --install-hooks`
   - Windows (PowerShell):
     - `Remove-Item -Recurse -Force \"$env:USERPROFILE\\.cache\\pre-commit\"`
     - `pre-commit install --install-hooks`

2) **Set a clean cache location**
   - `set PRE_COMMIT_HOME=/path/to/new/cache`
   - `pre-commit install --install-hooks`

If GitHub is unreachable, the above will still fail; fix connectivity or configure a proxy first.

## Windows Lock-File Guardrail (Required on WinError 5)

When you see:
- `PermissionError: [WinError 5] Access is denied`
- failure deleting `...\\.cache\\pre-commit\\...\\Scripts\\*.exe`

this is usually a **locked executable**, not a logic error in hooks.

Use this exact sequence (PowerShell):

1) Stop active processes that may hold the file lock
   - `Get-Process pre-commit,python,git -ErrorAction SilentlyContinue | Stop-Process -Force`
2) Use a repo-local pre-commit cache (prevents repeated global-cache lock conflicts)
   - `$env:PRE_COMMIT_HOME = \"$PWD\\.tmp\\pre-commit-win\"`
3) Clean and rerun
   - `pre-commit clean`
   - `pre-commit run detect-secrets --all-files`
   - `pre-commit run --all-files --show-diff-on-failure`
4) If cleanup still fails, remove cache directory directly
   - `Remove-Item -Recurse -Force \"$env:PRE_COMMIT_HOME\"`
   - `New-Item -ItemType Directory -Force \"$env:PRE_COMMIT_HOME\" | Out-Null`
   - rerun step (3)

Rules:
- Do not run multiple pre-commit commands in parallel on Windows.
- Do not mark tests as passed if hooks were interrupted by lock errors.

### Windows PATH and Process Reality Checks

Use these checks before assuming the hook runner is broken:

1) `where pre-commit` can be empty in PowerShell even when module execution works.
   - Prefer:
     - `python -m pre_commit --version`
     - `Get-Command pre-commit -All`
2) If multiple Python installations exist, always run:
   - `python -m pre_commit ...`
   instead of relying on bare `pre-commit` resolution.
3) If process cleanup looks inconsistent, inspect actual command lines:
   - `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pre-commit|detect-secrets|black' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine`
4) `taskkill` may report "no running instance" when the PID already exited between scans.
   - Re-run the `Get-CimInstance` query above before deciding a process is still stuck.

## Required Pre-Push Workflow (Must Run)

### Branch-Tip Revalidation Rule (Required)

For high-risk or cross-cutting changes (for example logger, path resolution, timestamp normalization, event-contract compatibility), do not rely only on the first green run from an intermediate worktree state. Re-run the mandatory full gate on the final branch tip that you actually intend to push when any of these occur:

- merge / rebase / conflict resolution changed the validated commit chain
- detached HEAD work was later attached or merged onto a branch
- a regression fix landed after the original item was already marked complete

Minimum expectation:

```bash
git branch --show-current
git rev-parse --short HEAD
```

Record the final validated branch + HEAD in the implementation record when the item is accepted.

### Push-Scope Boundary (Important)

The full-test scripts and `scripts/pre_push_checks.sh` validate the local acceptance gate only. They do **not** guarantee remote push success. A later `git push` can still fail for reasons outside the local test scope, including:

- GitHub authentication / missing credentials
- branch protection rules
- non-fast-forward remote state
- server-side policy hooks

Treat local gate success as "safe to attempt push", not as proof that the remote accepted the push.

### Optional: One-Command Full Test Scripts (Fastest)

Use these if you want a single command that runs **all required steps** (detect-secrets, pre-commit, host-like package/startup validation, unit tests, E2E). These scripts also handle the most common environment issues (Windows cache locks, Black cache, Node 18).
Scripts enforce a project-local venv and will bootstrap missing test tooling (`pre-commit`, and `aiohttp` where needed for imports).
On WSL, scripts prefer `.venv-wsl`; on Windows they use `.venv`.
If the selected venv exists but is invalid for the current OS/interpreter, rerun via the script so it can recreate that venv.
Linux script includes an explicit offline fail-fast guard: if dependency bootstrap fails (for example `aiohttp` / `pre-commit` install), it stops with remediation hints instead of continuing with partial state.

- Linux/WSL:
  - `bash scripts/run_full_tests_linux.sh`
- Windows (PowerShell):
  - `powershell -File scripts/run_full_tests_windows.ps1`

### Optional automation (recommended)

Enable the repository-managed Git pre-push hook once:

```bash
git config core.hooksPath .githooks
```

Then every `git push` will run:

```bash
bash scripts/pre_push_checks.sh
```

`scripts/pre_push_checks.sh` is the CI-parity guard and must include all 5 stages:
1) `detect-secrets`
2) all `pre-commit` hooks
3) host-like package/startup validation (`python scripts/validate_host_load.py`)
4) backend unit tests (`scripts/run_unittests.py --pattern "test_*.py"` or pytest fallback)
5) frontend E2E (`npm test`)

IMPORTANT:
- Do not remove stage (3). If pre-push skips host-like validation, package-load regressions can slip past local pytest.
- Do not remove stage (4). If pre-push skips backend unit tests, local pushes can pass while GitHub CI fails later.
- Keep dependency bootstrap in this script aligned with `.github/workflows/ci.yml` unit-test dependencies.

1) Detect Secrets (baseline-based)

```bash
pre-commit run detect-secrets --all-files
```

1) Run all pre-commit hooks

```bash
pre-commit run --all-files --show-diff-on-failure
```

**IMPORTANT (must read): pre-commit “modified files” is a failure until committed**

- Some hooks (e.g. `end-of-file-fixer`, `trailing-whitespace`) intentionally **exit non-zero** when they auto-fix files.
- CI will fail if those fixes are not committed.
- Rule: keep re-running step (2) until it reports **no modified files**, and `git status --porcelain` is empty.

Typical loop:

```bash
pre-commit run --all-files --show-diff-on-failure
git status --porcelain
git diff
git add -A
git commit -m "Apply pre-commit autofixes"
pre-commit run --all-files --show-diff-on-failure
```

1) Host-like package/startup validation

```bash
python scripts/validate_host_load.py
```

This stage exists because repo-root pytest imports can hide real ComfyUI custom-node package-load and prestartup encoding failures. Treat a failure here as a release-blocking regression in import/bootstrap behavior, not as an optional extra check.

1) Backend unit tests (recommended; CI enforces)

```bash
DOCTOR_STATE_DIR="$(pwd)/doctor_state/_local_unit" python scripts/run_unittests.py --start-dir tests --pattern "test_*.py"
```

1) Frontend E2E (Playwright; CI enforces)

```bash
# Ensure you are using Node.js 18+ (CI uses 20).
node -v

# If you're on WSL and `node -v` is < 18, your shell may be picking up the distro Node
# (e.g. `/usr/bin/node`) instead of your user-installed Node. If you use `nvm`, do:
#   source ~/.nvm/nvm.sh
#   nvm use 18.20.8
# Then re-check:
#   node -v
#
# IMPORTANT: run `npm install` with the same Node version you use for `npm test`.

# One-time browser install (recommended)
npx playwright install chromium

npm test
```

For OS-specific E2E setup (Windows/WSL temp-dir shims), see `tests/E2E_TESTING_SOP.md`.

## Doctor Admin and LLM Manual Checks

These checks are optional manual smoke tests for local ComfyUI sessions. They are
not a replacement for the required automated gate above.

### Admin token mode

Doctor write-sensitive endpoints use `DOCTOR_ADMIN_TOKEN` and
`DOCTOR_REQUIRE_ADMIN_TOKEN`.

PowerShell example:

```powershell
$env:DOCTOR_ADMIN_TOKEN="your_admin_token_here"
$env:DOCTOR_REQUIRE_ADMIN_TOKEN="1"
```

CMD example:

```cmd
set DOCTOR_ADMIN_TOKEN=your_admin_token_here
set DOCTOR_REQUIRE_ADMIN_TOKEN=1
```

After changing server-side environment variables, restart ComfyUI. The Settings
UI can send an admin token with guarded requests, but it cannot set the server's
admin token.

### LLM credential mode

Cloud providers require credentials from the session-only UI field, provider
environment variables, the generic `DOCTOR_LLM_API_KEY`, or the optional
server-side credential store.

Examples:

```powershell
$env:DOCTOR_OPENAI_API_KEY="<set-in-local-shell>"
$env:DOCTOR_LLM_BASE_URL="https://api.openai.com/v1"
```

```cmd
set DOCTOR_GEMINI_API_KEY=<set-in-local-shell>
set DOCTOR_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
```

Manual verification path:

1. Start ComfyUI with Doctor installed.
2. Open the Doctor sidebar Settings tab.
3. Select provider, base URL, privacy mode, and model.
4. Use key verification or model listing when available.
5. Trigger a known local error and verify Chat can stream or return a response.

Security notes:

- Do not expose ComfyUI to the internet with only browser-held tokens.
- Keep server tokens and cloud credentials in environment variables or the
  admin-gated server store.
- Use `Privacy Mode: Basic` or `Strict` for cloud providers.

## WSL / Restricted Environments

If `pre-commit` fails due to cache permissions, run with a writable cache directory:

```bash
PRE_COMMIT_HOME=/tmp/pre-commit-cache pre-commit run --all-files --show-diff-on-failure
```

## Troubleshooting Quick Fixes

**Detect-secrets fails**

- Update `.secrets.baseline` (or mark known false positives) and avoid real-looking secrets in docs/tests.

**Playwright fails (missing browsers)**

- Install browsers: `npx playwright install chromium`

**`npm test` fails before Playwright starts with a JS syntax error**

- The shell is using the wrong Node runtime for `scripts/preflight-js.mjs`.
- In WSL/non-interactive shells, run `source ~/.nvm/nvm.sh && nvm use 18`, confirm `node -v`, then rerun the E2E stage.

**Host-like package/startup validation fails**

- Run `python scripts/validate_host_load.py` directly to see which check failed.
- Treat import-policy, package-load, or prestartup encoding failures as product regressions that must be fixed before backend tests or E2E.

**E2E fails with “test harness failed to load”**

- Check the console error (module import/exports mismatch is the most common cause).
- Verify all referenced JS modules exist and export expected names.
<!-- ROOKIEUI-GLOBAL-TEST-SOP-RULES:START -->
## RookieUI-Derived Global Testing Rules

These rules preserve this repository's existing test lanes while adding the shared testing baseline used across this workspace.

### Required Reading Order

1. `tests/TEST_SOP.md`
2. `tests/E2E_TESTING_NOTICE.md`
3. `tests/E2E_TESTING_SOP.md`

### Acceptance Rule

A change is not accepted until required checks pass and evidence is recorded. Existing repo-specific gates remain authoritative; this section adds the shared minimum expectations.

Required shared gate:

1. `pre-commit run detect-secrets --all-files`
2. `pre-commit run --all-files --show-diff-on-failure`
3. backend/unit tests through the repo's documented runner, preferring `scripts/run_unittests.py` when present
4. frontend/E2E tests through the repo's documented Playwright or harness lane, usually `npm test` when a Node harness exists
5. targeted type/static validation when the changed surface has a typed frontend or equivalent static contract

If a repo has no frontend/E2E harness, the SOP must state the non-applicability and identify the replacement smoke, unit, or integration lane that catches the same user-facing risk.

### Problem-First Test Design Rule

All test scripts, test harnesses, and validation flows must be designed first to reproduce real failures and catch bugs early.

The purpose of testing is to expose defects, regressions, drift, and broken assumptions before users hit them. Tests must not be designed merely to produce a green validation result, satisfy a checklist, or prove that a happy path still passes. Do not waste validation time on pass-only checks that cannot fail for the bug class under review.

Every bugfix or high-risk change must start from the question: "Which test would have caught this before release?" If the existing gate missed the bug, update the targeted test or SOP flow so the same class of bug fails deterministically next time.

### Bugfix/Hotfix Rule (Reproduce -> Pin -> Sweep)

For bugfix/hotfix work, acceptance evidence must include:

1. pre-fix reproduction evidence
2. post-fix targeted regression evidence
3. final full-gate evidence

A green full gate alone is not sufficient bugfix evidence unless the record also shows how the specific failure was reproduced and pinned.

### Documentation-only Exception

If all touched files are documentation/planning text only and no code, tests, scripts, config, generated artifacts, dependency manifests, or runtime behavior changed, full test execution is optional. Once executable or runtime-affecting files change, this exception does not apply.

### Environment Guardrails

- Keep the Python interpreter consistent across all commands.
- Prefer a project-local virtual environment: `.venv` on Windows and `.venv-wsl` on WSL/Linux when the repo supports dual-OS validation.
- Do not mix global and venv-installed `pre-commit` accidentally.
- Node.js must be 18+ before running frontend/E2E tests.
- On Windows, prefer repo-local `PRE_COMMIT_HOME` to avoid cache lock issues.
- On WSL, if `python` is missing but `python3` exists, create a local shim before running Playwright or harness commands.
- If pre-commit modifies files, review/stage/commit those changes and rerun hooks until clean.

### Evidence Recording

Implementation records must include date/time, OS/environment, command log reference, and pass/fail result for each required stage. If a gate is intentionally skipped as non-applicable, record why and name the replacement validation lane.
<!-- ROOKIEUI-GLOBAL-TEST-SOP-RULES:END -->
