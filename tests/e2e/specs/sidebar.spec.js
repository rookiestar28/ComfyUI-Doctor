/**
 * Sidebar UI Tests
 *
 * Tests the Doctor right panel and chat interface:
 * - Messages area
 * - Input controls
 * - Error context display
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, clearStorage } from '../utils/helpers.js';

test.describe('Doctor Chat Interface', () => {
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
        body: JSON.stringify({}),
      });
    });

    await page.route('**/doctor/ui_text*', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sidebar_doctor_title: 'Doctor',
          no_errors: 'No errors detected',
        }),
      });
    });

    await page.route('**/debugger/set_language', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.route('**/debugger/last_analysis', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });

    // Navigate to test harness first
    await page.goto('/tests/e2e/test-harness.html');

    // Clear storage after page loads to avoid security errors
    await clearStorage(page);

    // Wait for Doctor UI to initialize
    await waitForDoctorReady(page);
  });

  test('should display messages area', async ({ page }) => {
    const messages = page.locator('#doctor-messages');
    await expect(messages).toBeVisible();
  });

  test('should display default no errors message', async ({ page }) => {
    const messages = page.locator('#doctor-messages');
    const content = await messages.textContent();

    // Should show "no errors" or similar message
    expect(content?.toLowerCase()).toContain('no error');
  });

  test('should have input textarea', async ({ page }) => {
    const input = page.locator('#doctor-input');
    await expect(input).toBeVisible();
    await expect(input).toBeEnabled();
  });

  test('should have send button', async ({ page }) => {
    const sendBtn = page.locator('#doctor-send-btn');
    await expect(sendBtn).toBeVisible();
    await expect(sendBtn).toBeEnabled();
  });

  test('should have clear button', async ({ page }) => {
    const clearBtn = page.locator('#doctor-clear-btn');
    await expect(clearBtn).toBeVisible();
    await expect(clearBtn).toBeEnabled();
  });

  test('should allow typing in input field', async ({ page }) => {
    const input = page.locator('#doctor-input');

    await input.fill('Test message');
    const value = await input.inputValue();

    expect(value).toBe('Test message');
  });

  test('should display error context area', async ({ page }) => {
    const errorContext = page.locator('#doctor-error-context');

    // Error context should exist but be hidden by default
    const count = await errorContext.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should have Doctor title in header', async ({ page }) => {
    // Check for Doctor title icon in the sidebar header
    const header = page.locator('#mock-sidebar-tabs');
    const headerText = await header.textContent();

    // The header should contain either "Doctor" or the hospital emoji
    const hasTitle = headerText.includes('Doctor') || headerText.includes('🏥');
    expect(hasTitle).toBe(true);
  });
});
