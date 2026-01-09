import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function ensureWritableTempDir() {
  if (process.platform === 'win32') return;
  if (process.env.TMPDIR && process.env.TMP && process.env.TEMP) return;

  const repoRoot = process.cwd();
  const tmpDir = path.join(repoRoot, '.tmp', 'playwright');
  fs.mkdirSync(tmpDir, { recursive: true });

  process.env.TMPDIR = process.env.TMPDIR || tmpDir;
  process.env.TMP = process.env.TMP || tmpDir;
  process.env.TEMP = process.env.TEMP || tmpDir;
}

ensureWritableTempDir();

const args = ['test', ...process.argv.slice(2)];
const result = spawnSync('playwright', args, {
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
});

process.exit(result.status ?? 1);

