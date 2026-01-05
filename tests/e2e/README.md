# ComfyUI Doctor - E2E Tests

Playwright-based end-to-end tests for the ComfyUI Doctor UI.

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
│   ├── chat.spec.js          # 🚧 TODO
│   ├── errors.spec.js        # 🚧 TODO
│   └── i18n.spec.js          # 🚧 TODO
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
- Sidebar tests (8 test cases)
- Settings panel tests (11 test cases)

### 🚧 TODO
- Chat interface tests
- Error display tests
- i18n switching tests
- CI/CD integration

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

See `.github/workflows/playwright-tests.yml` for configuration.
