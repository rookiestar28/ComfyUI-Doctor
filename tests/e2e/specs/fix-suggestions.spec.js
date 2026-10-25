/**
 * Fix-suggestion trust boundary.
 *
 * Fix blocks come from LLM output and are prompt-injectable: their fields must render as inert
 * text, only assistant messages may offer fix buttons, and a fix may change only the exact live
 * node/widget it names with a strictly validated value. Anything ambiguous fails closed without
 * mutating the graph.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, clearStorage } from '../utils/helpers.js';

const XSS_WIDGET = '<img src=x onerror="window.__s27Xss=(window.__s27Xss||0)+1">';
const XSS_REASON = '<svg onload="window.__s27Xss=(window.__s27Xss||0)+1">';

function fixBlock(fixes) {
  return '```json\n' + JSON.stringify({ fixes }) + '\n```';
}

function sse(events) {
  return {
    status: 200,
    contentType: 'text/event-stream',
    body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
  };
}

async function openChat(page, chatHandler) {
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
  if (chatHandler) await page.route('**/doctor/chat', chatHandler);

  await page.goto('test-harness.html');
  await clearStorage(page);
  await waitForDoctorReady(page);
  await page.waitForFunction(() => Boolean(window.marked), null, { timeout: 15000 });
  await expect(page.locator('#doctor-input')).toBeVisible();
}

async function sendChat(page, text) {
  await page.fill('#doctor-input', text);
  await page.click('#doctor-send-btn');
}

