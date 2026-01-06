# ComfyUI-Doctor E2E Testing SOP

> Standard Operating Procedure for E2E Testing

This Markdown file is the canonical SOP.

---

## 1. Purpose and Scope

This SOP describes the verified, repeatable steps to run Playwright E2E tests
for ComfyUI-Doctor in a local development environment. The E2E suite runs
against the test harness and mocks (no live ComfyUI backend required).

---

## 2. Requirements

| Item | Version | Notes |
|------|---------|-------|
| Node.js | 18+ | Required by Playwright and project engines |
| npm | 9+ | Works with Node 18 LTS |
| Python | 3.8+ | Used by Playwright web server (`python3`) |
| Playwright browsers | latest | Installed via `npx playwright install chromium` |

Notes:
- `playwright.config.js` starts a local web server using `python -m http.server 3000`.
  Ensure `python` is available on PATH (activate `.venv` if needed).
- If you use WSL and run from `/mnt/c/...`, set a writable temp directory to avoid
  Playwright transform cache permission errors (e.g. `.tmp/playwright` or `/tmp`).

---

## 3. Verified Procedure (Local Internal Verification)

These steps were executed and validated on WSL2 using Node 18 and Python 3:

```bash
# From the repository root
source ~/.nvm/nvm.sh
nvm use 18

npm install
npx playwright install chromium

# Run E2E with a safe temp directory (WSL /mnt/c permission fix)
mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright npm test
```

Expected result: `46 passed` with no failures.

---

## 4. Step-by-Step Instructions

### 4.1 Confirm versions

```bash
node -v
npm -v
python3 --version
```

If Node is not 18+, switch to an LTS version (example with nvm):

```bash
source ~/.nvm/nvm.sh
nvm install 18
nvm use 18
nvm alias default 18
```

### 4.2 Install dependencies

```bash
npm install
```

### 4.3 Install Playwright Chromium

```bash
npx playwright install chromium
```

### 4.4 Run E2E tests

```bash
mkdir -p .tmp/playwright
TMPDIR=.tmp/playwright TMP=.tmp/playwright TEMP=.tmp/playwright npm test
```

Optional modes:

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

All tests should wait for readiness:

```javascript
await page.goto('test-harness.html');
await page.waitForFunction(() => window.__doctorTestReady === true, { timeout: 10000 });
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
`playwright.config.js` uses `python3`. Ensure it is installed and on PATH.

### Port 3000 already in use
Stop the process using port 3000 or update the port in `playwright.config.js`.

### Tests stuck on "Loading..."
Ensure `test-harness.html` is reachable:

```bash
python3 -m http.server 3000
# Open http://127.0.0.1:3000/tests/e2e/test-harness.html
```

---

## 11. Related Docs

- Playwright docs: https://playwright.dev/
- E2E README: `tests/e2e/README.md`
- A7 record: `.planning/260105-A7_IMPLEMENTATION_RECORD.md`
