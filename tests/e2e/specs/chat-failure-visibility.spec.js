/**
 * Chat island failure visibility.
 *
 * Every chat failure (HTTP error, in-stream error event, network failure, empty stream) must replace
 * the pending `...` reply with a visible, localized, text-only error and leave the composer usable.
 * A user Stop reads as a stop, not as an error. The island's own error/notice bubbles are never sent
 * back to the provider as conversation history.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, clearStorage, disablePreact } from '../utils/helpers.js';

const XSS_MESSAGE = '<img src=x onerror="window.__r62Xss=(window.__r62Xss||0)+1">';

function sse(events) {
  return {
    status: 200,
    contentType: 'text/event-stream',
    body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
  };
}

function jsonError(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

async function openChat(page, chatHandler, { vanilla = false } = {}) {
  await page.route('**/scripts/app.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const app = window.app;',
  }));
  await page.route('**/scripts/api.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const api = window.api;',
  }));
  await page.route('**/doctor/provider_defaults', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({}),
  }));
  await page.route('**/debugger/set_language', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }),
  }));
  await page.route('**/debugger/last_analysis', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({}),
  }));
  await page.route('**/doctor/list_models', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, models: [] }),
  }));
  await page.route('**/doctor/chat', chatHandler);
  if (vanilla) await disablePreact(page);

  await page.goto('test-harness.html');
  // The Preact-disabled flag is read during async init, after goto resolves; keep it in vanilla mode.
  if (!vanilla) await clearStorage(page);
  await waitForDoctorReady(page);
  if (!vanilla) await page.waitForFunction(() => Boolean(window.marked), null, { timeout: 15000 });
  await expect(page.locator('#doctor-input')).toBeVisible();
}

async function submit(page, text) {
  const request = page.waitForRequest('**/doctor/chat');
  await page.fill('#doctor-input', text);
  await page.click('#doctor-send-btn');
  await request;
}

async function sendAndSettle(page, text) {
  await submit(page, text);
  await expect(page.locator('#doctor-input')).toBeEnabled({ timeout: 10000 });
  await page.waitForTimeout(200);
}

async function bubbleTexts(page) {
  return page.$$eval('#doctor-messages .doctor-chat-message', (nodes) => nodes.map((node) => node.textContent.trim()));
}

