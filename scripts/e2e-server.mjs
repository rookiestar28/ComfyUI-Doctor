#!/usr/bin/env node
import { createServer } from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const port = Number(process.env.PW_WEB_SERVER_PORT) || 3000;
const host = '127.0.0.1';
const rootDir = process.cwd();
const telemetryState = {
  enabled: false,
  events: [],
};

const allowedTelemetryEvents = {
  feature: {
    tab_switch: ['chat', 'stats', 'settings'],
  },
  analysis: {
    pattern_matched: null,
    llm_called: ['openai', 'deepseek', 'anthropic', 'ollama', 'lmstudio', 'gemini', 'groq', 'openrouter', 'xai', 'custom'],
  },
  resolution: {
    marked: ['resolved', 'unresolved', 'ignored'],
  },
  session: {
    start: null,
    end: null,
  },
};

const mimeTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.webm': 'video/webm',
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function sendNoContent(res) {
  res.writeHead(204, {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  });
  res.end();
}

function isDoctorPath(pathname) {
  return pathname.startsWith('/doctor/') || pathname.startsWith('/debugger/');
}

function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', chunk => {
      body += chunk;
      if (body.length > 1024 * 1024) {
        reject(new Error('Request body too large'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

async function readJsonPayload(req) {
  const body = await readRequestBody(req);
  if (!body.trim()) {
    return {};
  }
  return JSON.parse(body);
}

function telemetryStats() {
  return {
    count: telemetryState.events.length,
    oldest: telemetryState.events[0]?.timestamp || null,
    newest: telemetryState.events[telemetryState.events.length - 1]?.timestamp || null,
  };
}

function validateTelemetryEvent(payload) {
  const category = payload?.category;
  const action = payload?.action;
  if (!category || !action) {
    return 'Missing required field: category or action';
  }
  if (!Object.prototype.hasOwnProperty.call(allowedTelemetryEvents, category)) {
    return `Invalid category: ${category}`;
  }
  const actionMap = allowedTelemetryEvents[category];
  if (!Object.prototype.hasOwnProperty.call(actionMap, action)) {
    return `Invalid action: ${action} for category ${category}`;
  }
  const allowedLabels = actionMap[action];
  if (Array.isArray(allowedLabels) && payload.label !== undefined && !allowedLabels.includes(payload.label)) {
    return `Invalid label: ${payload.label}`;
  }
  return '';
}

function telemetryEventFromPayload(payload) {
  const event = {
    schema_version: '1.0',
    event_id: `mock-${Date.now()}-${telemetryState.events.length + 1}`,
    timestamp: new Date().toISOString(),
    category: payload.category,
    action: payload.action,
  };
  if (payload.label !== undefined) {
    event.label = payload.label;
  }
  if (payload.value !== undefined) {
    event.value = payload.value;
  }
  return event;
}

async function handleTelemetryEndpoint(req, res, url) {
  const { pathname } = url;
  const method = req.method || 'GET';

  if (pathname === '/doctor/telemetry/status' && method === 'GET') {
    sendJson(res, 200, {
      success: true,
      enabled: telemetryState.enabled,
      stats: telemetryStats(),
      upload_destination: null,
    });
    return true;
  }

  if (pathname === '/doctor/telemetry/buffer' && method === 'GET') {
    sendJson(res, 200, {
      success: true,
      events: telemetryState.events,
      count: telemetryState.events.length,
    });
    return true;
  }

  if (pathname === '/doctor/telemetry/toggle' && method === 'POST') {
    const payload = await readJsonPayload(req);
    telemetryState.enabled = Boolean(payload.enabled);
    sendJson(res, 200, {
      success: true,
      enabled: telemetryState.enabled,
      message: telemetryState.enabled ? 'Telemetry enabled' : 'Telemetry disabled',
    });
    return true;
  }

  if (pathname === '/doctor/telemetry/clear' && method === 'POST') {
    await readJsonPayload(req).catch(() => ({}));
    telemetryState.events = [];
    sendJson(res, 200, {
      success: true,
      message: 'Buffer cleared',
    });
    return true;
  }

  if (pathname === '/doctor/telemetry/track' && method === 'POST') {
    const origin = req.headers.origin || '';
    const hostHeader = req.headers.host || '';
    if (origin) {
      const originHost = new URL(origin).host;
      if (originHost && hostHeader && originHost !== hostHeader) {
        sendJson(res, 403, {
          success: false,
          error: 'cross_origin_rejected',
          message: 'Cross-origin request rejected',
        });
        return true;
      }
    }

    const contentLength = Number(req.headers['content-length'] || 0);
    if (contentLength > 1024) {
      sendJson(res, 413, {
        success: false,
        error: 'payload_too_large',
        message: 'Payload too large',
      });
      return true;
    }

    const payload = await readJsonPayload(req);
    if (!telemetryState.enabled) {
      sendJson(res, 200, {
        success: false,
        message: 'Telemetry disabled',
      });
      return true;
    }

    const validationError = validateTelemetryEvent(payload);
    if (validationError) {
      sendJson(res, 200, {
        success: false,
        message: validationError,
      });
      return true;
    }

    telemetryState.events.push(telemetryEventFromPayload(payload));
    sendJson(res, 200, {
      success: true,
      message: 'Event recorded',
    });
    return true;
  }

  if (pathname === '/doctor/telemetry/export' && method === 'GET') {
    const body = JSON.stringify(telemetryState.events);
    res.writeHead(200, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
      'Cache-Control': 'no-store',
      'Content-Disposition': 'attachment; filename=telemetry_export.json',
    });
    res.end(body);
    return true;
  }

  return false;
}

async function handleMockEndpoint(req, res, url) {
  const { pathname, searchParams } = url;
  const method = req.method || 'GET';
  // Root cause note: static http.server generated noisy 404/501 for
  // /doctor/* and /debugger/*, obscuring real regressions in E2E output.

  if (method === 'OPTIONS' && isDoctorPath(pathname)) {
    sendNoContent(res);
    return true;
  }

  if (await handleTelemetryEndpoint(req, res, url)) {
    return true;
  }

  if (pathname === '/doctor/health_report' && method === 'GET') {
    sendJson(res, 200, {
      success: true,
      errors: [],
      summary: { total: 0 },
    });
    return true;
  }

  if (pathname === '/doctor/provider_defaults' && method === 'GET') {
    sendJson(res, 200, {
      openai: 'https://api.openai.com/v1',
      deepseek: 'https://api.deepseek.com/v1',
    });
    return true;
  }

  if (pathname === '/doctor/ui_text' && method === 'GET') {
    const lang = searchParams.get('lang') || 'en';
    sendJson(res, 200, { language: lang, text: {} });
    return true;
  }

  if (pathname === '/doctor/list_models' && method === 'POST') {
    sendJson(res, 200, { success: true, models: [] });
    return true;
  }

  if (pathname === '/doctor/statistics' && method === 'GET') {
    sendJson(res, 200, {
      success: true,
      statistics: {
        total_errors: 0,
        pattern_frequency: {},
        category_breakdown: {},
        top_patterns: [],
        resolution_rate: { resolved: 0, unresolved: 0, ignored: 0 },
        trend: { last_24h: 0, last_7d: 0, last_30d: 0 },
      },
    });
    return true;
  }

  if (pathname === '/debugger/last_analysis' && method === 'GET') {
    sendJson(res, 200, {});
    return true;
  }

  if (pathname === '/debugger/set_language' && method === 'POST') {
    sendJson(res, 200, { success: true });
    return true;
  }

  if (isDoctorPath(pathname)) {
    sendJson(res, 200, { success: true, mocked: true, path: pathname });
    return true;
  }

  return false;
}

function resolveFilePath(pathname) {
  const requestedPath = pathname === '/' ? '/tests/e2e/test-harness.html' : pathname;
  const decodedPath = decodeURIComponent(requestedPath);
  const absolutePath = path.normalize(path.join(rootDir, decodedPath));
  const rootPrefix = rootDir.endsWith(path.sep) ? rootDir : `${rootDir}${path.sep}`;
  if (absolutePath !== rootDir && !absolutePath.startsWith(rootPrefix)) {
    return null;
  }
  return absolutePath;
}

function serveStatic(req, res, pathname) {
  const filePath = resolveFilePath(pathname);
  if (!filePath) {
    sendJson(res, 403, { success: false, message: 'Forbidden path' });
    return;
  }

  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      sendJson(res, 404, { success: false, message: 'File not found' });
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';
    res.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': stats.size,
      'Cache-Control': 'no-cache',
    });

    if (req.method === 'HEAD') {
      res.end();
      return;
    }

    const stream = fs.createReadStream(filePath);
    stream.on('error', () => {
      if (!res.headersSent) {
        sendJson(res, 500, { success: false, message: 'Failed to read file' });
      } else {
        res.destroy();
      }
    });
    stream.pipe(res);
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${host}:${port}`);
  try {
    if (await handleMockEndpoint(req, res, url)) {
      return;
    }

    if ((req.method || 'GET') !== 'GET' && (req.method || 'GET') !== 'HEAD') {
      sendJson(res, 405, { success: false, message: 'Method Not Allowed' });
      return;
    }

    serveStatic(req, res, url.pathname);
  } catch (error) {
    sendJson(res, 500, {
      success: false,
      message: error instanceof Error ? error.message : 'Mock server error',
    });
  }
});

server.listen(port, host, () => {
  console.error(`[e2e-server] serving ${rootDir} at http://${host}:${port}`);
});
