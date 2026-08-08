/**
 * Settings Panel Tests
 *
 * Tests the Doctor left sidebar settings panel functionality:
 * - Settings panel toggle
 * - Language selection
 * - Provider selection
 * - Settings persistence
 */

import fs from 'fs';
import path from 'path';
import { test, expect } from '@playwright/test';
import { waitForDoctorReady, waitForI18nLoaded, clearStorage } from '../utils/helpers.js';

const UI_TEXT = JSON.parse(
  fs.readFileSync(path.resolve(process.cwd(), 'tests/e2e/mocks/ui-text.json'), 'utf-8')
);

test.describe('Settings Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the ComfyUI modules that doctor.js tries to import
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

    // Mock backend API endpoints
    await page.route('**/doctor/provider_defaults', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          openai: 'https://api.openai.com/v1',
          deepseek: 'https://api.deepseek.com/v1',
        }),
      });
    });

    await page.route('**/doctor/ui_text*', route => {
      const url = new URL(route.request().url());
      const lang = url.searchParams.get('lang') || 'en';
      const text = UI_TEXT[lang] || UI_TEXT.en || {};
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ language: lang, text }),
      });
    });

    await page.route('**/debugger/set_language', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.goto('test-harness.html');
    await clearStorage(page);

    await waitForDoctorReady(page);
    await waitForI18nLoaded(page);
  });

  test('should register Doctor settings declaratively before setup logic runs', async ({ page }) => {
    const settings = await page.evaluate(() => ({
      enabled: window.app.extensionManager.setting.get('Doctor.General.Enable'),
      language: window.app.extensionManager.setting.get('Doctor.General.Language'),
      autoOpen: window.app.extensionManager.setting.get('Doctor.Behavior.AutoOpenOnError'),
    }));

    expect(settings.enabled).toBe(true);
    expect(settings.language).toBe('en');
    expect(settings.autoOpen).toBe(true);
  });

  test('every registered Doctor setting disables host change telemetry', async ({ page }) => {
    const contract = await page.evaluate(async () => {
      const { DOCTOR_EXTENSION_SETTINGS } = await import('/web/comfyui_frontend_compat.js');
      return DOCTOR_EXTENSION_SETTINGS.map((setting) => ({
        id: setting.id,
        trackChanges: setting.telemetry?.trackChanges,
        telemetryKeyCount: Object.keys(setting.telemetry || {}).length,
      }));
    });

    expect(contract).toHaveLength(11);
    expect(contract.map((setting) => setting.id)).not.toContain('Doctor.LLM.ApiKey');
    expect(contract.every(
      (setting) => setting.trackChanges === false && setting.telemetryKeyCount === 1
    )).toBe(true);
  });

  test('host sidebar API mock exposes current and deprecated wrappers', async ({ page }) => {
    const sidebarApi = await page.evaluate(() => {
      const current = window.app.extensionManager.sidebarTab;
      const legacy = window.app.extensionManager;
      const before = current.sidebarTabs.length;

      legacy.registerSidebarTab({
        id: 'legacy-host-compat',
        title: 'Legacy Host Compat',
        type: 'custom',
        render() {},
      });
      current.registerSidebarTab({
        id: 'current-host-compat',
        title: 'Current Host Compat',
        type: 'custom',
        render() {},
      });

      const ids = current.sidebarTabs.map((tab) => tab.id);
      const deprecatedReadsSameRegistry = legacy.getSidebarTabs().length === current.sidebarTabs.length;

      legacy.unregisterSidebarTab('legacy-host-compat');
      current.unregisterSidebarTab('current-host-compat');

      return {
        hasCurrentRegister: typeof current.registerSidebarTab === 'function',
        hasDeprecatedRegister: typeof legacy.registerSidebarTab === 'function',
        ids,
        deprecatedReadsSameRegistry,
        after: current.sidebarTabs.length,
        before,
      };
    });

    expect(sidebarApi.hasCurrentRegister).toBe(true);
    expect(sidebarApi.hasDeprecatedRegister).toBe(true);
    expect(sidebarApi.ids).toContain('legacy-host-compat');
    expect(sidebarApi.ids).toContain('current-host-compat');
    expect(sidebarApi.deprecatedReadsSameRegistry).toBe(true);
    expect(sidebarApi.after).toBe(sidebarApi.before);
  });

  test('should register Doctor sidebar through current sidebar API when present', async ({ page }) => {
    const registration = await page.evaluate(() => {
      const calls = window.app.__getSidebarRegistrationCalls()
        .filter((call) => call.id === 'comfyui-doctor');
      const sidebarTabs = window.app.extensionManager.sidebarTab.sidebarTabs
        .filter((tab) => tab.id === 'comfyui-doctor');
      return {
        lastSource: calls.at(-1)?.source,
        callCount: calls.length,
        tabCount: sidebarTabs.length,
      };
    });

    expect(registration.lastSource).toBe('extensionManager.sidebarTab');
    expect(registration.callCount).toBe(1);
    expect(registration.tabCount).toBe(1);
  });

  test('should fall back to deprecated sidebar wrapper when current API is absent', async ({ page }) => {
    await page.goto('test-harness.html?sidebarApi=deprecated-only');
    await waitForDoctorReady(page);
    await waitForI18nLoaded(page);

    const registration = await page.evaluate(() => {
      const calls = window.app.__getSidebarRegistrationCalls()
        .filter((call) => call.id === 'comfyui-doctor');
      const sidebarTabs = window.app.extensionManager.getSidebarTabs()
        .filter((tab) => tab.id === 'comfyui-doctor');
      return {
        hasCurrentApi: Boolean(window.app.extensionManager.sidebarTab),
        lastSource: calls.at(-1)?.source,
        callCount: calls.length,
        tabCount: sidebarTabs.length,
      };
    });

    expect(registration.hasCurrentApi).toBe(false);
    expect(registration.lastSource).toBe('extensionManager.registerSidebarTab');
    expect(registration.callCount).toBe(1);
    expect(registration.tabCount).toBe(1);
    await expect(page.locator('.doctor-tab-button[data-tab-id="settings"]')).toBeVisible();
  });

  test('should have settings tab button', async ({ page }) => {
    const toggleBtn = page.locator('.doctor-tab-button[data-tab-id="settings"]');
    await expect(toggleBtn).toBeVisible();
  });

  test('should toggle settings panel visibility via tab', async ({ page }) => {
    const settingsPanel = page.locator('#doctor-settings-panel');
    const settingsTabBtn = page.locator('.doctor-tab-button[data-tab-id="settings"]');
    const chatTabBtn = page.locator('.doctor-tab-button[data-tab-id="chat"]');

    // Panel should be hidden (or non-existent) by default as Chat is default tab
    await expect(settingsPanel).toBeHidden();

    // Click Settings Tab to show
    await settingsTabBtn.click();
    await expect(settingsPanel).toBeVisible();

    // Click Chat Tab to hide Settings
    await chatTabBtn.click();
    await expect(settingsPanel).toBeHidden();
  });

  test('should display language selector', async ({ page }) => {
    // Open settings panel
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const languageSelect = page.locator('#doctor-language-select');
    await expect(languageSelect).toBeVisible();
    await expect(languageSelect).toBeEnabled();
  });

  test('should have all supported languages in selector', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const languageSelect = page.locator('#doctor-language-select');
    const options = await languageSelect.locator('option').allTextContents();

    // Verify all 9 languages are present
    const expectedLanguages = ['English', '繁體中文', '简体中文', '日本語', 'Deutsch', 'Français', 'Italiano', 'Español', '한국어'];

    for (const lang of expectedLanguages) {
      const hasLang = options.some(opt => opt.includes(lang));
      expect(hasLang).toBe(true);
    }
  });

  test('should change language selection', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const languageSelect = page.locator('#doctor-language-select');

    // Get initial value
    const initialValue = await languageSelect.inputValue();

    // Change to Japanese
    await languageSelect.selectOption('ja');

    // Verify value changed
    const newValue = await languageSelect.inputValue();
    expect(newValue).toBe('ja');
    expect(newValue).not.toBe(initialValue);
  });

  test('should display provider selector', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const providerSelect = page.locator('#doctor-provider-select');
    await expect(providerSelect).toBeVisible();
    await expect(providerSelect).toBeEnabled();
  });

  test('should have multiple AI providers', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const providerSelect = page.locator('#doctor-provider-select');
    const options = await providerSelect.locator('option').allTextContents();

    // Should have at least these providers
    expect(options.length).toBeGreaterThan(5);
    expect(options.some(opt => opt.includes('OpenAI'))).toBe(true);
    expect(options.some(opt => opt.includes('DeepSeek'))).toBe(true);
  });

  test('should display API key input', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const apiKeyInput = page.locator('#doctor-apikey-input');
    await expect(apiKeyInput).toBeVisible();
    await expect(apiKeyInput).toHaveAttribute('type', 'password');
  });

  test('should display base URL input', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const baseUrlInput = page.locator('#doctor-baseurl-input');
    await expect(baseUrlInput).toBeVisible();
  });

  test('should display save button', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const saveBtn = page.locator('#doctor-save-settings-btn');
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeEnabled();
  });

  test('should save settings and show feedback', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    // Change language
    const languageSelect = page.locator('#doctor-language-select');
    await languageSelect.selectOption('ja');

    // Click save
    const saveBtn = page.locator('#doctor-save-settings-btn');
    const originalText = await saveBtn.textContent();
    await saveBtn.click();

    await expect(saveBtn).toContainText('Saved');
  });

  test('should persist active tab state', async ({ page }) => {
    // Open settings panel
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    // Verify it's open
    await expect(page.locator('#doctor-settings-panel')).toBeVisible();

    // Reload page
    await page.goto('test-harness.html');
    await waitForDoctorReady(page);

    // Panel should remember open state
    const settingsPanel = page.locator('#doctor-settings-panel');
    const isVisible = await settingsPanel.isVisible();

    // Check localStorage was set
    const storedState = await page.evaluate(() => {
      return localStorage.getItem('doctor_active_tab');
    });
    expect(storedState).toBe('settings');
  });

  // F17: Auto-open toggle tests
  test('should display auto-open toggle checkbox', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    await expect(autoOpenToggle).toBeVisible();
    await expect(autoOpenToggle).toHaveAttribute('type', 'checkbox');
  });

  test('should have auto-open toggle checked by default (new installs)', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    // Default for new installs should be checked (true)
    await expect(autoOpenToggle).toBeChecked();
  });

  test('should display auto-open toggle label with i18n text', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    // Look for the label text near the checkbox
    const labelText = page.locator('label:has(#doctor-auto-open-toggle)');
    await expect(labelText).toContainText('Auto-open error report panel');
  });

  test('should toggle auto-open checkbox state', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');

    // Initially checked (default true)
    await expect(autoOpenToggle).toBeChecked();

    // Click to uncheck
    await autoOpenToggle.click();
    await expect(autoOpenToggle).not.toBeChecked();

    // Click to check again
    await autoOpenToggle.click();
    await expect(autoOpenToggle).toBeChecked();
  });

  test('should save auto-open toggle state', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    const saveBtn = page.locator('#doctor-save-settings-btn');

    // Uncheck the toggle
    await autoOpenToggle.click();
    await expect(autoOpenToggle).not.toBeChecked();

    // Save settings
    await saveBtn.click();
    await expect(saveBtn).toContainText('Saved');

    // Verify setting was stored
    const storedValue = await page.evaluate(() => {
      return window.app.extensionManager.setting.get('Doctor.Behavior.AutoOpenOnError');
    });
    expect(storedValue).toBe(false);
  });

  test('should persist auto-open toggle state after reload', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    const saveBtn = page.locator('#doctor-save-settings-btn');

    // Uncheck the toggle and save
    await autoOpenToggle.click();
    await saveBtn.click();
    await expect(saveBtn).toContainText('Saved');

    // Reload page
    await page.goto('test-harness.html');
    await waitForDoctorReady(page);
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    // Verify toggle state persisted
    const reloadedToggle = page.locator('#doctor-auto-open-toggle');
    await expect(reloadedToggle).not.toBeChecked();
  });

  test('should apply auto-open setting immediately to DoctorUI', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="settings"]');

    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    const saveBtn = page.locator('#doctor-save-settings-btn');

    // Uncheck and save
    await autoOpenToggle.click();
    await saveBtn.click();

    // Verify DoctorUI instance was updated immediately
    const doctorAutoOpen = await page.evaluate(() => {
      return window.app.Doctor?.autoOpenOnError;
    });
    expect(doctorAutoOpen).toBe(false);
  });

  // F17: Behavior tests - verify panel auto-open on new error
  test('should auto-open right panel when enabled and error occurs', async ({ page }) => {
    // Ensure auto-open is ON (default)
    const isAutoOpenOn = await page.evaluate(() => {
      return window.app.Doctor?.autoOpenOnError === true;
    });
    expect(isAutoOpenOn).toBe(true);

    // Close the panel first if it's open
    await page.evaluate(() => {
      const panel = document.getElementById('doctor-sidebar');
      if (panel) {
        panel.classList.remove('visible');
        window.app.Doctor.isVisible = false;
      }
    });

    // Verify panel is closed
    const panelBefore = page.locator('#doctor-sidebar');
    await expect(panelBefore).not.toHaveClass(/visible/);

    // Trigger a new error
    await page.evaluate(() => {
      window.app.Doctor.handleNewError({
        last_error: 'RuntimeError: CUDA out of memory',
        timestamp: new Date().toISOString(),
        node_context: { node_id: '42', node_name: 'KSampler', node_class: 'KSampler' }
      });
    });

    // Panel should auto-open
    await expect(panelBefore).toHaveClass(/visible/, { timeout: 2000 });
  });

  test('should NOT auto-open right panel when disabled and error occurs', async ({ page }) => {
    // Disable auto-open via settings
    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    const autoOpenToggle = page.locator('#doctor-auto-open-toggle');
    const saveBtn = page.locator('#doctor-save-settings-btn');
    await autoOpenToggle.click();
    await saveBtn.click();
    await expect(saveBtn).toContainText('Saved');

    // Verify auto-open is OFF
    const isAutoOpenOff = await page.evaluate(() => {
      return window.app.Doctor?.autoOpenOnError === false;
    });
    expect(isAutoOpenOff).toBe(true);

    // Close the panel
    await page.evaluate(() => {
      const panel = document.getElementById('doctor-sidebar');
      if (panel) {
        panel.classList.remove('visible');
        window.app.Doctor.isVisible = false;
      }
    });

    // Verify panel is closed
    const panelBefore = page.locator('#doctor-sidebar');
    await expect(panelBefore).not.toHaveClass(/visible/);

    // Trigger a new error
    await page.evaluate(() => {
      window.app.Doctor.handleNewError({
        last_error: 'ValueError: invalid input shape',
        timestamp: new Date().toISOString(),
        node_context: { node_id: '99', node_name: 'VAEDecode', node_class: 'VAEDecode' }
      });
    });

    // Panel should remain closed
    await page.waitForTimeout(500); // Give time for any async updates
    await expect(panelBefore).not.toHaveClass(/visible/);
  });

  test('plain dynamic status keeps synchronous and asynchronous tab errors literal', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const payload = '<span id="dynamic-status-tab-marker">tab marker</span>';
      const { TabManager, TabRegistry } = await import('/web/doctor_tabs.js');

      const renderFailure = async (id, render) => {
        const registry = new TabRegistry();
        const content = document.createElement('div');
        const tabBar = document.createElement('div');
        registry.register({ id, label: id, icon: '!', order: 10, render });
        const manager = new TabManager(registry, content, tabBar);
        manager.init();
        await Promise.resolve();
        await Promise.resolve();
        const pane = content.querySelector(`#doctor-tab-${id}`);
        return {
          text: pane.textContent,
          parsedMarker: pane.querySelector('#dynamic-status-tab-marker') !== null,
        };
      };

      return {
        payload,
        sync: await renderFailure('dynamic-status-sync', () => { throw new Error(payload); }),
        async: await renderFailure('dynamic-status-async', async () => { throw new Error(payload); }),
      };
    });

    expect(result.sync.text).toContain(result.payload);
    expect(result.sync.parsedMarker).toBe(false);
    expect(result.async.text).toContain(result.payload);
    expect(result.async.parsedMarker).toBe(false);
  });

  test('plain dynamic status keeps key-store load errors and provider IDs literal', async ({ page }) => {
    const errorPayload = '<span id="dynamic-status-load-marker">load marker</span>';
    const providerPayload = '<span id="dynamic-status-provider-marker">provider marker</span>';
    let requestCount = 0;
    await page.route('**/doctor/secrets/status', route => {
      requestCount += 1;
      const body = requestCount === 1
        ? { success: false, error: errorPayload }
        : { success: true, providers: { [providerPayload]: { source: 'none' } } };
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.locator('#doctor-key-store-section summary').click();
    const grid = page.locator('#doctor-keystore-providers-grid');
    await expect(grid).toContainText(errorPayload);
    await expect(grid.locator('#dynamic-status-load-marker')).toHaveCount(0);

    await page.locator('#doctor-key-store-section summary').click();
    await page.locator('#doctor-key-store-section summary').click();
    await expect(grid).toContainText(providerPayload);
    await expect(grid.locator('#dynamic-status-provider-marker')).toHaveCount(0);
  });

  test('plain dynamic status keeps caught key-store load exceptions literal', async ({ page }) => {
    const payload = '<span id="dynamic-status-load-catch-marker">load catch marker</span>';
    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.evaluate(async errorText => {
      const { DoctorAPI } = await import('/web/doctor_api.js');
      DoctorAPI.getSecretsStatus = async () => { throw new Error(errorText); };
    }, payload);

    await page.locator('#doctor-key-store-section summary').click();
    const grid = page.locator('#doctor-keystore-providers-grid');
    await expect(grid).toContainText(payload);
    await expect(grid.locator('#dynamic-status-load-catch-marker')).toHaveCount(0);
  });

  test('plain dynamic status keeps key-store save result errors literal', async ({ page }) => {
    const payload = '<span id="dynamic-status-save-marker">save marker</span>';
    await page.route('**/doctor/secrets/status', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, providers: {} }),
    }));
    await page.route('**/doctor/secrets', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, error: payload }),
    }));

    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.locator('#doctor-key-store-section summary').click();
    await page.locator('#doctor-keystore-key').fill('fixture-value');
    await page.locator('#doctor-keystore-save-btn').click();

    const status = page.locator('#doctor-keystore-status');
    await expect(status).toContainText(payload);
    await expect(status.locator('#dynamic-status-save-marker')).toHaveCount(0);
    await expect(page.locator('#doctor-keystore-save-btn')).toBeEnabled();
  });

  test('plain dynamic status keeps caught key-store save exceptions literal', async ({ page }) => {
    const payload = '<span id="dynamic-status-save-catch-marker">save catch marker</span>';
    await page.route('**/doctor/secrets/status', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, providers: {} }),
    }));
    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.locator('#doctor-key-store-section summary').click();
    await page.evaluate(async errorText => {
      const { DoctorAPI } = await import('/web/doctor_api.js');
      DoctorAPI.saveSecret = async () => { throw new Error(errorText); };
    }, payload);
    await page.locator('#doctor-keystore-key').fill('fixture-value');
    await page.locator('#doctor-keystore-save-btn').click();

    const status = page.locator('#doctor-keystore-status');
    await expect(status).toContainText(payload);
    await expect(status.locator('#dynamic-status-save-catch-marker')).toHaveCount(0);
    await expect(page.locator('#doctor-keystore-save-btn')).toBeEnabled();
  });

  test('plain dynamic status keeps key-store delete result errors literal', async ({ page }) => {
    const payload = '<span id="dynamic-status-delete-marker">delete marker</span>';
    await page.route('**/doctor/secrets/*', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, error: payload }),
    }));
    await page.route('**/doctor/secrets/status', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, providers: {} }),
    }));
    page.on('dialog', dialog => dialog.accept());

    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.locator('#doctor-key-store-section summary').click();
    await page.locator('#doctor-keystore-delete-btn').click();

    const status = page.locator('#doctor-keystore-status');
    await expect(status).toContainText(payload);
    await expect(status.locator('#dynamic-status-delete-marker')).toHaveCount(0);
    await expect(page.locator('#doctor-keystore-delete-btn')).toBeEnabled();
  });

  test('plain dynamic status keeps caught key-store delete exceptions literal', async ({ page }) => {
    const payload = '<span id="dynamic-status-delete-catch-marker">delete catch marker</span>';
    await page.route('**/doctor/secrets/status', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, providers: {} }),
    }));
    page.on('dialog', dialog => dialog.accept());
    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.locator('#doctor-key-store-section summary').click();
    await page.evaluate(async errorText => {
      const { DoctorAPI } = await import('/web/doctor_api.js');
      DoctorAPI.clearSecret = async () => { throw new Error(errorText); };
    }, payload);
    await page.locator('#doctor-keystore-delete-btn').click();

    const status = page.locator('#doctor-keystore-status');
    await expect(status).toContainText(payload);
    await expect(status.locator('#dynamic-status-delete-catch-marker')).toHaveCount(0);
    await expect(page.locator('#doctor-keystore-delete-btn')).toBeEnabled();
  });

  test('plain dynamic status preserves key-store validation and success feedback', async ({ page }) => {
    await page.route('**/doctor/secrets/*', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    }));
    await page.route('**/doctor/secrets/status', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, providers: { openai: { source: 'env' } } }),
    }));
    await page.route('**/doctor/secrets', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    }));
    page.on('dialog', dialog => dialog.accept());

    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    await page.evaluate(() => {
      const doctorUI = window.app.Doctor;
      const originalGetUIText = doctorUI.getUIText.bind(doctorUI);
      const keyStoreText = {
        keystore_status_required: 'Provider and API Key are required.',
        keystore_save_success: 'Saved {0} key to server.',
        keystore_delete_success: 'Deleted {0} key.',
      };
      doctorUI.getUIText = key => keyStoreText[key] || originalGetUIText(key);
    });
    await page.locator('#doctor-key-store-section summary').click();
    const status = page.locator('#doctor-keystore-status');
    const grid = page.locator('#doctor-keystore-providers-grid');
    await expect(grid).toContainText('openai');
    await expect(grid).toContainText('ENV');

    await page.locator('#doctor-keystore-save-btn').click();
    await expect(status).toContainText('required');
    await expect(status.locator('span')).toHaveCSS('color', 'rgb(240, 173, 78)');

    await page.locator('#doctor-keystore-key').fill('fixture-value');
    await page.locator('#doctor-keystore-save-btn').click();
    await expect(status).toContainText('openai');
    await expect(status.locator('span')).toHaveCSS('color', 'rgb(76, 175, 80)');
    await expect(page.locator('#doctor-keystore-save-btn')).toBeEnabled();

    await page.locator('#doctor-keystore-delete-btn').click();
    await expect(status).toContainText('openai');
    await expect(status.locator('span')).toHaveCSS('color', 'rgb(76, 175, 80)');
    await expect(page.locator('#doctor-keystore-delete-btn')).toBeEnabled();
  });
});