test.describe('Chat island failure visibility', () => {
  test('HTTP failures replace the pending reply with a visible text error', async ({ page }) => {
    await openChat(page, (route) => route.fulfill(jsonError(500, { error: 'Upstream exploded' })));

    await sendAndSettle(page, 'probe');
    expect.soft(await bubbleTexts(page), 'pending placeholder left behind').not.toContain('...');
    const errors = page.locator('.doctor-chat-message.error');
    await expect.soft(errors).toHaveCount(1);
    await expect.soft(errors.first()).toHaveText('Chat error: Upstream exploded');
  });

  test('in-stream error events become visible errors and keep partial replies', async ({ page }) => {
    const replies = [
      sse([{ error: 'Provider failed', code: 'llm_error', done: true }]),
      sse([{ delta: 'Partial answer', done: false }, { error: 'Provider failed mid-stream', code: 'llm_error', done: true }]),
      sse([{ error: 'Destination refused', code: 'destination_not_allowed', done: true }]),
    ];
    await openChat(page, (route) => route.fulfill(replies.shift()));
    const errors = page.locator('.doctor-chat-message.error');

    await sendAndSettle(page, 'first');
    await expect.soft(errors.nth(0)).toHaveText('Chat error: Provider failed');

    await sendAndSettle(page, 'second');
    await expect.soft(page.locator('.doctor-chat-message.assistant').last()).toHaveText('Partial answer');
    await expect.soft(errors.nth(1)).toHaveText('Chat error: Provider failed mid-stream');

    await sendAndSettle(page, 'third');
    // Stable S29 code -> localized operator guidance, not the raw server string.
    await expect.soft(errors.nth(2)).toContainText('DOCTOR_LLM_ALLOWED_BASE_URLS');
    expect.soft(await bubbleTexts(page), 'pending placeholder left behind').not.toContain('...');
  });

  test('network failures and empty streams do not leave a pending reply', async ({ page }) => {
    const replies = [
      (route) => route.abort('failed'),
      (route) => route.fulfill(sse([{ delta: '', done: true }])),
    ];
    await openChat(page, (route) => replies.shift()(route));
    const errors = page.locator('.doctor-chat-message.error');

    await sendAndSettle(page, 'first');
    await expect.soft(errors.nth(0)).toContainText('Chat error: ');

    await sendAndSettle(page, 'second');
    await expect.soft(errors.nth(1)).toHaveText('Chat error: Stream Error');
    expect.soft(await bubbleTexts(page), 'pending placeholder left behind').not.toContain('...');
  });

  test('error text containing markup is shown literally and never executes', async ({ page }) => {
    const replies = [
      jsonError(500, { error: XSS_MESSAGE }),
      sse([{ error: XSS_MESSAGE, code: 'llm_error', done: true }]),
    ];
    await openChat(page, (route) => route.fulfill(replies.shift()));
    const errors = page.locator('.doctor-chat-message.error');

    await sendAndSettle(page, 'http');
    await sendAndSettle(page, 'stream');
    await page.waitForTimeout(300);
    expect.soft(await page.evaluate(() => window.__r62Xss || 0), 'injected handler executions').toBe(0);
    await expect.soft(page.locator('.doctor-chat-message img'), 'elements parsed from error text').toHaveCount(0);
    await expect.soft(errors).toHaveCount(2);
    await expect.soft(errors.nth(0)).toHaveText(`Chat error: ${XSS_MESSAGE}`);
    await expect.soft(errors.nth(1)).toHaveText(`Chat error: ${XSS_MESSAGE}`);
  });

  test('the composer recovers after a failure and island notices are never sent as history', async ({ page }) => {
    const bodies = [];
    const replies = [
      jsonError(500, { error: 'Upstream exploded' }),
      sse([{ delta: 'Recovered answer', done: false }, { delta: '', done: true }]),
    ];
    await openChat(page, (route) => {
      bodies.push(route.request().postDataJSON());
      return route.fulfill(replies.shift());
    });

    await sendAndSettle(page, 'first try');
    await expect(page.locator('#doctor-input')).toBeEnabled();
    await sendAndSettle(page, 'second try');
    await expect.soft(page.locator('.doctor-chat-message.assistant').last()).toHaveText('Recovered answer');
    expect.soft(bodies).toHaveLength(2);
    expect.soft(bodies[1]?.messages).toEqual([
      { role: 'user', content: 'first try' },
      { role: 'user', content: 'second try' },
    ]);
  });

  test('Stop ends the pending reply with a stop notice instead of an error', async ({ page }) => {
    // The first request never answers; the second one proves the composer recovered.
    const bodies = [];
    const replies = [
      () => new Promise(() => {}),
      (route) => route.fulfill(sse([{ delta: 'After stop', done: false }, { delta: '', done: true }])),
    ];
    await openChat(page, (route) => {
      bodies.push(route.request().postDataJSON());
      return replies.shift()(route);
    });

    await submit(page, 'long question');
    const stop = page.locator('#doctor-stop-btn');
    await expect.soft(stop).toBeVisible({ timeout: 3000 });
    if (await stop.isVisible()) await stop.click();
    await expect.soft(page.locator('#doctor-input')).toBeEnabled({ timeout: 3000 });
    await expect.soft(page.locator('.doctor-chat-message.system')).toHaveText('Generation stopped by user.');
    await expect.soft(page.locator('.doctor-chat-message.error')).toHaveCount(0);
    await expect.soft(stop).toHaveCount(0);
    expect.soft(await bubbleTexts(page), 'pending placeholder left behind').not.toContain('...');

    if (await page.locator('#doctor-input').isEnabled()) {
      await sendAndSettle(page, 'next question');
      await expect.soft(page.locator('.doctor-chat-message.assistant').last()).toHaveText('After stop');
      expect.soft(bodies[1]?.messages).toEqual([
        { role: 'user', content: 'long question' },
        { role: 'user', content: 'next question' },
      ]);
    }
  });

  test('vanilla chat (Preact disabled) still shows chat failures as text', async ({ page }) => {
    await openChat(page, (route) => route.fulfill(jsonError(500, { error: 'Upstream exploded' })), { vanilla: true });
    // The vanilla composer only sends with an active error context.
    await page.evaluate(() => { window.app.Doctor.currentErrorData = { error: 'boom', last_error: 'boom' }; });

    await submit(page, 'probe');
    const messages = page.locator('#doctor-messages');
    await expect(messages).toContainText('Error: Upstream exploded');
    await expect(messages).not.toContainText('Thinking...');
  });
});
