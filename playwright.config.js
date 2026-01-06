// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright Configuration for ComfyUI-Doctor
 *
 * Tests the frontend UI in isolation without requiring a full ComfyUI installation.
 * Uses a test harness HTML file with mocked ComfyUI dependencies.
 *
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  // Test directory
  testDir: './tests/e2e/specs',

  // Maximum time one test can run
  timeout: 30 * 1000,

  // Timeout for each assertion
  expect: {
    timeout: 5000,
  },

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Limit workers on CI for stability
  workers: process.env.CI ? 1 : undefined,

  // Reporter to use
  reporter: [
    ['html'],
    ['list'],
    ...(process.env.CI ? [['github']] : []),
  ],

  // Shared settings for all the projects below
  use: {
    // Base URL for test harness
    // Server runs from project root, so we need the full path to test-harness.html
    baseURL: 'http://127.0.0.1:3000/tests/e2e/',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Screenshot only on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Browser context options
    viewport: { width: 1280, height: 720 },
    actionTimeout: 10000,
  },

  // Configure projects for different browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Uncomment to test on other browsers (slower)
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Run local web server before starting tests
  // Serve from project root so that /web/doctor_ui.js paths work correctly
  webServer: {
    command: 'python -m http.server 3000',
    port: 3000,
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
