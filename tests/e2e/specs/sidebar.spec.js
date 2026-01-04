/**
 * Sidebar UI Tests
 *
 * Tests the Doctor sidebar's basic functionality:
 * - Opening and closing
 * - Toggle button behavior
 * - Initial state
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, openDoctorSidebar, closeDoctorSidebar, clearStorage } from '../utils/helpers.js';

test.describe('Doctor Sidebar', () => {
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

    // Navigate to test harness first
    await page.goto('/tests/e2e/test-harness.html');

    // Clear storage after page loads to avoid security errors
    await clearStorage(page);

    // Wait for Doctor UI to initialize
    await waitForDoctorReady(page);
  });

  test('should have a toggle button visible', async ({ page }) => {
    const toggleBtn = page.locator('#doctor-toggle-btn');

    await expect(toggleBtn).toBeVisible();
    await expect(toggleBtn).toBeEnabled();
  });

  test('should start with sidebar closed by default', async ({ page }) => {
    const sidebar = page.locator('#doctor-sidebar');

    // Sidebar should not be visible initially
    const isVisible = await sidebar.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });

  test('should open sidebar when toggle button is clicked', async ({ page }) => {
    const toggleBtn = page.locator('#doctor-toggle-btn');
    const sidebar = page.locator('#doctor-sidebar');

    // Click toggle button
    await toggleBtn.click();

    // Sidebar should become visible
    await expect(sidebar).toBeVisible({ timeout: 5000 });

    // Verify sidebar has expected content
    await expect(sidebar).toContainText('ComfyUI Doctor');
  });

  test('should close sidebar when toggle button is clicked again', async ({ page }) => {
    const toggleBtn = page.locator('#doctor-toggle-btn');
    const sidebar = page.locator('#doctor-sidebar');

    // Open sidebar
    await toggleBtn.click();
    await expect(sidebar).toBeVisible();

    // Close sidebar
    await toggleBtn.click();

    // Sidebar should be hidden
    await expect(sidebar).not.toBeVisible();
  });

  test('should toggle sidebar multiple times correctly', async ({ page }) => {
    const toggleBtn = page.locator('#doctor-toggle-btn');
    const sidebar = page.locator('#doctor-sidebar');

    // Test multiple open/close cycles
    for (let i = 0; i < 3; i++) {
      // Open
      await toggleBtn.click();
      await expect(sidebar).toBeVisible();

      // Close
      await toggleBtn.click();
      await expect(sidebar).not.toBeVisible();
    }
  });

  test('should display all three tabs when sidebar is open', async ({ page }) => {
    await openDoctorSidebar(page);

    // Check for tab buttons
    const errorsTab = page.locator('[data-tab="errors"]');
    const chatTab = page.locator('[data-tab="chat"]');
    const settingsTab = page.locator('[data-tab="settings"]');

    await expect(errorsTab).toBeVisible();
    await expect(chatTab).toBeVisible();
    await expect(settingsTab).toBeVisible();
  });

  test('should have "errors" tab active by default', async ({ page }) => {
    await openDoctorSidebar(page);

    const errorsTab = page.locator('[data-tab="errors"]');

    // Errors tab should have "active" class
    await expect(errorsTab).toHaveClass(/active/);
  });

  test('should persist sidebar state in localStorage', async ({ page }) => {
    // Open sidebar
    await openDoctorSidebar(page);

    // Check localStorage
    const isOpen = await page.evaluate(() => {
      return localStorage.getItem('doctor_sidebar_open') === 'true';
    });

    expect(isOpen).toBe(true);

    // Close sidebar
    await closeDoctorSidebar(page);

    // Check localStorage again
    const isClosed = await page.evaluate(() => {
      return localStorage.getItem('doctor_sidebar_open') === 'false';
    });

    expect(isClosed).toBe(true);
  });
});
