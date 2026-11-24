import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, test } from 'vitest';

// S34 source pins. The tab-initialization error panel in web/doctor.js is only reached when a tab fails to
// initialize, which an E2E run cannot trigger without changing production code. These pins therefore read the
// source: the message must be assigned as text and never be interpolated into the panel's template.
const source = readFileSync(fileURLToPath(new URL('../../web/doctor.js', import.meta.url)), 'utf8');

describe('S34 tab-initialization error panel', () => {
  const marker = source.indexOf('Tab Initialization Error');
  const start = source.lastIndexOf('content.innerHTML = `', marker);
  const end = source.indexOf('`;', marker);

  test('the panel template is found', () => {
    expect(marker).toBeGreaterThan(0);
    expect(start).toBeGreaterThan(0);
    expect(end).toBeGreaterThan(marker);
  });

  test('the panel template has no interpolation at all', () => {
    expect(source.slice(start, end)).not.toContain('${');
  });

  test('the message is assigned as text', () => {
    expect(source).toContain('tabErrorMessage.textContent = String(tabError?.message ?? tabError)');
  });
});
