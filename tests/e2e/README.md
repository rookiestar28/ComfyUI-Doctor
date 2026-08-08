# ComfyUI Doctor - E2E Tests

Playwright-based end-to-end tests for the ComfyUI Doctor UI.

Requires Node.js `>=18 <26`.

## Setup

### 1. Install Dependencies

```bash
npm install
npx playwright install chromium
```

### 2. Run Tests

```bash
# Run all tests
npm test

# Run integration-only tests (uses harness backend by default)
npm run test:integration

# Run opt-in stress tests (uses harness backend)
npm run test:stress

# Run with UI mode (interactive)
npm run test:ui

# Run in headed mode (see browser)
npm run test:headed

# Debug mode
npm run test:debug

# View last test report
npm run test:report
```

## Test Structure

```
tests/e2e/
├── specs/                    # Test specifications
│   ├── sidebar.spec.js       # ✅ Sidebar toggle and navigation
│   ├── settings.spec.js      # ✅ Settings panel interaction
│   ├── statistics.spec.js    # ✅ Statistics, diagnostics, telemetry, feedback
│   ├── preact-loader.spec.js # ✅ Preact loader and fallback behavior
│   └── error-boundaries.spec.js # ✅ Island error boundaries and recovery
├── mocks/                    # Mock data
│   ├── comfyui-app.js        # Mock ComfyUI app/api objects
│   └── ui-text.json          # Mock i18n translations
├── utils/                    # Test utilities
│   └── helpers.js            # Reusable test functions
└── test-harness.html         # Standalone test page
```

## Current Status

### ✅ Completed
- Playwright setup and configuration
- Test harness with ComfyUI mocks
- Sidebar and chat-context tests
- Owned-pane Chat activation, detached cleanup, and decoy-container regressions
- Settings panel tests
- Statistics, diagnostics, telemetry, and feedback tests
- Preact loader and vanilla fallback tests
- Error boundary and recovery tests

### 🚧 TODO
- Keep adding focused E2E assertions for new user-visible regressions.
- Run `npm run test:integration` separately for telemetry integration coverage; set `COMFYUI_URL` only when validating against a live ComfyUI backend.
- Run `npm run test:stress` separately for opt-in telemetry stress coverage.

## Writing New Tests

### Example Test

```javascript
import { test, expect } from '@playwright/test';
import { waitForDoctorReady, navigateToTab } from '../utils/helpers.js';

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('test-harness.html');
    await waitForDoctorReady(page);
  });

  test('should do something', async ({ page }) => {
    // Your test code here
    const element = page.locator('#my-element');
    await expect(element).toBeVisible();
  });
});
```

## Debugging Tips

### 1. Visual Debugging

```bash
npm run test:ui
```

### 2. See Browser

```bash
npm run test:headed
```

### 3. Pause Execution

```javascript
await page.pause(); // Add this to your test
```

### 4. Screenshots on Failure

Screenshots are automatically captured on test failure and saved to `test-results/`.

## CI Integration

Tests run automatically on GitHub Actions when:
- Pushing to `main` or `dev` branches
- Opening a pull request
- Modifying files in `web/` or `tests/e2e/`

Notes:
- `npm test` excludes `@integration` specs by default.
- `npm test` excludes `@stress` specs by default.
- `npm run test:integration` runs the telemetry integration suite against the harness backend by default, or a live backend when `COMFYUI_URL` is set.
- `npm run test:stress` runs opt-in telemetry stress specs against the harness backend.
- `focused-regression-gate.yml` uses dual-track CI: required `npm test` + optional integration track.

See `.github/workflows/focused-regression-gate.yml` for configuration.
