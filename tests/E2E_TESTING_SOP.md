# ComfyUI-Doctor E2E Testing SOP

## Problem-First Test Design Rule

E2E scripts and mocked harness flows must be designed to reproduce failures and catch bugs early. The goal is not to make the harness pass; the goal is to make the harness fail when a real user-facing contract breaks.

When adding or reviewing E2E coverage, prefer assertions that prove final user-visible behavior, request routing, payload shape, state synchronization, and failure feedback. Avoid pass-only checks that only prove the page loaded or a mocked happy path returned.
> Standard Operating Procedure for E2E Testing

This Markdown file is the canonical SOP.

---

## 1. Purpose and Scope

This SOP describes the verified, repeatable steps to run Playwright E2E tests
for ComfyUI-Doctor in local development. The E2E suite runs against the test
harness and mocks (no live ComfyUI backend required).

E2E is the final stage of the repo-local acceptance gate. Run the earlier
stages from `tests/TEST_SOP.md` first (detect-secrets, pre-commit, host-like
package/startup validation, and backend unit tests), then run Playwright.

This SOP is split for two supported environments:

- Windows 11 (native)
- WSL2 (Linux)

---

## 2. Requirements

| Item | Version | Notes |
|------|---------|-------|
| Node.js | 18+ | Required by Playwright and project engines |
| npm | 9+ | Works with Node 18 LTS |
| Playwright browsers | latest | Installed via `npx playwright install chromium` |
| ComfyUI backend (optional) | latest | Only needed for `@integration` telemetry tests |

Notes:

- `playwright.config.js` starts `scripts/e2e-server.mjs` automatically.
  This server hosts static files and provides default `/doctor/*` and `/debugger/*`
  mock responses for stable harness tests.
- If you use WSL and run from `/mnt/c/...`, set a writable temp directory to avoid
  Playwright transform cache permission errors (e.g. `.tmp/playwright` or `/tmp`).
- If you use WSL and run from `/mnt/c/...`, Playwright may also fail to delete/write large
  test artifacts (videos, HTML report) due to Windows/DrvFS permission semantics.
  - Best: clone/move the repo into the WSL Linux filesystem (e.g. `~/src/ComfyUI-Doctor`).
  - Alternative: redirect Playwright outputs using `PW_TEST_OUTPUT_DIR` and `PW_HTML_REPORT_DIR`.
    `scripts/run-playwright.mjs` auto-defaults these to `/tmp/comfyui-doctor/playwright/...`
    when it detects WSL + `/mnt/*`, so you usually don't need to set them manually.
- If you run tests from a non-interactive shell (CI/automation/tools), `nvm` may not auto-load.
  Run `source ~/.nvm/nvm.sh` and confirm `node -v` shows 18+ before `npm test`.

---

## 3. Verified Procedure (Environment-Specific)

These steps were executed and validated in both environments:

### 3.1 Windows 11 (PowerShell)

```powershell
# From the repository root
node -v
npm -v

npm install
npx playwright install chromium

npm test
```

Expected result: `92 passed` (default local harness run, integration telemetry suite excluded).

### 3.2 WSL2 (bash)

```bash
# From the repository root
source ~/.nvm/nvm.sh
nvm use 18
node -v

npm install
npx playwright install chromium

# Run E2E with a safe temp directory (WSL /mnt/c permission fix)
npm test
```

Expected result: `92 passed` (default local harness run, integration telemetry suite excluded).

---

## 4. Step-by-Step Instructions

### 4.1 Windows 11 (PowerShell)

1. Confirm versions:

```powershell
node -v
npm -v
```

2. Install dependencies and browsers:

```powershell
npm install
npx playwright install chromium
```

3. Run tests:

```powershell
npm test
```

### 4.2 WSL2 (bash)

1. Confirm versions:

```bash
source ~/.nvm/nvm.sh
nvm install 18
nvm use 18
node -v
```

2. Install dependencies and browsers:

```bash
npm install
npx playwright install chromium
```

3. Run tests:

