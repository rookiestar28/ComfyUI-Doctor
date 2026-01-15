/**
 * Island Registry
 * ===============
 * Centralized registry for Preact islands with standardized mount/unmount/fallback contract.
 * Provides consistent error handling and fallback behavior across all islands.
 *
 * @module island_registry
 */

import { isPreactEnabled } from './preact-loader.js';

// Default timeout for island render (prevents hangs when CDN/vendor loads stall)
const DEFAULT_RENDER_TIMEOUT_MS = 8000;

function getRenderTimeoutMs() {
    const v = Number(globalThis?.__doctorIslandRenderTimeoutMs);
    if (Number.isFinite(v) && v > 0) return v;
    return DEFAULT_RENDER_TIMEOUT_MS;
}

async function withTimeout(promise, timeoutMs, timeoutMessage) {
    let timeoutId;
    const timeout = new Promise((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
    });
    try {
        return await Promise.race([promise, timeout]);
    } finally {
        clearTimeout(timeoutId);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// TYPES (JSDoc)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * @typedef {Object} IslandConfig
 * @property {string} id - Unique island identifier
 * @property {() => boolean} isEnabled - Returns true if island should render
 * @property {(container: HTMLElement, props: Object) => Promise<void>} render - Mount the Preact island
 * @property {(container: HTMLElement) => void} unmount - Cleanup the island
 * @property {(container: HTMLElement, error?: Error) => void} fallbackRender - Render vanilla fallback UI
 * @property {(error: Error) => void} [onError] - Optional error handler
 */

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

/** @type {Map<string, IslandConfig>} */
const registry = new Map();

/** @type {Map<string, HTMLElement>} */
const mountedContainers = new Map();

/** @type {Array<{id: string, error: Error, timestamp: number}>} */
const islandErrors = [];

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Register an island configuration.
 * @param {IslandConfig} config - Island configuration
 */
export function register(config) {
    if (!config.id) {
        throw new Error('[IslandRegistry] Config must have an id');
    }
    if (registry.has(config.id)) {
        console.warn(`[IslandRegistry] Overwriting existing config for "${config.id}"`);
    }

    // Validate required methods
    const required = ['isEnabled', 'render', 'unmount', 'fallbackRender'];
    for (const method of required) {
        if (typeof config[method] !== 'function') {
            throw new Error(`[IslandRegistry] Config "${config.id}" missing required method: ${method}`);
        }
    }

    registry.set(config.id, config);
    console.log(`[IslandRegistry] ✅ Registered island: ${config.id}`);
}

/**
 * Mount an island by id.
 * Handles Preact enable check, error boundary, and fallback.
 *
 * @param {string} id - Island id
 * @param {HTMLElement} container - DOM container to mount into
 * @param {Object} [props={}] - Props to pass to island
 * @returns {Promise<boolean>} - True if Preact island mounted, false if fallback used
 */
export async function mount(id, container, props = {}) {
    const config = registry.get(id);
    if (!config) {
        console.error(`[IslandRegistry] ❌ Unknown island: ${id}`);
        return false;
    }

    // Check if island is enabled
    if (!config.isEnabled()) {
        console.log(`[IslandRegistry] Island "${id}" disabled, using fallback`);
        config.fallbackRender(container, null);
        return false;
    }

    // Check if Preact is globally enabled
    if (!isPreactEnabled()) {
        console.log(`[IslandRegistry] Preact disabled, using fallback for "${id}"`);
        config.fallbackRender(container, null);
        return false;
    }

    // Try to render with error boundary
    try {
        const timeoutMs = getRenderTimeoutMs();
        await withTimeout(
            config.render(container, props),
            timeoutMs,
            `[IslandRegistry] Island "${id}" render timeout after ${timeoutMs}ms`
        );
        mountedContainers.set(id, container);
        console.log(`[IslandRegistry] ✅ ${id} mounted`);
        return true;
    } catch (error) {
        // Record error
        recordError(id, error);

        // Notify via callback if provided
        if (config.onError) {
            try {
                config.onError(error);
            } catch (e) {
                console.error(`[IslandRegistry] onError callback threw:`, e);
            }
        }

        // Fallback to vanilla
        console.warn(`[IslandRegistry] ⚠️ ${id} render failed, using fallback:`, error.message);
        try {
            config.fallbackRender(container, error);
        } catch (fallbackError) {
            console.error(`[IslandRegistry] ❌ Fallback also failed for "${id}":`, fallbackError);
        }
        return false;
    }
}

/**
 * Unmount an island by id.
 * @param {string} id - Island id
 */
export function unmount(id) {
    const config = registry.get(id);
    const container = mountedContainers.get(id);

    if (config && container) {
        try {
            config.unmount(container);
            mountedContainers.delete(id);
            console.log(`[IslandRegistry] ✅ ${id} unmounted`);
        } catch (error) {
            console.error(`[IslandRegistry] ❌ Error unmounting "${id}":`, error);
        }
    }
}

/**
 * Get an island config by id.
 * @param {string} id - Island id
 * @returns {IslandConfig|undefined}
 */
export function getConfig(id) {
    return registry.get(id);
}

/**
 * Check if an island is registered.
 * @param {string} id - Island id
 * @returns {boolean}
 */
export function isRegistered(id) {
    return registry.has(id);
}

/**
 * Get all recorded island errors.
 * @returns {Array<{id: string, error: Error, timestamp: number}>}
 */
export function getErrors() {
    return [...islandErrors];
}

/**
 * Clear all recorded errors.
 */
export function clearErrors() {
    islandErrors.length = 0;
}

// INTERNAL FUNCTIONS (exported for testing)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Record an island error for debugging/reporting.
 * Exported for testing - allows tests to verify error recording.
 * @param {string} id - Island id
 * @param {Error} error - The error
 */
export function recordError(id, error) {
    islandErrors.push({
        id,
        error,
        timestamp: Date.now()
    });

    // Keep last 50 errors max
    if (islandErrors.length > 50) {
        islandErrors.shift();
    }

    console.error(`[IslandRegistry] ❌ Error in "${id}":`, error);
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS FOR TESTING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Reset the registry (for testing only).
 */
export function _resetRegistry() {
    registry.clear();
    mountedContainers.clear();
    islandErrors.length = 0;
}
