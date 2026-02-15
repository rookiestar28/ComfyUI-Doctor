# Test SOP

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

### Optional: One-Command Full Test Scripts (Fastest)

Use these if you want a single command that runs **all required steps** (detect-secrets, pre-commit, unit tests, E2E). These scripts also handle the most common environment issues (Windows cache locks, Black cache, Node 18).
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

`scripts/pre_push_checks.sh` is the CI-parity guard and must include all 4 stages:
1) `detect-secrets`
2) all `pre-commit` hooks
3) backend unit tests (`scripts/run_unittests.py --pattern "test_*.py"`)
4) frontend E2E (`npm test`)

IMPORTANT:
- Do not remove stage (3). If pre-push skips backend unit tests, local pushes can pass while GitHub CI fails later.
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

## Chat Connector (Telegram / Discord / LINE) — Manual Test SOP

The chat connector runs as a **separate process** and talks to your local ComfyUI/OpenClaw via HTTP.

### Prereq: use the correct Python interpreter

The connector requires `aiohttp`. A common failure mode on Windows is:

- `pip show aiohttp` succeeds (installed in your conda env)
- but `python3 -m connector` uses a different Python (e.g. system Python) and crashes with `ModuleNotFoundError: aiohttp`

Sanity check:

```powershell
python -c "import sys; print(sys.executable)"
python -c "import aiohttp; print(aiohttp.__version__)"
```

Run the connector with **the same** interpreter:

```powershell
python -m connector
```

### Common env (all platforms)

- `OPENCLAW_CONNECTOR_URL`: ComfyUI base URL (default: `http://127.0.0.1:8188`)
- `OPENCLAW_CONNECTOR_ADMIN_TOKEN`: optional; required for admin endpoints if your server enforces it
- `OPENCLAW_CONNECTOR_DEBUG=1`: verbose logs (recommended while setting up allowlists)

### 1) Telegram (recommended first: no webhook/HTTPS required)

Minimum:

```powershell
$env:OPENCLAW_CONNECTOR_TELEGRAM_TOKEN="123456:ABC..."
$env:OPENCLAW_CONNECTOR_TELEGRAM_ALLOWED_USERS="123456789"   # your Telegram user_id
$env:OPENCLAW_CONNECTOR_ADMIN_USERS="123456789"             # for admin-only commands
python -m connector
```

Test commands (in Telegram chat with the bot):

- `/help`
- `/status`
- `/jobs`
- `/run <template_id> key=value --approval`
- `/approvals`
- `/approve <approval_id>`

### 2) Discord (no webhook/HTTPS required; requires Message Content Intent)

In Discord Developer Portal, enable **Message Content Intent** for your bot, otherwise the connector can connect but won’t receive message text.

Minimum:

```powershell
$env:OPENCLAW_CONNECTOR_DISCORD_TOKEN="discord_bot_token"
$env:OPENCLAW_CONNECTOR_DISCORD_ALLOWED_USERS="your_discord_user_id"
$env:OPENCLAW_CONNECTOR_ADMIN_USERS="your_discord_user_id"
python -m connector
```

Optional allowlist by channel instead:

```powershell
$env:OPENCLAW_CONNECTOR_DISCORD_ALLOWED_CHANNELS="your_channel_id"
```

### 3) LINE (requires a public HTTPS webhook URL)

LINE is webhook-based: LINE servers must be able to `POST` into your connector.
Localhost (`127.0.0.1`) is not reachable from LINE, so you typically need **Cloudflare Tunnel** or **ngrok**.

Minimum:

```powershell
$env:OPENCLAW_CONNECTOR_LINE_CHANNEL_SECRET="line_channel_secret"
$env:OPENCLAW_CONNECTOR_LINE_CHANNEL_ACCESS_TOKEN="line_channel_access_token"
$env:OPENCLAW_CONNECTOR_LINE_ALLOWED_USERS="your_line_user_id"
$env:OPENCLAW_CONNECTOR_ADMIN_USERS="your_line_user_id"
python -m connector
```

Optional bind/port/path:

```powershell
$env:OPENCLAW_CONNECTOR_LINE_BIND="127.0.0.1"
$env:OPENCLAW_CONNECTOR_LINE_PORT="8099"
$env:OPENCLAW_CONNECTOR_LINE_PATH="/line/webhook"
$env:OPENCLAW_CONNECTOR_PUBLIC_BASE_URL="https://<public-host>" # Required for images
```

After starting the connector, expose it via tunnel and set the LINE webhook URL to:
`https://<public-host>/line/webhook`

If messages are ignored, enable debug and check allowlist logs (user/group/room IDs).

#### LINE Image Delivery (F33) — Quick Test
1) Ensure `OPENCLAW_CONNECTOR_PUBLIC_BASE_URL` is set to a **public HTTPS** URL.
2) Send `/run <template_id> <prompt> --approval` and approve if required.
3) On completion, the bot should push an image message to LINE.

