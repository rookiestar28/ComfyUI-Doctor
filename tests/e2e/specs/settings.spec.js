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

    // Debug: capture console output
    page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

    await page.goto('test-harness.html');
    await clearStorage(page);

    // Debug: check for test harness error
    const hasError = await page.evaluate(() => window.__doctorTestError);
    if (hasError) {
      console.log('TEST HARNESS ERROR:', hasError);
    }

    await waitForDoctorReady(page);
    await waitForI18nLoaded(page);
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
});
