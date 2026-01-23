import { describe, it, expect } from 'vitest';
import {
    formatPatternName,
    calculateCategoryBreakdown,
    calculateResolutionPercentages,
    getScoreColor
} from '../../web/utils/stats_logic.js';

describe('Stats Logic - formatPatternName', () => {
    it('should format pattern IDs correctly', () => {
        expect(formatPatternName('oom_error')).toBe('OOM Error');
        expect(formatPatternName('cuda_memory')).toBe('CUDA Memory');
        expect(formatPatternName('vae_decode_fail')).toBe('VAE Decode Fail');
        expect(formatPatternName('llm_load_fail')).toBe('LLM Load Fail');
        expect(formatPatternName('generic_error')).toBe('Generic Error');
    });

    it('should handle empty input', () => {
        expect(formatPatternName(null)).toBe('Unknown');
        expect(formatPatternName('')).toBe('Unknown');
    });
});

describe('Stats Logic - calculateCategoryBreakdown', () => {
    it('should calculate percentages and sort by count descending', () => {
        const breakdown = {
            'memory': 10,
            'workflow': 5,
            'generic': 5
        };
        const total = 20;

        const result = calculateCategoryBreakdown(breakdown, total);

        expect(result).toHaveLength(3);
        // Should be sorted desc
        expect(result[0].id).toBe('memory');
        expect(result[0].percent).toBe(50); // 10/20

        // Handling ties is stable/unspecified for sort, but logic is fine
        expect(result[1].percent).toBe(25);
        expect(result[2].percent).toBe(25);
    });

    it('should handle zero total gracefully', () => {
        const breakdown = { 'memory': 0 };
        const result = calculateCategoryBreakdown(breakdown, 0);
        expect(result[0].percent).toBe(0);
    });

    it('should handle null breakdown', () => {
        expect(calculateCategoryBreakdown(null, 10)).toEqual([]);
    });
});

describe('Stats Logic - calculateResolutionPercentages', () => {
    it('should calculate percentages correctly', () => {
        const rates = { resolved: 50, unresolved: 30, ignored: 20 };
        const res = calculateResolutionPercentages(rates);

        expect(res.resolved).toBe(50);
        expect(res.unresolved).toBe(30);
        expect(res.ignored).toBe(20);
        expect(res.total).toBe(100);
    });

    it('should handle empty/null rates (default to zero)', () => {
        const res = calculateResolutionPercentages(null);
        expect(res.resolved).toBe(0);
        expect(res.unresolved).toBe(0);
        expect(res.ignored).toBe(0);
        expect(res.total).toBe(1); // Avoid div zero protection
    });
});

describe('Stats Logic - getScoreColor', () => {
    it('should return correct colors for thresholds', () => {
        expect(getScoreColor(90)).toBe('#4caf50');
        expect(getScoreColor(80)).toBe('#4caf50');
        expect(getScoreColor(79)).toBe('#ff9800'); // Warning
        expect(getScoreColor(50)).toBe('#ff9800');
        expect(getScoreColor(49)).toBe('#f44336'); // Critical
    });
});
