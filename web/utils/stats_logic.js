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