```bash
npm test
```

Optional modes (both environments):

```bash
npm run test:ui
npm run test:headed
npm run test:debug
npm run test:report
npm run test:integration
```

`npm run test:integration` runs only `@integration` specs (currently telemetry) and
expects a live ComfyUI backend at `COMFYUI_URL` (default `http://127.0.0.1:8188`).

---

## 5. CI Dual-Track Policy

`phase2-release-gate.yml` runs E2E in two tracks:

- Required track: `npm test` (stable harness tests, excludes `@integration`)
- Optional track: `npm run test:integration` (backend-dependent telemetry tests)

How to enable optional track:

- `workflow_dispatch`: set `run_integration_e2e=true` (optionally set `comfyui_url`)
- Repository variable: set `RUN_INTEGRATION_E2E=true`
- Optional backend URL variable: `COMFYUI_URL`

The required track is merge-blocking. The optional track is informational/non-blocking.

---

## 6. Test Structure

```
tests/
  e2e/
    specs/
      preact-loader.spec.js
      settings.spec.js
      sidebar.spec.js
      statistics.spec.js
    mocks/
      comfyui-app.js
      ui-text.json
    utils/
      helpers.js
    test-harness.html
    README.md
```

---

## 7. Test Harness Behavior

`tests/e2e/test-harness.html` provides a minimal ComfyUI environment:

- Creates mock `window.app` and `window.api`
- Loads `web/doctor.js`
- Sets `window.__doctorTestReady = true` when initialization finishes
- Dispatches a `doctor-ready` event

All tests should wait for readiness using the shared helper (ensures tab content
mounts, not just the ready flag):

```javascript
await page.goto('test-harness.html');
await waitForDoctorReady(page);
```

Notes:

- The Playwright `baseURL` is `http://127.0.0.1:3000/tests/e2e/`
- Use relative paths like `test-harness.html` (do not prefix with `/`)

---

## 8. Mocking Rules (Important for Stability)

`web/doctor.js` imports ComfyUI core modules. Always mock them before `page.goto`:

```javascript
await page.route('**/scripts/app.js', route => {
  route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: 'export const app = window.app;',
  });
});

await page.route('**/scripts/api.js', route => {
  route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: 'export const api = window.api;',
  });
});
```

If tests rely on localized strings, mock `/doctor/ui_text` (or
`/debugger/get_ui_text`) to return `{ language, text }` to avoid missing i18n keys.
Prefer waiting on `waitForI18nLoaded` before asserting translated UI.

---

## 9. Expected Server Behavior

The E2E server (`scripts/e2e-server.mjs`) serves static assets and responds to
common `/doctor/*` and `/debugger/*` endpoints with deterministic mock JSON.

If you still see repeated `404`/`501` for those endpoints, treat it as a setup
regression and verify `npm test` is launching the configured Playwright server.

---

## 10. Preact Loader Tests (A7)

`preact-loader.spec.js` validates:

- Module loading from local vendor files
- Feature flag behavior
- Error handling when CDN is blocked
- Single-instance loading

Run only this file:

```bash
npx playwright test tests/e2e/specs/preact-loader.spec.js
```

Notes:

- The loader uses local files in `web/lib` first, then CDN fallback.
- If local files are missing, CDN access is required.

---

## 11. Troubleshooting

### EACCES errors under /mnt/c

Use a Linux temp directory:

```bash
TMPDIR=/tmp npm test
```

`scripts/run-playwright.mjs` already auto-configures temp/output directories on
WSL `/mnt/*`; this manual override is only for stubborn local environments.

### Node version mismatch

`npm test` runs a preflight check that requires Node 18+.

```bash
source ~/.nvm/nvm.sh
nvm use 18
node -v
```

### `npm test` fails before Playwright starts

If `npm test` stops inside `scripts/preflight-js.mjs` with a JavaScript syntax
error, your shell is not using the required Node 18+ runtime yet. Load Node 18,
confirm `node -v`, then rerun the E2E stage.

