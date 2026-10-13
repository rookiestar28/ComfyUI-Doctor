/**
 * Host-shaped asset path tests.
 *
 * ComfyUI serves this extension's web directory at /extensions/<install folder>/. Loaded through
 * that host-shaped entry, the vendored rendering assets must resolve inside the same folder (never
 * from a CDN) whatever the folder is called, and chat replies must stay readable when they are missing.
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

async function openHarness(page, { query = '', waitForAssets = true } = {}) {
  const requested = [];
  page.on('request', (request) => requested.push(request.url()));
  await mockHost(page);
  await page.goto(`test-harness.html${query}`);
  await waitForDoctorReady(page);
  if (waitForAssets) {
    await page.waitForFunction(() => Boolean(window.marked && window.hljs), null, { timeout: 15000 });
  }
  return requested;
}

const RENDERING_ASSETS = ['github-dark.min.css', 'highlight.min.js', 'marked.min.js'];
const MARKDOWN_REPLY = 'The **sampler** failed; check `cfg_scale`.';

async function sendMarkdownReply(page) {
  await page.route('**/doctor/chat', (route) => route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: sseBody([{ delta: MARKDOWN_REPLY, done: false }, { delta: '', done: true }]),
  }));
  await page.fill('#doctor-input', 'Why did it fail?');
  await page.click('#doctor-send-btn');
}

// One snapshot of everything the rendering path touched, so a failure shows the whole picture.
async function observeRendering(page, requested, pageErrors) {
  const urls = requested.map((url) => new URL(url));
  const reply = page.locator('.chat-messages .doctor-chat-message.assistant').last();
  const hasReply = (await reply.count()) > 0;
  return {
    localAssetRequests: [...new Set(urls
      .filter((url) => !CDN_HOSTS.includes(url.hostname))
      .filter((url) => RENDERING_ASSETS.some((name) => url.pathname.endsWith(`/lib/${name}`)))
      .map((url) => url.pathname))].sort(),
    cdnRequests: urls.filter((url) => CDN_HOSTS.includes(url.hostname)).map((url) => url.href),
    replyText: hasReply ? (await reply.textContent()).trim() : null,
    formattedBold: hasReply ? await reply.locator('strong', { hasText: 'sampler' }).count() : 0,
    pageErrors: [...pageErrors],
  };
}

function collectPageErrors(page) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error && error.message ? error.message : error)));
  return errors;
}

test.describe('Host-shaped extension assets', () => {
  // ComfyUI serves the extension under its install folder name, which is not always ComfyUI-Doctor.
  for (const folder of ['ComfyUI-Doctor', 'comfyui-doctor']) {
    test(`loads rendering assets from /extensions/${folder}/ and renders markdown with the CDN blocked`, async ({ page }) => {
      const pageErrors = collectPageErrors(page);
      if (folder !== 'ComfyUI-Doctor') {
        // Only the install folder exists on this host: the canonical path is a 404, as in ComfyUI.
        await page.route(/\/extensions\/ComfyUI-Doctor\//, (route) => route.fulfill({
          status: 404, contentType: 'application/json', body: '{"success":false}',
        }));
      }
      const requested = await openHarness(page, { query: `?extensionFolder=${folder}`, waitForAssets: false });
      await sendMarkdownReply(page);

      await expect.poll(() => observeRendering(page, requested, pageErrors), { timeout: 10000 }).toEqual({
        localAssetRequests: RENDERING_ASSETS.map((name) => `/extensions/${folder}/lib/${name}`).sort(),
        cdnRequests: [],
        replyText: 'The sampler failed; check cfg_scale.',
        formattedBold: 1,
        pageErrors: [],
      });
    });
  }

  test('degrades to plain text without any CDN request when vendored assets are missing', async ({ page }) => {
    const pageErrors = collectPageErrors(page);
    await page.route(/\/lib\/(marked\.min\.js|highlight\.min\.js|github-dark\.min\.css)$/, (route) => route.fulfill({
      status: 404, contentType: 'application/json', body: '{"success":false}',
    }));
    const requested = await openHarness(page, { query: '?extensionFolder=ComfyUI-Doctor', waitForAssets: false });
    await sendMarkdownReply(page);

    await expect.poll(() => observeRendering(page, requested, pageErrors), { timeout: 10000 }).toEqual({
      localAssetRequests: RENDERING_ASSETS.map((name) => `/extensions/ComfyUI-Doctor/lib/${name}`).sort(),
      cdnRequests: [],
      replyText: MARKDOWN_REPLY,
      formattedBold: 0,
      pageErrors: [],
    });
  });

  test('shows a reply that arrives before marked as text, then re-renders it as markdown', async ({ page }) => {
    const pageErrors = collectPageErrors(page);
    await page.route(/\/lib\/marked\.min\.js$/, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await route.continue();
    });
    const requested = await openHarness(page, { query: '?extensionFolder=ComfyUI-Doctor', waitForAssets: false });
    await sendMarkdownReply(page);

    // While marked is still pending the reply is readable as plain text (not a blank bubble).
    const reply = page.locator('.chat-messages .doctor-chat-message.assistant').last();
    await expect(reply).toHaveText(MARKDOWN_REPLY, { timeout: 3000 });
    await expect.poll(() => observeRendering(page, requested, pageErrors), { timeout: 15000 })
      .toMatchObject({ replyText: 'The sampler failed; check cfg_scale.', formattedBold: 1, cdnRequests: [], pageErrors: [] });
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

    const installFolderAsset = await request.get('/extensions/comfyui-doctor/lib/marked.min.js');
    expect(installFolderAsset.status()).toBe(200);
    const installFolderEscape = await request.get('/extensions/comfyui-doctor/..%2fpackage.json');
    expect(installFolderEscape.status()).toBe(403);

    const rootFile = await request.get('/package.json');
    expect(rootFile.status()).toBe(200);
  });
});
