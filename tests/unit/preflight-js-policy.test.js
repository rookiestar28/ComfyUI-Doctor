import { describe, expect, test } from 'vitest';

import {
  getUnsupportedNodeVersionMessage,
  isSupportedNodeMajor,
  NODE_POLICY,
  parseNodeMajor,
} from '../../scripts/preflight-js.mjs';

describe('preflight Node policy', () => {
  test('documents Doctor Node support range', () => {
    expect(NODE_POLICY).toEqual({
      minMajor: 18,
      maxMajorExclusive: 26,
      label: 'Node.js >=18 <26',
    });
  });

  test.each([
    ['18.20.8', 18],
    ['v20.19.0', 20],
    ['24.13.1', 24],
    ['25.0.0', 25],
    ['not-a-version', null],
  ])('parses Node major from %s', (version, expectedMajor) => {
    expect(parseNodeMajor(version)).toBe(expectedMajor);
  });

  test.each([18, 20, 24, 25])('accepts Node %s', (major) => {
    expect(isSupportedNodeMajor(major)).toBe(true);
  });

  test.each([16, 17, 26, 27])('rejects Node %s', (major) => {
    expect(isSupportedNodeMajor(major)).toBe(false);
  });

  test.each(['16.20.2', 'v26.0.0', 'not-a-version'])(
    'returns actionable failure text for unsupported version %s',
    (version) => {
      const message = getUnsupportedNodeVersionMessage(version);
      expect(message).toContain('Node.js >=18 <26');
      expect(message).toContain('Node 26+ is blocked until validated');
    },
  );

  test('returns no failure text for supported versions', () => {
    expect(getUnsupportedNodeVersionMessage('24.13.1')).toBeNull();
  });
});
