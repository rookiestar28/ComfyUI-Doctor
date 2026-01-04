/**
 * Test helper utilities for Playwright tests
 */

/**
 * Wait for Doctor UI to be fully initialized
 * @param {import('@playwright/test').Page} page
 */
export async function waitForDoctorReady(page) {
  // Wait for the custom ready event
  await page.waitForFunction(() => window.__doctorTestReady === true, {
    timeout: 10000,
  });

  // Additional wait for any async operations
  await page.waitForTimeout(200);
}

/**
 * Open the Doctor sidebar if it's closed
 * @param {import('@playwright/test').Page} page
 */
export async function openDoctorSidebar(page) {
  const sidebar = page.locator('#doctor-sidebar');
  const isVisible = await sidebar.isVisible().catch(() => false);

  if (!isVisible) {
    await page.click('#doctor-toggle-btn');
    await sidebar.waitFor({ state: 'visible', timeout: 5000 });
  }
}

/**
 * Close the Doctor sidebar if it's open
 * @param {import('@playwright/test').Page} page
 */
export async function closeDoctorSidebar(page) {
  const sidebar = page.locator('#doctor-sidebar');
  const isVisible = await sidebar.isVisible().catch(() => false);

  if (isVisible) {
    await page.click('#doctor-toggle-btn');
    await sidebar.waitFor({ state: 'hidden', timeout: 5000 });
  }
}

/**
 * Navigate to a specific tab in the Doctor sidebar
 * @param {import('@playwright/test').Page} page
 * @param {'errors' | 'chat' | 'settings'} tabName
 */
export async function navigateToTab(page, tabName) {
  await openDoctorSidebar(page);
  await page.click(`[data-tab="${tabName}"]`);
  await page.waitForTimeout(200); // Wait for tab transition
}

/**
 * Get the current active tab
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<string>}
 */
export async function getActiveTab(page) {
  const activeTab = await page.locator('.doctor-tab.active').getAttribute('data-tab');
  return activeTab;
}

/**
 * Mock an API response
 * @param {import('@playwright/test').Page} page
 * @param {string} endpoint - The API endpoint to mock
 * @param {object} response - The response data
 * @param {number} status - HTTP status code (default: 200)
 */
export async function mockApiResponse(page, endpoint, response, status = 200) {
  await page.route(`**${endpoint}`, route => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}

/**
 * Trigger a mock error event
 * @param {import('@playwright/test').Page} page
 * @param {object} errorData
 */
export async function triggerMockError(page, errorData) {
  await page.evaluate((data) => {
    window.__testMocks.api._triggerEvent('execution_error', data);
  }, errorData);
}

/**
 * Clear all localStorage data
 * @param {import('@playwright/test').Page} page
 */
export async function clearStorage(page) {
  // Use context.clearCookies() instead of page.evaluate to avoid security errors
  // This works even with file:// protocol and http:// protocol
  try {
    await page.context().clearCookies();
  } catch (e) {
    // Ignore errors if cookies can't be cleared
  }

  // Try to clear storage, but don't fail if it's not accessible yet
  try {
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  } catch (e) {
    // Storage not accessible yet, which is fine for beforeEach hooks
    // It will be cleared when the page actually loads
  }
}

/**
 * Wait for UI text to be loaded (i18n)
 * @param {import('@playwright/test').Page} page
 */
export async function waitForI18nLoaded(page) {
  await page.waitForFunction(() => {
    return window.app?.Doctor?.uiText && Object.keys(window.app.Doctor.uiText).length > 0;
  }, { timeout: 10000 });
}
