/**
 * Outbound destination policy UI tests.
 *
 * The backend answers `destination_not_allowed` when a base URL is not an operator-approved LLM
 * destination. The settings model list must show localized operator guidance (from the shipped
 * i18n data) instead of a raw code, and switching to a built-in provider must keep working.
 */

import fs from 'fs';
import path from 'path';
import { test, expect } from '@playwright/test';
import { waitForDoctorReady, waitForI18nLoaded, clearStorage } from '../utils/helpers.js';

const UNAPPROVED_URL = 'https://llm-gateway.example.test/v1';

function shippedUiText(lang) {
  const file = path.resolve(process.cwd(), 'i18n_data', `${lang}.json`);
  return JSON.parse(fs.readFileSync(file, 'utf-8')).ui_text;
}

async function mockHost(page, { lang = 'en', listModelsCalls }) {
  await page.route('**/scripts/app.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const app = window.app;',
  }));
  await page.route('**/scripts/api.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const api = window.api;',
  }));
  await page.route('**/doctor/provider_defaults', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ openai: 'https://api.openai.com/v1', deepseek: 'https://api.deepseek.com/v1' }),
  }));
  // The harness api.fetchApi mock reads this file for /doctor/ui_text; serve the shipped dictionary
  // of the language under test as the active (default) language.
  await page.route('**/tests/e2e/mocks/ui-text.json', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ en: shippedUiText(lang) }),
  }));
  await page.route('**/debugger/set_language', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }),
  }));
  await page.route('**/doctor/list_models', (route) => {
    const body = route.request().postDataJSON() || {};
    listModelsCalls.push(body.base_url);
    if (body.base_url === UNAPPROVED_URL) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: 'destination_not_allowed',
          message: 'This LLM endpoint is not approved on this server.',
          models: [],
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, models: [{ id: 'deepseek-chat', name: 'deepseek-chat' }] }),
    });
  });
}

async function openSettings(page, lang, listModelsCalls) {
  await mockHost(page, { lang, listModelsCalls });
  await page.goto('test-harness.html');
  await clearStorage(page);
  await waitForDoctorReady(page);
  await waitForI18nLoaded(page);
  await page.click('.doctor-tab-button[data-tab-id="settings"]');
}

test.describe('Outbound destination policy guidance', () => {
  for (const lang of ['en', 'zh_TW']) {
    test(`shows localized operator guidance for an unapproved base URL (${lang})`, async ({ page }) => {
      const listModelsCalls = [];
      await openSettings(page, lang, listModelsCalls);
      const expected = shippedUiText(lang).llm_destination_not_allowed;
      expect(expected).toContain('DOCTOR_LLM_ALLOWED_BASE_URLS');

      await page.fill('#doctor-baseurl-input', UNAPPROVED_URL);
      await page.click('#doctor-refresh-models-btn');

      const modelSelect = page.locator('#doctor-model-select');
      await expect(modelSelect.locator('option')).toHaveText([expected]);
      await expect(modelSelect).toHaveAttribute('title', expected);
      await expect(modelSelect).not.toContainText('destination_not_allowed');
      expect(listModelsCalls).toContain(UNAPPROVED_URL);
    });
  }

  test('switching to a built-in provider still loads its models', async ({ page }) => {
    const listModelsCalls = [];
    await openSettings(page, 'en', listModelsCalls);

    await page.fill('#doctor-baseurl-input', UNAPPROVED_URL);
    await page.click('#doctor-refresh-models-btn');
    await expect(page.locator('#doctor-model-select option')).toHaveText([shippedUiText('en').llm_destination_not_allowed]);

    await page.selectOption('#doctor-provider-select', 'deepseek');
    await expect(page.locator('#doctor-baseurl-input')).toHaveValue('https://api.deepseek.com/v1');
    await expect(page.locator('#doctor-model-select option', { hasText: 'deepseek-chat' })).toHaveCount(1);
    await expect(page.locator('#doctor-model-select')).toHaveAttribute('title', '');
    expect(listModelsCalls).toContain('https://api.deepseek.com/v1');
  });
});
