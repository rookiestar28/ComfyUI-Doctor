export const DYNAMIC_VRAM_RECOMMENDATION =
    'Automatic DynamicVRAM requires PyTorch 2.8 or later and working comfy-aimdo; ComfyUI recommends PyTorch 2.12 or later for DynamicVRAM; base ComfyUI support remains PyTorch 2.7.';

const DYNAMIC_VRAM_REASONS = ['pytorch_threshold', 'comfy_aimdo_unavailable'];
const DYNAMIC_VRAM_TITLE = 'DynamicVRAM fallback';
const DYNAMIC_VRAM_MESSAGE = 'Automatic DynamicVRAM fell back to legacy ModelPatcher.';
const MAX_REPEAT_COUNT = 65535;


function hasValidReasons(reasons) {
    if (!Array.isArray(reasons) || reasons.length < 1 || reasons.length > DYNAMIC_VRAM_REASONS.length) {
        return false;
    }
    const expected = DYNAMIC_VRAM_REASONS.filter((reason) => reasons.includes(reason));
    return expected.length === reasons.length && expected.every((reason, index) => reasons[index] === reason);
}


/** Return fixed safe advisory text only for the exact backend projection. */
export function formatDynamicVramAdvisory(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
    if (value.active !== true || value.kind !== 'dynamic_vram_fallback') return '';
    if (value.severity !== 'warning' || value.fatal !== false) return '';
    if (value.title !== DYNAMIC_VRAM_TITLE || value.message !== DYNAMIC_VRAM_MESSAGE) return '';
    if (value.recommendation !== DYNAMIC_VRAM_RECOMMENDATION) return '';
    if (!hasValidReasons(value.reasons)) return '';
    if (!Number.isInteger(value.repeat_count) || value.repeat_count < 1 || value.repeat_count > MAX_REPEAT_COUNT) return '';
    if (typeof value.first_seen !== 'string' || !value.first_seen.endsWith('Z')) return '';
    if (typeof value.last_seen !== 'string' || !value.last_seen.endsWith('Z')) return '';
    return DYNAMIC_VRAM_RECOMMENDATION;
}


/** Build the shared legacy/Preact Trust & Health text without HTML. */
export function formatHealthSummary(healthData, emptyText = '') {
    if (healthData?.error) return `Health: ${healthData.error}`;
    if (!healthData) return emptyText;

    const pipelineStatus = healthData.last_analysis?.pipeline_status || 'unknown';
    const ssrfBlocked = healthData.ssrf?.blocked_total ?? healthData.ssrf?.blocked ?? 0;
    const droppedLogs = healthData.logger?.dropped_messages ?? 0;
    const summary = `Health: pipeline_status=${pipelineStatus}, ssrf_blocked=${ssrfBlocked}, dropped_logs=${droppedLogs}`;
    const advisoryText = formatDynamicVramAdvisory(healthData.dynamic_vram_advisory);
    return advisoryText ? `${summary}, advisory=${advisoryText}` : summary;
}
