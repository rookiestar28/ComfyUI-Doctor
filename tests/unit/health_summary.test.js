import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import {
    DYNAMIC_VRAM_RECOMMENDATION,
    formatDynamicVramAdvisory,
    formatHealthSummary,
} from '../../web/utils/health_summary.js';


const activeAdvisory = {
    active: true,
    kind: 'dynamic_vram_fallback',
    severity: 'warning',
    fatal: false,
    reasons: ['pytorch_threshold'],
    title: 'DynamicVRAM fallback',
    message: 'Automatic DynamicVRAM fell back to legacy ModelPatcher.',
    recommendation: DYNAMIC_VRAM_RECOMMENDATION,
    repeat_count: 1,
    first_seen: '2026-08-19T00:00:00Z',
    last_seen: '2026-08-19T00:00:00Z',
};


describe('DynamicVRAM health advisory formatting', () => {
    it('keeps the base, feature requirement, and upstream recommendation distinct', () => {
        expect(DYNAMIC_VRAM_RECOMMENDATION).toBe(
            'Automatic DynamicVRAM requires PyTorch 2.8 or later and working comfy-aimdo; ComfyUI recommends PyTorch 2.12 or later for DynamicVRAM; base ComfyUI support remains PyTorch 2.7.',
        );
    });

    it('returns only the fixed recommendation for the exact active projection', () => {
        expect(formatDynamicVramAdvisory(activeAdvisory)).toBe(DYNAMIC_VRAM_RECOMMENDATION);
    });

    it.each([
        null,
        undefined,
        {},
        { active: false },
        { ...activeAdvisory, kind: 'unknown' },
        { ...activeAdvisory, severity: 'critical' },
        { ...activeAdvisory, fatal: true },
        { ...activeAdvisory, recommendation: 'untrusted host text' },
        { ...activeAdvisory, reasons: ['unknown_reason'] },
    ])('fails closed for inactive, malformed, or unknown projections', (value) => {
        expect(formatDynamicVramAdvisory(value)).toBe('');
    });

    it('preserves the legacy health summary when the additive field is absent', () => {
        const health = {
            logger: { dropped_messages: 2 },
            ssrf: { blocked_total: 1 },
            last_analysis: { pipeline_status: 'ok' },
        };

        expect(formatHealthSummary(health, 'fallback')).toBe(
            'Health: pipeline_status=ok, ssrf_blocked=1, dropped_logs=2',
        );
    });

    it('appends the same fixed advisory text for both frontend consumers', () => {
        const health = {
            logger: { dropped_messages: 2 },
            ssrf: { blocked_total: 1 },
            last_analysis: { pipeline_status: 'ok' },
            dynamic_vram_advisory: activeAdvisory,
        };

        const summary = formatHealthSummary(health, 'fallback');
        expect(summary).toContain('pipeline_status=ok');
        expect(summary).toContain(DYNAMIC_VRAM_RECOMMENDATION);
        expect(summary).not.toContain('Unsupported Pytorch detected');
        expect(summary).not.toContain('No working comfy-aimdo install detected');
        expect(summary).not.toContain('<');
    });

    it('keeps error and empty-state behavior backward compatible', () => {
        expect(formatHealthSummary({ error: 'Failed' }, 'fallback')).toBe('Health: Failed');
        expect(formatHealthSummary(null, 'fallback')).toBe('fallback');
    });

    it('is the shared formatter used by both Preact and legacy health paths', () => {
        const preactSource = readFileSync(new URL('../../web/statistics-island.js', import.meta.url), 'utf8');
        const legacySource = readFileSync(new URL('../../web/tabs/stats_tab.js', import.meta.url), 'utf8');

        expect(preactSource).toContain("import { formatHealthSummary } from './utils/health_summary.js';");
        expect(legacySource).toContain("import { formatHealthSummary } from \"../utils/health_summary.js\";");
        expect(preactSource).toMatch(/formatHealthSummary\(\s*healthData,/);
        expect(legacySource).toContain('formatHealthSummary(healthRes.health)');
    });
});
