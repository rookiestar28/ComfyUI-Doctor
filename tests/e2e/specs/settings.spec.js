/**
 * Settings Panel Tests
 *
 * Tests the Doctor settings panel functionality:
 * - Navigation to settings tab
 * - Language selection
 * - Settings persistence
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, navigateToTab, clearStorage, mockApiResponse } from '../utils/helpers.js';

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

    await page.goto('/tests/e2e/test-harness.html');
    await clearStorage(page);
    await waitForDoctorReady(page);
  });

  test('should navigate to settings tab', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const settingsTab = page.locator('[data-tab="settings"]');
    await expect(settingsTab).toHaveClass(/active/);

    // Verify settings panel is visible
    const settingsPanel = page.locator('#doctor-settings-panel');
    await expect(settingsPanel).toBeVisible();
  });

  test('should display language selector', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const languageSelect = page.locator('#doctor-language-select');
    await expect(languageSelect).toBeVisible();
    await expect(languageSelect).toBeEnabled();
  });

  test('should have all supported languages in selector', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const languageSelect = page.locator('#doctor-language-select');
    const options = await languageSelect.locator('option').allTextContents();

    // Verify all 9 languages are present
    const expectedLanguages = ['en', 'zh_TW', 'zh_CN', 'ja', 'de', 'fr', 'it', 'es', 'ko'];

    for (const lang of expectedLanguages) {
      const hasLang = options.some(opt => opt.includes(lang) || opt.toLowerCase().includes(lang));
      expect(hasLang).toBe(true);
    }
  });

  test('should change language selection', async ({ page }) => {
    await navigateToTab(page, 'settings');

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

  test('should display save settings button', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const saveBtn = page.locator('#doctor-save-settings-btn');
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeEnabled();
  });

  test('should save settings when save button is clicked', async ({ page }) => {
    // Mock the settings save API endpoint
    await mockApiResponse(page, '/doctor/settings', { success: true });

    await navigateToTab(page, 'settings');

    // Change language
    const languageSelect = page.locator('#doctor-language-select');
    await languageSelect.selectOption('ja');

    // Click save
    const saveBtn = page.locator('#doctor-save-settings-btn');
    await saveBtn.click();

    // Wait for save operation
    await page.waitForTimeout(500);

    // Verify settings were persisted in localStorage
    const savedLanguage = await page.evaluate(() => {
      return localStorage.getItem('doctor_language');
    });

    expect(savedLanguage).toBe('ja');
  });

  test('should display API provider settings', async ({ page }) => {
    await navigateToTab(page, 'settings');

    // Check for provider selector
    const providerSelect = page.locator('#doctor-provider-select');
    await expect(providerSelect).toBeVisible();
  });

  test('should display API key input field', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const apiKeyInput = page.locator('#doctor-api-key-input');
    await expect(apiKeyInput).toBeVisible();

    // API key field should be password type
    await expect(apiKeyInput).toHaveAttribute('type', 'password');
  });

  test('should display model selection', async ({ page }) => {
    await navigateToTab(page, 'settings');

    const modelInput = page.locator('#doctor-model-input');
    await expect(modelInput).toBeVisible();
  });

  test('should load saved settings on initialization', async ({ page }) => {
    // Pre-set settings in localStorage
    await page.evaluate(() => {
      localStorage.setItem('doctor_language', 'zh_CN');
      localStorage.setItem('doctor_provider', 'deepseek');
      localStorage.setItem('doctor_model', 'deepseek-chat');
    });

    // Reload page
    await page.goto('/tests/e2e/test-harness.html');
    await waitForDoctorReady(page);
    await navigateToTab(page, 'settings');

    // Verify settings were loaded
    const languageValue = await page.locator('#doctor-language-select').inputValue();
    expect(languageValue).toBe('zh_CN');

    const providerValue = await page.locator('#doctor-provider-select').inputValue();
    expect(providerValue).toBe('deepseek');

    const modelValue = await page.locator('#doctor-model-input').inputValue();
    expect(modelValue).toBe('deepseek-chat');
  });
});
