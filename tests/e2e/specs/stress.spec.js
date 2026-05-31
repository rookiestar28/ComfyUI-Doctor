const { test, expect } = require('@playwright/test');


const BACKEND_URL = process.env.PW_BACKEND_URL || `http://127.0.0.1:${process.env.PW_WEB_SERVER_PORT || 3000}`;
const EVENT_COUNT = 40;


async function setTelemetryEnabled(request, enabled) {
  const response = await request.post(`${BACKEND_URL}/doctor/telemetry/toggle`, {
    data: { enabled },
  });
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.enabled).toBe(enabled);
}


async function clearTelemetry(request) {
  const response = await request.post(`${BACKEND_URL}/doctor/telemetry/clear`, {
    data: {},
  });
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.success).toBe(true);
}


async function getTelemetryBuffer(request) {
  const response = await request.get(`${BACKEND_URL}/doctor/telemetry/buffer`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}


test.describe('@stress telemetry harness backend', () => {
  test.beforeEach(async ({ request }) => {
    await setTelemetryEnabled(request, false);
    await clearTelemetry(request);
  });

  test.afterEach(async ({ request }) => {
    await setTelemetryEnabled(request, false);
    await clearTelemetry(request);
  });

  test('preserves buffer consistency under concurrent tracking', async ({ request }) => {
    await setTelemetryEnabled(request, true);

    const responses = await Promise.all(
      Array.from({ length: EVENT_COUNT }, (_, index) => request.post(`${BACKEND_URL}/doctor/telemetry/track`, {
        data: {
          category: 'feature',
          action: 'tab_switch',
          label: ['chat', 'stats', 'settings'][index % 3],
          value: index,
        },
      }))
    );

    for (const response of responses) {
      expect(response.ok()).toBeTruthy();
      const body = await response.json();
      expect(body.success).toBe(true);
    }

    const buffer = await getTelemetryBuffer(request);
    expect(buffer.count).toBe(EVENT_COUNT);
    expect(buffer.events).toHaveLength(EVENT_COUNT);
    expect(new Set(buffer.events.map(event => event.event_id)).size).toBe(EVENT_COUNT);
  });

  test('keeps deterministic state across repeated toggle and clear cycles', async ({ request }) => {
    for (let i = 0; i < 5; i += 1) {
      await setTelemetryEnabled(request, true);
      const trackResponse = await request.post(`${BACKEND_URL}/doctor/telemetry/track`, {
        data: { category: 'session', action: 'start', value: i },
      });
      expect(trackResponse.ok()).toBeTruthy();
      expect((await trackResponse.json()).success).toBe(true);

      let buffer = await getTelemetryBuffer(request);
      expect(buffer.count).toBe(1);

      await clearTelemetry(request);
      buffer = await getTelemetryBuffer(request);
      expect(buffer.count).toBe(0);

      await setTelemetryEnabled(request, false);
      const disabledResponse = await request.post(`${BACKEND_URL}/doctor/telemetry/track`, {
        data: { category: 'session', action: 'start' },
      });
      expect((await disabledResponse.json()).success).toBe(false);
      buffer = await getTelemetryBuffer(request);
      expect(buffer.count).toBe(0);
    }
  });

  test('rejects oversized payload bursts without polluting the buffer', async ({ request }) => {
    await setTelemetryEnabled(request, true);

    const responses = await Promise.all(
      Array.from({ length: 8 }, () => request.post(`${BACKEND_URL}/doctor/telemetry/track`, {
        data: {
          category: 'feature',
          action: 'tab_switch',
          label: 'x'.repeat(2000),
        },
      }))
    );

    for (const response of responses) {
      expect(response.status()).toBe(413);
    }

    const buffer = await getTelemetryBuffer(request);
    expect(buffer.count).toBe(0);
    expect(buffer.events).toHaveLength(0);
  });
});
