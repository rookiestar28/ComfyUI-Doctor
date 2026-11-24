/**
 * Opt-in workflow context for chat requests.
 *
 * The backend can narrow a workflow to the failed node's neighborhood, but the sidebar never sent one.
 * The graph carries prompts, file names and custom-node settings, so it leaves the machine only when the
 * user turns "send the workflow with chat questions" on; the default is off. These specs capture the real
 * chat request the island sends and the real settings panel, with the host's graph mocked.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, clearStorage } from '../utils/helpers.js';

const SETTING_ID = 'Doctor.Behavior.IncludeWorkflowContext';
const GRAPH_MARKER = 'a20-graph-only-marker';
const NODE = {
  id: 3, type: 'KSampler', widgets_values: [5, 'fixed', 20, 8, 'euler', 'normal', 1], properties: { marker: GRAPH_MARKER },
};
const ERROR_CONTEXT = {
  last_error: 'RuntimeError: CUDA out of memory',
  traceback: 'Traceback (most recent call last):\n  File "x.py", line 1\nRuntimeError: CUDA out of memory',
  node_context: { node_id: '3', node_class: 'KSampler' },
};

async function openHarness(page, { withError = true, vanilla = false } = {}) {
  const bodies = [];
  await page.route('**/scripts/app.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const app = window.app;',
  }));
  await page.route('**/scripts/api.js', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: 'export const api = window.api;',
  }));
  for (const [pattern, body] of [
    ['**/doctor/provider_defaults', {}],
    ['**/debugger/set_language', { success: true }],
    ['**/debugger/last_analysis', {}],
    ['**/doctor/list_models', { success: true, models: [] }],
  ]) {
    await page.route(pattern, (route) => route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(body),
    }));
  }
  await page.route('**/doctor/chat', (route) => {
    bodies.push(route.request().postDataJSON());
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [{ delta: 'ok', done: false }, { done: true }].map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
    });
  });
  await page.goto('test-harness.html');
  await clearStorage(page);
  await waitForDoctorReady(page);
  if (vanilla) {
    // The vanilla fallback chat (DoctorUI.sendToAI) is what renders when Preact is unavailable.
    await page.evaluate(() => localStorage.setItem('doctor_preact_disabled', 'true'));
    await page.reload();
    await waitForDoctorReady(page);
  }
  await page.evaluate(({ node, errorContext, withErrorContext }) => {
    window.app.rootGraph._nodes = [node];
    if (withErrorContext) window.app.Doctor.updateSidebarTab(errorContext);
  }, { node: NODE, errorContext: ERROR_CONTEXT, withErrorContext: withError });
  return bodies;
}

async function sendChat(page, bodies) {
  const before = bodies.length;
  const request = page.waitForRequest('**/doctor/chat');
  await page.fill('#doctor-input', 'why did it fail?');
  await page.click('#doctor-send-btn');
  await request;
  await expect(page.locator('#doctor-input')).toBeEnabled({ timeout: 10000 });
  expect(bodies.length).toBe(before + 1);
  return bodies[bodies.length - 1];
}

const setSetting = (page, value) => page.evaluate(
  ({ id, next }) => window.app.ui.settings.setSettingValue(id, next),
  { id: SETTING_ID, next: value },
);

