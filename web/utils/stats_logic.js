/**
 * Pure functions for statistics formatting and calculation.
 */

export function formatPatternName(patternId) {
    if (!patternId) return 'Unknown';
    return patternId
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase())
        .replace(/Oom/g, 'OOM')
        .replace(/Cuda/g, 'CUDA')
        .replace(/Vae/g, 'VAE')
        .replace(/Llm/g, 'LLM');
}

export function calculateResolutionPercentages(rates) {
    const { resolved = 0, unresolved = 0, ignored = 0 } = rates || {};
    const total = resolved + unresolved + ignored || 1; // Avoid div by zero

    return {
        resolved: Math.round((resolved / total) * 100),
        unresolved: Math.round((unresolved / total) * 100),
        ignored: Math.round((ignored / total) * 100),
        total,
        counts: { resolved, unresolved, ignored }
    };
}

export function calculateCategoryBreakdown(breakdown, total) {
    if (!breakdown) return [];

    // Sort by count descending
    const categories = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);

    return categories.map(([cat, count]) => ({
        id: cat,
        count,
        percent: Math.round((count / (total || 1)) * 100)
    }));
}

export const CATEGORY_COLORS = {
    'memory': '#f44',
    'model_loading': '#ff9800',
    'workflow': '#2196f3',
    'framework': '#9c27b0',
    'generic': '#607d8b'
};

export function getCategoryColor(cat) {
    return CATEGORY_COLORS[cat] || '#888';
}

export function getScoreColor(score) {
    if (score >= 80) return '#4caf50';
    if (score >= 50) return '#ff9800';
    return '#f44336';
}

/**
 * Coerce a statistics value that arrives in a response into a plain count.
 *
 * IMPORTANT (S34): the vanilla statistics renderer writes counts into `innerHTML`. A count must therefore
 * be a finite, non-negative whole number, or 0. Interpolating the raw value turns a tampered response such
 * as `"<img src=x onerror=...>9"` into a live element. Numeric strings are accepted because older
 * stored files held counts as text; anything else (null, objects, NaN, negatives, booleans) is 0.
 *
 * @param {unknown} value
 * @returns {number}
 */
export function toSafeCount(value) {
    const candidate = typeof value === 'string' && value.trim() !== '' ? Number(value) : value;
    if (typeof candidate !== 'number' || !Number.isFinite(candidate) || candidate < 0) return 0;
    return Math.floor(candidate);
}
