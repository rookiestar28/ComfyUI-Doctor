#!/usr/bin/env node
import { createServer } from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const port = Number(process.env.PW_WEB_SERVER_PORT) || 3000;
const host = '127.0.0.1';
const rootDir = process.cwd();

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

function handleMockEndpoint(req, res, url) {
  const { pathname, searchParams } = url;
  const method = req.method || 'GET';
  // Root cause note: static http.server generated noisy 404/501 for
  // /doctor/* and /debugger/*, obscuring real regressions in E2E output.

  if (method === 'OPTIONS' && isDoctorPath(pathname)) {
    sendNoContent(res);
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

  if (pathname === '/doctor/telemetry/status' && method === 'GET') {
    sendJson(res, 200, {
      success: true,
      enabled: false,
      stats: { total_events: 0 },
      upload_destination: null,
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

const server = createServer((req, res) => {
  const url = new URL(req.url || '/', `http://${host}:${port}`);
  if (handleMockEndpoint(req, res, url)) {
    return;
  }

  if ((req.method || 'GET') !== 'GET' && (req.method || 'GET') !== 'HEAD') {
    sendJson(res, 405, { success: false, message: 'Method Not Allowed' });
    return;
  }

  serveStatic(req, res, url.pathname);
});

server.listen(port, host, () => {
  console.error(`[e2e-server] serving ${rootDir} at http://${host}:${port}`);
});