```bash
source ~/.nvm/nvm.sh
nvm use 18
node -v
npm test
```


### Port 3000 already in use

Stop the process using port 3000 or update the port in `playwright.config.js`.

### Tests stuck on "Loading..."

Ensure `test-harness.html` is reachable and your test uses `waitForDoctorReady`:

```bash
node scripts/e2e-server.mjs
# Open http://127.0.0.1:3000/tests/e2e/test-harness.html
```

---

## 12. Island Fallback Testing (5C.5)

New helpers in `tests/e2e/utils/helpers.js` for testing Preact island fallback:

```javascript
import {
  disablePreact,
  enablePreact,
  simulateVendorLoadFailure,
  assertChatFallbackUI,
  assertStatsFallbackUI,
  assertIslandActive,
  getIslandErrors
} from '../utils/helpers.js';
```

| Helper | Usage |
|--------|-------|
| `disablePreact(page)` | Call **before** `page.goto()` to disable Preact via localStorage flag |
| `simulateVendorLoadFailure(page)` | Block vendor files + CDN to force fallback |
| `assertChatFallbackUI(page)` | Verify vanilla Chat UI is visible |
| `assertStatsFallbackUI(page)` | Verify vanilla Stats UI is visible |
| `assertIslandActive(page, 'chat'|'stats')` | Verify Preact island is active |
| `getIslandErrors(page)` | Get errors recorded by island registry |

Example test:

```javascript
test('should render vanilla UI when Preact fails', async ({ page }) => {
  await simulateVendorLoadFailure(page);
  await page.goto('test-harness.html');
  await waitForDoctorReady(page);
  await assertChatFallbackUI(page);
});
```

---

## 13. Related Docs

- Playwright docs: <https://playwright.dev/>
- E2E README: `tests/e2e/README.md`
- A7 record: `.planning/260105-A7(Phase 4D)_IMPLEMENTATION_RECORD.md`
- 5C record: `.planning/260107-A7_PHASE_5C_IMPLEMENTATION_RECORD.md`
<!-- ROOKIEUI-GLOBAL-E2E-SOP-RULES:START -->
## RookieUI-Derived Global E2E Rules

This section preserves the repo's existing E2E procedure while adding the shared Playwright/harness baseline used across this workspace.

### Problem-First Test Design Rule

E2E scripts and mocked harness flows must be designed to reproduce failures and catch bugs early. The goal is not to make the harness pass; the goal is to make the harness fail when a real user-facing contract breaks.

When adding or reviewing E2E coverage, prefer assertions that prove final user-visible behavior, request routing, payload shape, state synchronization, and failure feedback. Avoid pass-only checks that only prove the page loaded or a mocked happy path returned.

### Requirements

- Node.js 18+
- npm 9+ when the repo uses npm
- Python command available (`python` or a local shim to `python3`) when the harness serves files through Python
- Playwright Chromium installed with `npx playwright install chromium` when Playwright is used

### Windows (PowerShell)

```powershell
node -v
npm -v
python --version

npm install
npx playwright install chromium
npm test
```

### WSL2 (bash)

```bash
source ~/.nvm/nvm.sh
nvm use 18
node -v
python3 --version

mkdir -p .tmp/bin
ln -sf "$(command -v python3)" .tmp/bin/python

npm install
npx playwright install chromium

mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright \
  PATH=".tmp/bin:$PATH" npm test
```

### Troubleshooting

- `python: command not found` on WSL: create `.tmp/bin/python` as a shim to `python3`.
- Port bind failure: use the repo-documented E2E port override or stop the conflicting process.
- Browser missing: run `npx playwright install chromium`.
- Dependency drift: remove `node_modules` and rerun `npm install`.

### Non-applicable E2E

If the repo does not have a frontend or Playwright harness, document the non-applicability in `tests/TEST_SOP.md` and identify the replacement smoke, unit, or integration lane. Do not treat a missing E2E harness as an unrecorded pass.
<!-- ROOKIEUI-GLOBAL-E2E-SOP-RULES:END -->