test.describe('Fix suggestion trust boundary', () => {
  for (const scenario of ['raw', 'nested', 'ambiguous', 'duplicate', 'removed']) {
    test(`opaque target ${scenario}: chat click changes only an exact unique live node`, async ({ page }) => {
      const opaque = 'insert:synthetic-operation:root:node:9';
      const targetId = scenario === 'nested' ? `host:synthetic:${opaque}`
        : scenario === 'ambiguous' ? '12:5' : opaque;
      const block = fixBlock([{ node_id: targetId, widget: 'steps', to: 25 }]);
      const logs = [];
      page.on('console', (message) => {
        if (message.text().startsWith('[FixHandler]')) logs.push(message.text());
      });
      await openChat(page, (route) => route.fulfill(sse([{ delta: block, done: false }, { done: true }])));
      await page.evaluate(({ opaque, targetId, scenario }) => {
        const make = (id) => ({ id, widgets: [{ name: 'steps', type: 'number', value: 20 }] });
        const root = window.app.rootGraph;
        const target = make(scenario === 'nested' ? opaque : targetId);
        const other = make('insert:other:root:node:9');
        const numeric = make(9);
        const innerLeaf = make(5);
        root._nodes = [other, numeric];
        if (scenario === 'nested') {
          const inner = { _nodes: [target] };
          target.graph = inner;
          root._nodes.push({ id: 'host:synthetic', subgraph: inner, isSubgraphNode: () => true });
        } else if (scenario !== 'removed') {
          root._nodes.push(target);
        }
        if (scenario === 'ambiguous') root._nodes.push({ id: 12, subgraph: { _nodes: [innerLeaf] }, isSubgraphNode: () => true });
        if (scenario === 'duplicate') root._nodes.push(make(targetId));
        window.__identityTargets = { target, other, numeric, innerLeaf };
      }, { opaque, targetId, scenario });
      await sendChat(page, 'apply the synthetic fix');
      const button = page.locator('.doctor-chat-message.assistant .doctor-fix-btn');
      await expect(button).toHaveCount(1);
      await button.click();
      const accepted = scenario === 'raw' || scenario === 'nested';
      if (accepted) await expect(button).toHaveClass(/applied/);
      else await expect(button).not.toHaveClass(/applied/);
      expect(await page.evaluate(() => Object.fromEntries(Object.entries(window.__identityTargets)
        .map(([name, node]) => [name, node.widgets[0].value])))).toEqual({
        target: accepted ? 25 : 20, other: 20, numeric: 20, innerLeaf: 20,
      });
      if (accepted) expect(logs.filter((line) => line.includes('Applied'))).toEqual(['[FixHandler] Applied fix']);
    });
  }

  test('streamed fix fields render as inert text and never execute', async ({ page }) => {
    const block = fixBlock([{ node_id: '1', widget: XSS_WIDGET, from: XSS_WIDGET, to: XSS_WIDGET, reason: XSS_REASON }]);
    await openChat(page, (route) => route.fulfill(sse([
      { delta: 'Try this fix:\n' + block, done: false },
      { delta: '\nGood luck.', done: false },
      { delta: '', done: true },
    ])));

    await sendChat(page, 'probe');
    const button = page.locator('.doctor-chat-message.assistant .doctor-fix-btn');
    await expect(button).toHaveCount(1);
    await page.waitForTimeout(300);
    // Soft assertions: report every observation (execution count, parsed elements, text, title).
    expect.soft(await page.evaluate(() => window.__s27Xss || 0), 'injected handler executions').toBe(0);
    await expect.soft(button.locator('img, svg'), 'elements parsed from fix fields').toHaveCount(0);
    await expect.soft(button).toContainText(XSS_WIDGET);
    await expect.soft(button).toHaveAttribute('title', XSS_REASON);
  });

  test('fix blocks in user, system and error messages render no fix buttons', async ({ page }) => {
    const block = fixBlock([{ node_id: '1', widget: 'seed', to: 1 }]);
    await openChat(page, (route) => route.fulfill(sse([{ delta: 'No fix needed.', done: false }, { delta: '', done: true }])));

    await sendChat(page, 'Please apply:\n' + block);
    await expect(page.locator('.doctor-chat-message.assistant')).toContainText('No fix needed.');
    // System/error bubbles are created by the island itself (e.g. failures); inject them through
    // the same state module instance the island renders from.
    await page.evaluate(async (text) => {
      const { doctorContext } = await import('/web/doctor_state.js');
      doctorContext.addMessage('system', 'Error: ' + text);
      doctorContext.addMessage('error', text);
    }, block);
    await expect(page.locator('.doctor-chat-message.system')).toContainText('Error');
    await expect(page.locator('.doctor-chat-message.error')).toHaveCount(1);
    await expect.soft(page.locator('.doctor-chat-message.user .doctor-fix-btn')).toHaveCount(0);
    await expect.soft(page.locator('.doctor-chat-message.system .doctor-fix-btn')).toHaveCount(0);
    await expect.soft(page.locator('.doctor-chat-message.error .doctor-fix-btn')).toHaveCount(0);
  });

  test('a valid assistant fix applies to the named root node through the chat button', async ({ page }) => {
    const block = fixBlock([{ node_id: '30', widget: 'steps', from: 20, to: '25', reason: 'more steps' }]);
    await openChat(page, (route) => route.fulfill(sse([{ delta: 'Fix:\n' + block, done: false }, { delta: '', done: true }])));
    await page.evaluate(() => {
      window.__s27Dirty = 0;
      window.app.rootGraph.setDirtyCanvas = () => { window.__s27Dirty += 1; };
      window.app.rootGraph._nodes.push({ id: 30, title: 'KSampler', widgets: [{ name: 'steps', type: 'number', value: 20, options: { min: 1, max: 150 } }] });
    });

    await sendChat(page, 'fix it');
    const button = page.locator('.doctor-chat-message.assistant .doctor-fix-btn');
    await expect(button).toHaveCount(1);
    await button.click();
    await expect(button).toHaveClass(/applied/);
    expect(await page.evaluate(() => window.app.rootGraph.getNodeById(30).widgets[0].value)).toBe(25);
    expect(await page.evaluate(() => window.__s27Dirty)).toBeGreaterThan(0);
  });

  test('fixes resolve only the exact live node and validate values strictly', async ({ page }) => {
    await openChat(page, null);
    const result = await page.evaluate(async () => {
      const { FixHandler } = await import('/web/doctor_fix_handler.js');
      const graph = window.app.rootGraph;
      let dirty = 0;
      graph.setDirtyCanvas = () => { dirty += 1; };
      const makeGraph = (nodes) => ({
        _nodes: nodes,
        getNodeById(id) { return this._nodes.find((node) => String(node.id) === String(id)) || null; },
      });
      const inner = makeGraph([
        { id: 5, title: 'inner-5', widgets: [{ name: 'seed', type: 'number', value: 1 }] },
      ]);
      graph._nodes.push(
        // Real subgraph host whose own (promoted) seed widget must not be touched by "12:5".
        { id: 12, title: 'subgraph-12', subgraph: inner, isSubgraphNode: () => true,
          widgets: [{ name: 'seed', type: 'number', value: 1 }] },
        { id: 13, title: 'toggle-13', widgets: [{ name: 'enabled', type: 'toggle', value: true }] },
        { id: 14, title: 'number-14', widgets: [{ name: 'cfg', type: 'number', value: 7, options: { min: 1, max: 30 } }] },
        { id: 15, title: 'combo-15', widgets: [{ name: 'sampler', type: 'combo', value: 'euler', options: { values: ['euler', 'dpmpp_2m'] } }] },
        { id: 16, title: 'text-16', widgets: [{ name: 'prompt', type: 'text', value: 'cat' }] },
        // Executable group host (not a real subgraph): paths through it are ambiguous.
        { id: 20, title: 'group-20', isGroupNode: () => true, widgets: [{ name: 'seed', type: 'number', value: 1 }] },
      );
      const handler = new FixHandler(window.app);
      const value = (id, index = 0) => graph.getNodeById(id).widgets[index].value;
      const apply = async (fix) => {
        const button = document.createElement('button');
        await handler.applyFix(fix, button, {});
        return { applied: button.className.includes('applied'), text: button.textContent };
      };

      const out = {};
      out.path = await apply({ node_id: '12:5', widget: 'seed', to: 777 });
      out.path_inner = inner.getNodeById(5).widgets[0].value;
      out.path_root = value(12);
      out.path_undo = handler.undoLastFix();
      out.path_inner_after_undo = inner.getNodeById(5).widgets[0].value;
      out.unresolvable = await apply({ node_id: '99:5', widget: 'seed', to: 9 });
      out.group = await apply({ node_id: '20:1', widget: 'seed', to: 9 });
      out.non_subgraph = await apply({ node_id: '13:5', widget: 'enabled', to: false });
      out.loose_ids = [];
      for (const nodeId of [' 12', '12.0', '0x0c', '012', '12abc', 12.5]) {
        out.loose_ids.push(await apply({ node_id: nodeId, widget: 'seed', to: 4242 }));
      }
      out.root_seed_after_loose = value(12);
      out.group_seed = value(20);

      out.toggle_false = await apply({ node_id: '13', widget: 'enabled', to: 'false' });
      out.toggle_value_1 = value(13);
      out.toggle_true_upper = await apply({ node_id: 13, widget: 'enabled', to: 'TRUE' });
      out.toggle_value_2 = value(13);
      out.toggle_zero = await apply({ node_id: '13', widget: 'enabled', to: 0 });
      out.toggle_value_3 = value(13);
      out.toggle_yes = await apply({ node_id: '13', widget: 'enabled', to: 'yes' });
      out.toggle_value_4 = value(13);

      out.number_partial = await apply({ node_id: '14', widget: 'cfg', to: '12abc' });
      out.number_blank = await apply({ node_id: '14', widget: 'cfg', to: ' ' });
      out.number_range = await apply({ node_id: '14', widget: 'cfg', to: '1e3' });
      out.number_value_rejected = value(14);
      out.number_ok = await apply({ node_id: '14', widget: 'cfg', to: '8.5' });
      out.number_value_ok = value(14);

      out.combo_bad = await apply({ node_id: '15', widget: 'sampler', to: 'evil' });
      out.combo_value_rejected = value(15);
      out.combo_ok = await apply({ node_id: '15', widget: 'sampler', to: 'dpmpp_2m' });
      out.combo_value_ok = value(15);

      out.text_long = await apply({ node_id: '16', widget: 'prompt', to: 'x'.repeat(5000) });
      out.text_value_rejected = value(16);
      out.text_ok = await apply({ node_id: '16', widget: 'prompt', to: 'dog' });
      out.text_value_ok = value(16);
      out.text_undo = handler.undoLastFix();
      out.text_value_after_undo = value(16);
      out.dirty = dirty;
      return out;
    });

    // Path ids mutate only the concrete inner node; undo restores it.
    expect.soft(result.path.applied).toBe(true);
    expect.soft(result.path_inner).toBe(777);
    expect.soft(result.path_root).toBe(1);
    expect.soft(result.path_undo).toBe(true);
    expect.soft(result.path_inner_after_undo).toBe(1);
    for (const key of ['unresolvable', 'group', 'non_subgraph']) {
      expect.soft(result[key].applied, key).toBe(false);
      expect.soft(result[key].text.length, key).toBeGreaterThan(1);
    }
    for (const outcome of result.loose_ids) expect.soft(outcome.applied).toBe(false);
    expect.soft(result.root_seed_after_loose).toBe(1);
    expect.soft(result.group_seed).toBe(1);

    // Toggles: only booleans, "true"/"false" and 1/0.
    expect.soft(result.toggle_false.applied).toBe(true);
    expect.soft(result.toggle_value_1).toBe(false);
    expect.soft(result.toggle_value_2).toBe(true);
    expect.soft(result.toggle_value_3).toBe(false);
    expect.soft(result.toggle_yes.applied).toBe(false);
    expect.soft(result.toggle_value_4).toBe(false);

    // Numbers: no partial parses, no blanks, range enforced.
    for (const key of ['number_partial', 'number_blank', 'number_range']) {
      expect.soft(result[key].applied, key).toBe(false);
      expect.soft(result[key].text.length, key).toBeGreaterThan(1);
    }
    expect.soft(result.number_value_rejected).toBe(7);
    expect.soft(result.number_ok.applied).toBe(true);
    expect.soft(result.number_value_ok).toBe(8.5);

    // Combos: membership only. Text: bounded length.
    expect.soft(result.combo_bad.applied).toBe(false);
    expect.soft(result.combo_value_rejected).toBe('euler');
    expect.soft(result.combo_value_ok).toBe('dpmpp_2m');
    expect.soft(result.text_long.applied).toBe(false);
    expect.soft(result.text_value_rejected).toBe('cat');
    expect.soft(result.text_value_ok).toBe('dog');
    expect.soft(result.text_undo).toBe(true);
    expect.soft(result.text_value_after_undo).toBe('cat');
    expect.soft(result.dirty).toBeGreaterThan(0);
  });
});
