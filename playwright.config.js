// @ts-check
const { defineConfig, devices } = require('@playwright/test');
const path = require('node:path');

const webServerPort = Number(process.env.PW_WEB_SERVER_PORT) || 3000;
const baseURL = process.env.PW_BASE_URL || `http://127.0.0.1:${webServerPort}/tests/e2e/`;
const testOutputDir = process.env.PW_TEST_OUTPUT_DIR || 'test-results';
const htmlReportDir = process.env.PW_HTML_REPORT_DIR || 'playwright-report';
const includeIntegration = process.env.PW_INCLUDE_INTEGRATION === '1';
const isWsl = !!process.env.WSL_DISTRO_NAME || !!process.env.WSL_INTEROP;
const isDrvFs = process.platform !== 'win32' && process.cwd().startsWith('/mnt/');
const isConstrainedFs = isWsl && isDrvFs;
const configuredWorkers = process.env.PW_WORKERS ? Number(process.env.PW_WORKERS) : null;
const resolvedWorkers = process.env.CI
  ? 1
  : (Number.isFinite(configuredWorkers) && configuredWorkers > 0
      ? configuredWorkers
      : (isConstrainedFs ? 1 : undefined));
const resolvedTestTimeout = isConstrainedFs ? 45 * 1000 : 30 * 1000;
const resolvedExpectTimeout = isConstrainedFs ? 7000 : 5000;

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

  // Test artifacts output
  outputDir: path.resolve(testOutputDir),

  // Maximum time one test can run
  timeout: resolvedTestTimeout,

  // Timeout for each assertion
  expect: {
    timeout: resolvedExpectTimeout,
  },

  // Run tests in files in parallel
  fullyParallel: !isConstrainedFs,

  // Keep integration suites out of default local/CI runs.
  grepInvert: includeIntegration ? undefined : /@integration/,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Limit workers on CI for stability
  workers: resolvedWorkers,

  // Reporter to use
  reporter: [
    ['html', { outputFolder: path.resolve(htmlReportDir), open: 'never' }],
    ['list'],
    ...(process.env.CI ? [['github']] : []),
  ],

  // Shared settings for all the projects below
  use: {
    // Base URL for test harness
    // Server runs from project root, so we need the full path to test-harness.html
    baseURL,

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
    command: `node scripts/e2e-server.mjs`,
    port: webServerPort,
    timeout: 120 * 1000,
    // Root cause note: stale reused server can cause intermittent
    // net::ERR_EMPTY_RESPONSE on test-harness navigation.
    // Avoid reusing stale local servers from prior runs/sandboxes.
    // Set PW_REUSE_SERVER=1 to opt in when needed.
    reuseExistingServer: process.env.PW_REUSE_SERVER === '1',
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
