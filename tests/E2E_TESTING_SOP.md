# ComfyUI-Doctor E2E Testing SOP

> Standard Operating Procedure for E2E Testing

This Markdown file is the canonical SOP.

---

## 1. Purpose and Scope

This SOP describes the verified, repeatable steps to run Playwright E2E tests
for ComfyUI-Doctor in local development. The E2E suite runs against the test
harness and mocks (no live ComfyUI backend required).

This SOP is split for two supported environments:

- Windows 11 (native)
- WSL2 (Linux)

---

## 2. Requirements

| Item | Version | Notes |
|------|---------|-------|
| Node.js | 18+ | Required by Playwright and project engines |
| npm | 9+ | Works with Node 18 LTS |
| Python | 3.8+ | Used by Playwright web server (`python -m http.server 3000`) |
| Playwright browsers | latest | Installed via `npx playwright install chromium` |

Notes:

- `playwright.config.js` starts a local web server using `python -m http.server 3000`.
  Ensure `python` is available on PATH (WSL2 may only have `python3`).
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
python --version

npm install
npx playwright install chromium

npm test
```

Expected result: `55 passed` with no failures.

### 3.2 WSL2 (bash)

```bash
# From the repository root
source ~/.nvm/nvm.sh
nvm use 18
node -v
python3 --version

# Provide `python` if only python3 exists (local shim)
mkdir -p .tmp/bin
ln -sf "$(command -v python3)" .tmp/bin/python

npm install
npx playwright install chromium

# Run E2E with a safe temp directory (WSL /mnt/c permission fix)
mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright \
  PATH=".tmp/bin:$PATH" npm test
```

Expected result: `55 passed` with no failures.

---

## 4. Step-by-Step Instructions

### 4.1 Windows 11 (PowerShell)

1. Confirm versions:

```powershell
node -v
npm -v
python --version
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
python3 --version
```

2. Provide `python` if only `python3` exists:

```bash
mkdir -p .tmp/bin
ln -sf "$(command -v python3)" .tmp/bin/python
```

3. Install dependencies and browsers:

```bash
npm install
npx playwright install chromium
```

4. Run tests with safe temp directory:

```bash
mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright \
  PATH=".tmp/bin:$PATH" npm test
```

Optional modes (both environments):

```bash
npm run test:ui
npm run test:headed
npm run test:debug
npm run test:report
```

---

## 5. Test Structure

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

## 6. Test Harness Behavior

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

## 7. Mocking Rules (Important for Stability)

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

## 8. Expected Server Log Warnings (Normal)

The web server is a static `http.server`. It does not handle POST or real APIs.
During tests you may see:

- `404` for `/doctor/...` endpoints
- `501` for POST requests

These are expected and do not indicate test failure.

---

## 9. Preact Loader Tests (A7)

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

## 10. Troubleshooting

### EACCES errors under /mnt/c

Use a Linux temp directory:

```bash
TMPDIR=/tmp npm test
```

### python not found

`playwright.config.js` uses `python`. On WSL2, create a local shim:

```bash
mkdir -p .tmp/bin
ln -sf "$(command -v python3)" .tmp/bin/python
PATH=".tmp/bin:$PATH" npm test
```

### Port 3000 already in use

Stop the process using port 3000 or update the port in `playwright.config.js`.

### Tests stuck on "Loading..."

Ensure `test-harness.html` is reachable and your test uses `waitForDoctorReady`:

```bash
python3 -m http.server 3000
# Open http://127.0.0.1:3000/tests/e2e/test-harness.html
```

---

## 11. Island Fallback Testing (5C.5)

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

## 12. Related Docs

- Playwright docs: <https://playwright.dev/>
- E2E README: `tests/e2e/README.md`
- A7 record: `.planning/260105-A7(Phase 4D)_IMPLEMENTATION_RECORD.md`
- 5C record: `.planning/260107-A7_PHASE_5C_IMPLEMENTATION_RECORD.md`
