/**
 * Doctor Telemetry Module
 * =======================
 * Frontend event tracking with debounce for ComfyUI-Doctor S3 feature.
 * 
 * Usage:
 *   import { trackEvent, TelemetryAPI } from './doctor_telemetry.js';
 *   trackEvent('feature', 'tab_switch', 'chat');
 * 
 * All events are sent to backend; no local storage on frontend.
 * Backend manages buffer, rate limiting, and persistence.
 */

// ═══════════════════════════════════════════════════════════════════════════
// RATE LIMITER (Best-effort, frontend-side)
// ═══════════════════════════════════════════════════════════════════════════

class FrontendRateLimiter {
    constructor(minIntervalMs = 1000) {
        this.minInterval = minIntervalMs;
        this.lastCall = {};
    }

    /**
     * Check if event is allowed (debounce by category).
     * @param {string} category - Event category
     * @returns {boolean} True if allowed
     */
    allow(category) {
        const now = Date.now();
        const last = this.lastCall[category] || 0;
        if (now - last < this.minInterval) {
            return false;
        }
        this.lastCall[category] = now;
        return true;
    }

    /**
     * Reset rate limiter state.
     */
    reset() {
        this.lastCall = {};
    }
}

const rateLimiter = new FrontendRateLimiter(1000); // 1 second debounce

// ═══════════════════════════════════════════════════════════════════════════
// TELEMETRY API
// ═══════════════════════════════════════════════════════════════════════════

export const TelemetryAPI = {
    /**
     * Get telemetry status.
     * @returns {Promise<{success: boolean, enabled: boolean, stats: object}>}
     */
    async getStatus() {
        try {
            const response = await fetch('/doctor/telemetry/status');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry status error:', error);
            return { success: false, enabled: false, stats: null };
        }
    },

    /**
     * Get buffered events.
     * @returns {Promise<{success: boolean, events: array, count: number}>}
     */
    async getBuffer() {
        try {
            const response = await fetch('/doctor/telemetry/buffer');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry buffer error:', error);
            return { success: false, events: [], count: 0 };
        }
    },

    /**
     * Track a telemetry event.
     * @param {object} data - Event data {category, action, label?, value?}
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async track(data) {
        try {
            const response = await fetch('/doctor/telemetry/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry track error:', error);
            return { success: false, message: error.message };
        }
    },

    /**
     * Clear all buffered events.
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async clear() {
        try {
            const response = await fetch('/doctor/telemetry/clear', {
                method: 'POST',
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry clear error:', error);
            return { success: false, message: error.message };
        }
    },

    /**
     * Export buffer as JSON file download.
     * Triggers browser download.
     */
    async exportToFile() {
        try {
            const response = await fetch('/doctor/telemetry/export');
            const blob = await response.blob();

            // Create download link
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'telemetry_export.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            return { success: true };
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry export error:', error);
            return { success: false, message: error.message };
        }
    },

    /**
     * Toggle telemetry enabled/disabled state.
     * @param {boolean} enabled - New enabled state
     * @returns {Promise<{success: boolean, enabled: boolean, message: string}>}
     */
    async toggle(enabled) {
        try {
            const response = await fetch('/doctor/telemetry/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled }),
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Telemetry toggle error:', error);
            return { success: false, enabled: false, message: error.message };
        }
    },
};

// ═══════════════════════════════════════════════════════════════════════════
// CONVENIENCE FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Track a telemetry event with frontend rate limiting.
 * 
 * @param {string} category - Event category (feature, analysis, resolution, session)
 * @param {string} action - Event action
 * @param {string} [label] - Optional label
 * @param {number} [value] - Optional numeric value
 * @returns {Promise<boolean>} True if event was sent (may still be rejected by backend)
 */
export async function trackEvent(category, action, label = null, value = null) {
    // Frontend rate limiting (best-effort)
    if (!rateLimiter.allow(category)) {
        console.debug('[ComfyUI-Doctor] Telemetry event debounced:', category, action);
        return false;
    }

    const data = { category, action };
    if (label !== null) data.label = label;
    if (value !== null) data.value = value;

    const result = await TelemetryAPI.track(data);
    return result.success;
}

/**
 * Track tab switch event (convenience).
 * @param {string} tabName - Tab name (chat, stats, settings)
 */
export function trackTabSwitch(tabName) {
    trackEvent('feature', 'tab_switch', tabName);
}

/**
 * Track LLM call event (convenience).
 * @param {string} provider - LLM provider name
 */
export function trackLLMCall(provider) {
    trackEvent('analysis', 'llm_called', provider);
}

/**
 * Track pattern match event (convenience).
 * @param {string} patternId - Pattern ID
 */
export function trackPatternMatch(patternId) {
    trackEvent('analysis', 'pattern_matched', patternId);
}

/**
 * Track resolution status change (convenience).
 * @param {string} status - Status (resolved, unresolved, ignored)
 */
export function trackResolution(status) {
    trackEvent('resolution', 'marked', status);
}

/**
 * Track session start.
 */
export function trackSessionStart() {
    trackEvent('session', 'start');
}

/**
 * Track session end.
 */
export function trackSessionEnd() {
    trackEvent('session', 'end');
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export default {
    TelemetryAPI,
    trackEvent,
    trackTabSwitch,
    trackLLMCall,
    trackPatternMatch,
    trackResolution,
    trackSessionStart,
    trackSessionEnd,
};
