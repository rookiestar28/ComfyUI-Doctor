/**
 * Test helper utilities for Playwright tests
 */

/**
 * Wait for Doctor UI to be fully initialized
 * @param {import('@playwright/test').Page} page
 */
export async function waitForDoctorReady(page) {
  // Wait for the custom ready event
  await page.waitForFunction(() => window.__doctorTestReady === true, null, { timeout: 20000 });

  // Ensure at least one tab's content has actually mounted (preact or vanilla).
  await page.waitForFunction(() => {
    return Boolean(
      // Settings tab
      document.querySelector('#doctor-settings-panel') ||
      // Stats tab
      document.querySelector('#doctor-statistics-panel') ||
      document.querySelector('#doctor-stats-content') ||
      // Chat tab (vanilla + preact)
      document.querySelector('#doctor-error-context') ||
      document.querySelector('#doctor-sanitization-status') ||
      document.querySelector('#doctor-messages') ||
      document.querySelector('.chat-messages')
    );
  }, null, { timeout: 20000 });
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

// ═══════════════════════════════════════════════════════════════════════════
// 5C.5: ISLAND FALLBACK TESTING HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Disable Preact before page load by setting localStorage flag.
 * Must be called BEFORE navigating to the page.
 * @param {import('@playwright/test').Page} page
 */
export async function disablePreact(page) {
  await page.addInitScript(() => {
    localStorage.setItem('doctor_preact_disabled', 'true');
  });
}

/**
 * Enable Preact (remove disable flag).
 * @param {import('@playwright/test').Page} page
 */
export async function enablePreact(page) {
  await page.evaluate(() => {
    localStorage.removeItem('doctor_preact_disabled');
  });
}

/**
 * Block vendor files to simulate Preact load failure.
 * Forces fallback to vanilla UI.
 * @param {import('@playwright/test').Page} page
 */
export async function simulateVendorLoadFailure(page) {
  await page.route('**/web/lib/**', route => route.abort());
  await page.route('**/esm.sh/**', route => route.abort());
}

/**
 * Assert that fallback (vanilla) Chat UI is visible.
 * @param {import('@playwright/test').Page} page
 */
export async function assertChatFallbackUI(page) {
  const { expect } = await import('@playwright/test');

  // Vanilla Chat UI has these elements
  const chatMessages = page.locator('#doctor-messages');
  const chatInput = page.locator('#doctor-input');
  const sendBtn = page.locator('#doctor-send-btn');

  await expect(chatMessages).toBeVisible({ timeout: 5000 });
  await expect(chatInput).toBeVisible();
  await expect(sendBtn).toBeVisible();
}

/**
 * Assert that fallback (vanilla) Stats UI is visible.
 * @param {import('@playwright/test').Page} page
 */
export async function assertStatsFallbackUI(page) {
  const { expect } = await import('@playwright/test');

  // Vanilla Stats UI has these elements
  const statsPanel = page.locator('#doctor-statistics-panel, #doctor-stats-content');
  await expect(statsPanel.first()).toBeVisible({ timeout: 5000 });
}

/**
 * Assert that Preact island is active (not vanilla fallback).
 * Checks for island-specific markers.
 * @param {import('@playwright/test').Page} page
 * @param {'chat' | 'stats'} islandType
 */
export async function assertIslandActive(page, islandType) {
  const isActive = await page.evaluate((type) => {
    const doctorUI = window.app?.Doctor;
    if (!doctorUI) return false;
    return type === 'chat' ? doctorUI.chatIslandActive : doctorUI.statsIslandActive;
  }, islandType);

  const { expect } = await import('@playwright/test');
  expect(isActive).toBe(true);
}

/**
 * Get island registry errors (for testing error boundary).
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<Array<{id: string, timestamp: number}>>}
 */
export async function getIslandErrors(page) {
  return await page.evaluate(async () => {
    try {
      const registry = await import('/web/island_registry.js');
      return registry.getErrors().map(e => ({ id: e.id, timestamp: e.timestamp }));
    } catch {
      return [];
    }
  });
}
