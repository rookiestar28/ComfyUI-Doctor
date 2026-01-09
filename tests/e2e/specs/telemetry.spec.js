/**
 * E2E Tests for Telemetry Feature (S3)
 * 
 * Tests:
 * 1. Toggle OFF → no events recorded
 * 2. Toggle ON → events recorded
 * 3. View Buffer → alert shows events
 * 4. Clear All → buffer emptied
 * 5. Export → downloads JSON
 */

const { test, expect } = require('@playwright/test');

// Base URL for ComfyUI
const BASE_URL = process.env.COMFYUI_URL || 'http://127.0.0.1:8188';

test.describe('S3: Telemetry Feature', () => {

    test.beforeEach(async ({ page }) => {
        // Navigate to ComfyUI
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');

        // Wait for Doctor sidebar to be available
        await page.waitForTimeout(2000);
    });

    test('telemetry status endpoint returns correct format', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/doctor/telemetry/status`);
        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data.success).toBe(true);
        expect(typeof data.enabled).toBe('boolean');
        expect(data.stats).toBeDefined();
        expect(data.upload_destination).toBeNull(); // Phase 1-3: local only
    });

    test('toggle OFF prevents event recording', async ({ request }) => {
        // Disable telemetry
        const toggleRes = await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
        expect(toggleRes.ok()).toBeTruthy();
        const toggleData = await toggleRes.json();
        expect(toggleData.enabled).toBe(false);

        // Try to track an event
        const trackRes = await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'feature', action: 'tab_switch', label: 'chat' }
        });
        const trackData = await trackRes.json();
        expect(trackData.success).toBe(false);
        expect(trackData.message).toContain('disabled');
    });

    test('toggle ON enables event recording', async ({ request }) => {
        // Enable telemetry
        const toggleRes = await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: true }
        });
        expect(toggleRes.ok()).toBeTruthy();
        const toggleData = await toggleRes.json();
        expect(toggleData.enabled).toBe(true);

        // Clear buffer first
        await request.post(`${BASE_URL}/doctor/telemetry/clear`);

        // Track an event
        const trackRes = await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'feature', action: 'tab_switch', label: 'chat' }
        });
        const trackData = await trackRes.json();
        expect(trackData.success).toBe(true);

        // Verify buffer has event
        const bufferRes = await request.get(`${BASE_URL}/doctor/telemetry/buffer`);
        const bufferData = await bufferRes.json();
        expect(bufferData.count).toBeGreaterThanOrEqual(1);
        expect(bufferData.events.some(e => e.label === 'chat')).toBe(true);

        // Cleanup: disable telemetry
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
    });

    test('clear empties buffer', async ({ request }) => {
        // Enable and add event
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: true }
        });
        await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'session', action: 'start' }
        });

        // Clear
        const clearRes = await request.post(`${BASE_URL}/doctor/telemetry/clear`);
        expect(clearRes.ok()).toBeTruthy();
        const clearData = await clearRes.json();
        expect(clearData.success).toBe(true);

        // Verify buffer is empty
        const bufferRes = await request.get(`${BASE_URL}/doctor/telemetry/buffer`);
        const bufferData = await bufferRes.json();
        expect(bufferData.count).toBe(0);

        // Cleanup
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
    });

    test('export returns downloadable JSON', async ({ request }) => {
        // Enable and add event
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: true }
        });
        await request.post(`${BASE_URL}/doctor/telemetry/clear`);
        await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'feature', action: 'tab_switch', label: 'stats' }
        });

        // Export
        const exportRes = await request.get(`${BASE_URL}/doctor/telemetry/export`);
        expect(exportRes.ok()).toBeTruthy();

        const contentDisp = exportRes.headers()['content-disposition'];
        expect(contentDisp).toContain('attachment');
        expect(contentDisp).toContain('telemetry_export.json');

        const body = await exportRes.text();
        const events = JSON.parse(body);
        expect(Array.isArray(events)).toBe(true);
        expect(events.some(e => e.label === 'stats')).toBe(true);

        // Cleanup
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
    });

    test('/track rejects cross-origin requests with 403', async ({ request }) => {
        // Simulate cross-origin by sending mismatched Origin header
        const response = await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'feature', action: 'tab_switch', label: 'chat' },
            headers: {
                'Origin': 'http://evil.example.com',
                'Host': 'localhost:8188'
            }
        });

        // Should be rejected
        expect(response.status()).toBe(403);
    });

    test('/track rejects invalid category with error', async ({ request }) => {
        // Enable telemetry
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: true }
        });

        const response = await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'invalid_category', action: 'invalid_action' }
        });

        const data = await response.json();
        expect(data.success).toBe(false);
        expect(data.message).toContain('category');

        // Cleanup
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
    });

    test('/track rejects payload over 1KB', async ({ request }) => {
        // Enable telemetry
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: true }
        });

        // Create payload > 1KB
        const largeLabel = 'x'.repeat(2000);
        const response = await request.post(`${BASE_URL}/doctor/telemetry/track`, {
            data: { category: 'feature', action: 'tab_switch', label: largeLabel }
        });

        expect(response.status()).toBe(413);

        // Cleanup
        await request.post(`${BASE_URL}/doctor/telemetry/toggle`, {
            data: { enabled: false }
        });
    });

});
