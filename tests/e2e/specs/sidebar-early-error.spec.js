/**
 * Errors that arrive before the Doctor sidebar exists.
 *
 * DoctorUI subscribes to execution errors in its constructor but builds the sidebar panel only
 * after UI text loads. An error delivered in that window must not throw, and auto-open (enabled
 * by default) must apply once the panel exists.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady } from '../utils/helpers.js';

const EARLY_ERROR = {
  node_id: '7',
  node_type: 'KSampler',
  exception_type: 'RuntimeError',
  exception_message: 'early execution error',
  traceback: ['Traceback (most recent call last):', 'RuntimeError: early execution error'],
};

async function mockHostModules(page) {
  await page.route('**/scripts/app.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const app = window.app;',
  }));
  await page.route('**/scripts/api.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const api = window.api;',
  }));
  await page.route('**/doctor/provider_defaults', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: '{}',
  }));
}

test('an execution error before UI text loads is shown once the sidebar exists', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error && error.message ? error.message : error)));
  await mockHostModules(page);

  // Hold the harness UI-text fixture (read by the mock api.fetchApi) until the error has fired.
  let releaseUiText;
  const uiTextGate = new Promise((resolve) => { releaseUiText = resolve; });
  await page.route('**/tests/e2e/mocks/ui-text.json', async (route) => {
    await uiTextGate;
    await route.continue();
  });

  await page.goto('test-harness.html');
  await page.waitForFunction(() => Boolean(window.app && window.app.Doctor));

  const early = await page.evaluate((detail) => {
    const sidebarExists = Boolean(document.getElementById('doctor-sidebar'));
    try {
      window.api._triggerEvent('execution_error', detail);
      return { sidebarExists, thrown: null };
    } catch (error) {
      return { sidebarExists, thrown: String(error && error.message ? error.message : error) };
    }
  }, EARLY_ERROR);

  releaseUiText();
  await waitForDoctorReady(page);

  const after = await page.evaluate(() => {
    const panel = document.getElementById('doctor-sidebar');
    return {
      sidebarExists: Boolean(panel),
      sidebarVisible: Boolean(panel && panel.classList.contains('visible')),
      lastErrorNode: window.app.Doctor.lastErrorData?.node_context?.node_name ?? null,
    };
  });

  expect({ early, after, pageErrors }).toEqual({
    early: { sidebarExists: false, thrown: null },
    after: { sidebarExists: true, sidebarVisible: true, lastErrorNode: 'KSampler' },
    pageErrors: [],
  });
});

test('opening Doctor from the menu before UI text loads applies once the sidebar exists', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error && error.message ? error.message : error)));
  await mockHostModules(page);

  let releaseUiText;
  const uiTextGate = new Promise((resolve) => { releaseUiText = resolve; });
  await page.route('**/tests/e2e/mocks/ui-text.json', async (route) => {
    await uiTextGate;
    await route.continue();
  });

  await page.goto('test-harness.html');
  await page.waitForFunction(() => Boolean(window.app && window.app.Doctor));

  // toggle() is the menu button's click handler.
  const early = await page.evaluate(() => {
    const sidebarExists = Boolean(document.getElementById('doctor-sidebar'));
    try {
      window.app.Doctor.toggle();
      return { sidebarExists, thrown: null };
    } catch (error) {
      return { sidebarExists, thrown: String(error && error.message ? error.message : error) };
    }
  });

  releaseUiText();
  await waitForDoctorReady(page);

  const sidebarVisible = await page.evaluate(() => {
    const panel = document.getElementById('doctor-sidebar');
    return Boolean(panel && panel.classList.contains('visible'));
  });

  expect({ early, sidebarVisible, pageErrors }).toEqual({
    early: { sidebarExists: false, thrown: null },
    sidebarVisible: true,
    pageErrors: [],
  });
});
