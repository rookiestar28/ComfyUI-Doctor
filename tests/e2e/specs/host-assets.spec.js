/**
 * Host-shaped asset path tests.
 *
 * ComfyUI serves this extension's web directory at /extensions/<folder>/. The default harness
 * must load the vendored rendering assets from that host-shaped path (never from a CDN) so chat
 * markdown and code highlighting are exercised the way users see them.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady } from '../utils/helpers.js';

const CDN_HOSTS = ['cdn.jsdelivr.net', 'esm.sh'];

function sseBody(events) {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
}

async function mockHost(page) {
  // Abort (but still observe) CDN fallbacks so rendering can only succeed through local assets.
  await page.route(/^https:\/\/(cdn\.jsdelivr\.net|esm\.sh)\//, (route) => route.abort());
  await page.route('**/scripts/app.js', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: 'export const app = window.app;',
  }));
  await page.route('**/scripts/api.js', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: 'export const api = window.api;',
  }));
  await page.route('**/doctor/provider_defaults', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: '{}',
  }));
  await page.route('**/doctor/list_models', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, models: [] }),
  }));
  await page.route('**/doctor/statistics*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      statistics: {
        total_errors: 0,
        pattern_frequency: {},
        category_breakdown: {},
        top_patterns: [],
        resolution_rate: { resolved: 0, unresolved: 0, ignored: 0 },
        trend: { last_24h: 0, last_7d: 0, last_30d: 0 },
      },
    }),
  }));
}

async function openHarness(page) {
  const requested = [];
  page.on('request', (request) => requested.push(request.url()));
  await mockHost(page);
  await page.goto('test-harness.html');
  await waitForDoctorReady(page);
  await page.waitForFunction(() => Boolean(window.marked && window.hljs), null, { timeout: 15000 });
  return requested;
}

test.describe('Host-shaped extension assets', () => {
  test('loads marked and highlight.js from /extensions/ComfyUI-Doctor/ without any CDN request', async ({ page }) => {
    const requested = await openHarness(page);

    const paths = requested.map((url) => new URL(url).pathname);
    expect(paths).toContain('/extensions/ComfyUI-Doctor/lib/marked.min.js');
    expect(paths).toContain('/extensions/ComfyUI-Doctor/lib/highlight.min.js');
    const cdnRequests = requested.filter((url) => CDN_HOSTS.includes(new URL(url).hostname));
    expect(cdnRequests).toEqual([]);
  });

  test('renders a markdown chat reply as formatted HTML', async ({ page }) => {
    await page.route('**/doctor/chat', (route) => route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody([
        { delta: 'The **sampler** failed; check `cfg_scale`.', done: false },
        { delta: '', done: true },
      ]),
    }));
    await openHarness(page);

    await page.fill('#doctor-input', 'Why did it fail?');
    await page.click('#doctor-send-btn');

    const messages = page.locator('.chat-messages');
    await expect(messages.locator('strong', { hasText: 'sampler' })).toBeVisible();
    await expect(messages.locator('code', { hasText: 'cfg_scale' })).toBeVisible();
    await expect(messages).not.toContainText('**sampler**');
  });

  test('keeps the host-shaped alias confined to web/', async ({ request }) => {
    const asset = await request.get('/extensions/ComfyUI-Doctor/lib/marked.min.js');
    expect(asset.status()).toBe(200);

    const escaped = await request.get('/extensions/ComfyUI-Doctor/..%2fpackage.json');
    expect(escaped.status()).toBe(403);

    const rootFile = await request.get('/package.json');
    expect(rootFile.status()).toBe(200);
  });
});