test.describe('Chat workflow context (opt-in)', () => {
  test('the setting is registered and off by default', async ({ page }) => {
    await openHarness(page);

    const value = await page.evaluate((id) => window.app.ui.settings.getSettingValue(id), SETTING_ID);

    expect(value).toBe(false);
  });

  test('by default the chat request carries the error context and no workflow', async ({ page }) => {
    const bodies = await openHarness(page);

    const body = await sendChat(page, bodies);

    expect(body.error_context.last_error).toBe(ERROR_CONTEXT.last_error);
    expect(Object.keys(body.error_context)).not.toContain('workflow');
    expect(JSON.stringify(body)).not.toContain(GRAPH_MARKER);
  });

  test('with the setting on the request also carries the serialized graph', async ({ page }) => {
    const bodies = await openHarness(page);
    await setSetting(page, true);

    const body = await sendChat(page, bodies);

    expect(body.error_context.last_error).toBe(ERROR_CONTEXT.last_error);
    expect(body.error_context.node_context).toEqual(ERROR_CONTEXT.node_context);
    expect(typeof body.error_context.workflow).toBe('string');
    const graph = JSON.parse(body.error_context.workflow);
    expect(graph.nodes.map((node) => [node.id, node.type])).toEqual([[3, 'KSampler']]);
    expect(body.error_context.workflow).toContain(GRAPH_MARKER);
  });

  test('turning the setting off again stops sending the workflow', async ({ page }) => {
    const bodies = await openHarness(page);
    await setSetting(page, true);
    expect(Object.keys((await sendChat(page, bodies)).error_context)).toContain('workflow');

    await setSetting(page, false);

    expect(Object.keys((await sendChat(page, bodies)).error_context)).not.toContain('workflow');
  });

  test('a chat without a stored error still works and may carry the graph when opted in', async ({ page }) => {
    const bodies = await openHarness(page, { withError: false });
    await setSetting(page, true);

    const body = await sendChat(page, bodies);

    expect(typeof body.error_context.workflow).toBe('string');
    expect(Object.keys(body.error_context)).toEqual(['workflow']);
  });

  test('a graph that is too large to send whole is left out instead of cut', async ({ page }) => {
    const bodies = await openHarness(page);
    await page.evaluate(() => {
      window.app.rootGraph._nodes = [{ id: 1, type: 'Big', widgets_values: ['x'.repeat(300000)] }];
    });
    await setSetting(page, true);

    const body = await sendChat(page, bodies);

    expect(Object.keys(body.error_context)).not.toContain('workflow');
    expect(body.error_context.last_error).toBe(ERROR_CONTEXT.last_error);
  });

  test('a graph that cannot be serialized never blocks the chat', async ({ page }) => {
    const bodies = await openHarness(page);
    await page.evaluate(() => {
      window.app.rootGraph.serialize = () => { throw new Error('serialize failed'); };
    });
    await setSetting(page, true);

    const body = await sendChat(page, bodies);

    expect(Object.keys(body.error_context)).not.toContain('workflow');
    expect(body.messages.at(-1).content).toBe('why did it fail?');
  });

  test('a host without a graph never blocks the chat', async ({ page }) => {
    const bodies = await openHarness(page);
    await page.evaluate(() => { window.app.rootGraph = null; window.app.graph = null; });
    await setSetting(page, true);

    const body = await sendChat(page, bodies);

    expect(Object.keys(body.error_context)).not.toContain('workflow');
  });

  test('the vanilla fallback chat sends no workflow by default and the graph once opted in', async ({ page }) => {
    const bodies = await openHarness(page, { vanilla: true });

    const off = await sendChat(page, bodies);
    expect(off.error_context.last_error).toBe(ERROR_CONTEXT.last_error);
    expect(Object.keys(off.error_context)).not.toContain('workflow');
    expect(JSON.stringify(off)).not.toContain(GRAPH_MARKER);

    await setSetting(page, true);
    const on = await sendChat(page, bodies);
    expect(on.error_context.last_error).toBe(ERROR_CONTEXT.last_error);
    expect(on.error_context.workflow).toContain(GRAPH_MARKER);
  });

  test('the settings tab shows the toggle unchecked and saves the choice', async ({ page }) => {
    await openHarness(page);
    await page.click('.doctor-tab-button[data-tab-id="settings"]');
    const toggle = page.locator('#doctor-include-workflow-toggle');
    await expect(toggle).toBeVisible();
    await expect(toggle).not.toBeChecked();
    await expect(page.locator('#doctor-include-workflow-hint')).not.toBeEmpty();

    await toggle.check();
    await page.click('#doctor-save-settings-btn');

    await expect.poll(() => page.evaluate((id) => window.app.ui.settings.getSettingValue(id), SETTING_ID)).toBe(true);
  });
});
