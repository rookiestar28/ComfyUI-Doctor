import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

function ensureWritableTempDir() {
  if (process.platform === 'win32') return;
  if (process.env.TMPDIR && process.env.TMP && process.env.TEMP) return;

  const tmpDir = (isWsl() && isDrvFsPath(process.cwd()))
    ? path.join('/tmp', 'comfyui-doctor', 'playwright-tmp')
    : path.join(process.cwd(), '.tmp', 'playwright');
  fs.mkdirSync(tmpDir, { recursive: true });

  process.env.TMPDIR = process.env.TMPDIR || tmpDir;
  process.env.TMP = process.env.TMP || tmpDir;
  process.env.TEMP = process.env.TEMP || tmpDir;
}

function isWsl() {
  return !!process.env.WSL_DISTRO_NAME || fs.existsSync('/proc/sys/fs/binfmt_misc/WSLInterop');
}

function isDrvFsPath(p) {
  return p.startsWith('/mnt/');
}

ensureWritableTempDir();

function ensureWritablePlaywrightOutputDirs() {
  if (process.platform === 'win32') return;
  if (!isWsl()) return;
  if (!isDrvFsPath(process.cwd())) return;

  if (process.env.PW_TEST_OUTPUT_DIR && process.env.PW_HTML_REPORT_DIR) return;

  const baseDir = path.join(os.tmpdir(), 'comfyui-doctor', 'playwright');
  const testOutputDir = path.join(baseDir, 'test-results');
  const htmlReportDir = path.join(baseDir, 'playwright-report');
  fs.mkdirSync(testOutputDir, { recursive: true });
  fs.mkdirSync(htmlReportDir, { recursive: true });

  process.env.PW_TEST_OUTPUT_DIR = process.env.PW_TEST_OUTPUT_DIR || testOutputDir;
  process.env.PW_HTML_REPORT_DIR = process.env.PW_HTML_REPORT_DIR || htmlReportDir;
}

ensureWritablePlaywrightOutputDirs();

const args = ['test', ...process.argv.slice(2)];
const result = spawnSync('playwright', args, {
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
});

process.exit(result.status ?? 1);
