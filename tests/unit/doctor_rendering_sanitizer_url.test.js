import { describe, expect, it } from 'vitest';
import { judgeSanitizerUrl } from '../../web/doctor_rendering.js';

// The URL judge is DOM-free on purpose so the scheme rules can be pinned without a browser. The DOM
// side (element/attribute allowlist, real clicks) is covered by tests/e2e/specs/chat-sanitizer.spec.js.
describe('judgeSanitizerUrl', () => {
  it('keeps absolute http(s) links and returns the parser canonical form', () => {
    expect(judgeSanitizerUrl('https://example.com/ok?q=1#frag', 'a')).toBe('https://example.com/ok?q=1#frag');
    expect(judgeSanitizerUrl('HTTP://EXAMPLE.com', 'a')).toBe('http://example.com/');
    expect(judgeSanitizerUrl('  https://exa\tmple.com/a\nb  ', 'a')).toBe('https://example.com/ab');
  });

  it('allows mailto for links only', () => {
    expect(judgeSanitizerUrl('mailto:someone@example.com', 'a')).toBe('mailto:someone@example.com');
    expect(judgeSanitizerUrl('mailto:someone@example.com', 'img')).toBeNull();
  });

  it('keeps bare fragment links for anchors only', () => {
    expect(judgeSanitizerUrl('#section-1', 'a')).toBe('#section-1');
    expect(judgeSanitizerUrl(' #section-1 ', 'a')).toBe('#section-1');
    expect(judgeSanitizerUrl('#', 'a')).toBe('#');
    expect(judgeSanitizerUrl('#section-1', 'img')).toBeNull();
    expect(judgeSanitizerUrl('#"onclick=1', 'a')).toBeNull();
  });

  it('rejects every script-capable scheme however it is disguised', () => {
    const hostile = [
      'javascript:alert(1)',
      'JaVaScRiPt:alert(1)',
      'java\tscript:alert(1)',
      'java\nscript:alert(1)',
      'java\rscript:alert(1)',
      '   javascript:alert(1)',
      '\u0001javascript:alert(1)',
      '\u0000javascript:alert(1)',
      'java\u0000script:alert(1)',
      'jav&#x61;script:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',
      'vbscript:msgbox(1)',
      'blob:https://example.com/00000000-0000-0000-0000-000000000000',
      'file:///etc/passwd',
      'ftp://example.com/x',
      'ws://example.com/x',
    ];
    for (const value of hostile) {
      expect(judgeSanitizerUrl(value, 'a'), `a: ${JSON.stringify(value)}`).toBeNull();
      expect(judgeSanitizerUrl(value, 'img'), `img: ${JSON.stringify(value)}`).toBeNull();
    }
  });

  it('rejects relative, protocol-relative and host-less values', () => {
    for (const value of ['/api/x', 'relative/path', '//canary.invalid/x', './x', '?q=1', 'https:///', 'https:', '']) {
      expect(judgeSanitizerUrl(value, 'a'), JSON.stringify(value)).toBeNull();
      expect(judgeSanitizerUrl(value, 'img'), JSON.stringify(value)).toBeNull();
    }
  });

  it('rejects credential-bearing URLs', () => {
    expect(judgeSanitizerUrl('https://user:pass@example.com/', 'a')).toBeNull();  // pragma: allowlist secret
    expect(judgeSanitizerUrl('https://user@example.com/', 'img')).toBeNull();
  });

  it('rejects non-strings and oversized values without throwing', () => {
    for (const value of [null, undefined, 42, {}, [], true]) {
      expect(judgeSanitizerUrl(value, 'a')).toBeNull();
    }
    expect(judgeSanitizerUrl(`https://example.com/${'a'.repeat(2100)}`, 'a')).toBeNull();
    expect(judgeSanitizerUrl(`https://example.com/${'a'.repeat(2000)}`, 'a')).toMatch(/^https:\/\/example\.com\/a+$/);
  });

  it('allows images only over http(s)', () => {
    expect(judgeSanitizerUrl('https://example.com/a.png', 'img')).toBe('https://example.com/a.png');
    expect(judgeSanitizerUrl('data:image/png;base64,AAAA', 'img')).toBeNull();
  });
});