If you receive a text fallback warning, the public URL is missing, not HTTPS, or unreachable from LINE.

## Templates + `/run` — Authoring & Validation SOP

`/run` does **not** take a ComfyUI “workflow id”. It takes a **`template_id`** that maps to a JSON workflow file.

### Where templates live

In this repo (and in your ComfyUI install), templates are loaded from:

- `data/templates/*.json` (the exported ComfyUI workflow in API format)
- `data/templates/manifest.json` (optional metadata: defaults, etc)

### Step-by-step: create a new template

1) Export a workflow JSON from ComfyUI (API format)

- Build your workflow in ComfyUI
- Export the workflow JSON (API format) to a file, e.g. `z.json`

1) Copy the exported file into the template directory

- Place it at: `data/templates/z.json`

1) Replace input values with placeholders

The renderer performs **strict placeholder substitution**:

- ✅ supported: a JSON string value exactly equal to `{{key}}`
  - Example: `"text": "{{positive_prompt}}"`
- ❌ not supported: partial substitutions
  - Example: `"text": "Prompt: {{positive_prompt}}"` (will not be replaced)

So for each field you want to make configurable via chat/webhook, replace the value with a placeholder:

- `{{positive_prompt}}`
- `{{negative_prompt}}`
- `{{seed}}`
- etc.

1) Add an entry to `manifest.json`

This step is **optional**. If you want defaults/metadata, add a new entry under `templates` in `data/templates/manifest.json`:

```json
"your_template_id": {
  "path": "z.json",
  "allowed_inputs": ["positive_prompt"],
  "defaults": {}
}
```

Rules:

- `your_template_id` becomes the identifier used by `/run your_template_id ...` (typically match the file name, e.g. `z`)
- `allowed_inputs` is **metadata only** (not enforced); it can be used by UIs/tools for hints
- `defaults` is optional but recommended (use `{}` if none)
- JSON cannot contain trailing commas

1) Restart ComfyUI

Not strictly required (the backend hot-reloads `manifest.json`), but restarting ComfyUI is still recommended after significant template changes.

### Validate templates are visible

Use the template quick-list endpoint:

- `GET /openclaw/templates`
- `GET /api/openclaw/templates` (browser-friendly)
- Diagnostics (when a template is unexpectedly missing):
  - `GET /api/openclaw/templates?debug=1` (shows which `manifest.json` path was actually loaded)

Expected response:

- `ok: true`
- `templates: [{ id, allowed_inputs, defaults }, ...]`

### Use `/run` from chat

**Free-text prompt support (no `key=value` needed):**

- `/run <template_id> <free text> seed=-1`
- Connector maps free-text to a prompt key:
  - If `manifest.json` `allowed_inputs` has exactly one key → it uses that.
  - Otherwise prefers: `positive_prompt` → `prompt` → `text` → `positive` → `caption`.
  - If none match, defaults to `positive_prompt`.
- Ensure the template uses the same placeholder (e.g., `"text": "{{positive_prompt}}"`).

Once the template appears in `/openclaw/templates`, you can run it via chat:

- Run immediately:
  - `/run your_template_id positive_prompt="a cat" seed=123`
- Request approval:
  - `/run your_template_id positive_prompt="a cat" seed=123 --approval`

Unused keys have no effect unless the workflow contains a matching `{{key}}` placeholder.

## Admin Token & UI Usage (SOP)

**Key rule:** `OPENCLAW_ADMIN_TOKEN` is a **server-side environment variable**.
The UI can **use** an Admin Token for authenticated requests, but **cannot set or persist** the server token.

### Recommended setup (local only)

1) **Set server token (env)**

```powershell
$env:OPENCLAW_ADMIN_TOKEN="your_admin_token_here"
```

2) **Restart ComfyUI**
2) **Enter the same token in the Settings UI**
   - This only stores it in the browser session for API calls.

### Windows CMD (per-session)

```cmd
set OPENCLAW_ADMIN_TOKEN=your_admin_token_here
set OPENCLAW_LLM_API_KEY=your_api_key_here
set OPENCLAW_LLM_PROVIDER=gemini
```

### Windows CMD (persistent, user-level)

```cmd
setx OPENCLAW_ADMIN_TOKEN "your_admin_token_here"
setx OPENCLAW_LLM_API_KEY "your_api_key_here"
setx OPENCLAW_LLM_PROVIDER "gemini"
```

> After `setx`, open a **new** terminal session before launching ComfyUI.

### Security Notes

- Do **not** expose ComfyUI to the internet with UI-only tokens.
- Admin token must remain server-side and protected by OS/environment.

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

**E2E fails with “test harness failed to load”**

- Check the console error (module import/exports mismatch is the most common cause).
- Verify all referenced JS modules exist and export expected names.
