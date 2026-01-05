/**
 * Preact Loader Utility
 * =====================
 * Provides a centralized, single-instance loader for Preact and related libraries.
 * Ensures consistent loading from local vendor files with CDN fallback.
 *
 * Usage:
 *   import { loadPreact, isPreactEnabled } from './utils/preact-loader.js';
 *
 *   if (isPreactEnabled()) {
 *       const { h, render } = await loadPreact();
 *       // ... use Preact
 *   }
 *
 * @module preact-loader
 */

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

// Feature flag to enable/disable Preact islands
// Set to 'false' to completely disable all Preact functionality and use Vanilla JS fallbacks
const PREACT_ENABLED = true;

// Library versions for consistency
const VERSIONS = {
    preact: '10.26.5',
    signals: '1.3.1',
    htm: '3.1.1'
};

// Local vendor paths (relative to web/)
const VENDOR_PATHS = {
    preact: './lib/preact.module.js',
    preactHooks: './lib/preact-hooks.module.js',
    signals: './lib/preact-signals.module.js',
    htm: './lib/htm.module.js'
};

// CDN fallback paths (used if local files fail)
const CDN_PATHS = {
    preact: `https://esm.sh/preact@${VERSIONS.preact}`,
    preactHooks: `https://esm.sh/preact@${VERSIONS.preact}/hooks`,
    signals: `https://esm.sh/@preact/signals@${VERSIONS.signals}`,
    htm: `https://esm.sh/htm@${VERSIONS.htm}`
};

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

// Cached loaded modules (single instance pattern)
let cachedPreact = null;
let cachedHooks = null;
let cachedSignals = null;
let cachedHtm = null;
let loadPromise = null;
let loadError = null;

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Check if Preact islands are enabled.
 * @returns {boolean} True if Preact is enabled
 */
export function isPreactEnabled() {
    return PREACT_ENABLED;
}

/**
 * Check if Preact has been successfully loaded.
 * @returns {boolean} True if Preact is loaded and ready
 */
export function isPreactLoaded() {
    return cachedPreact !== null && loadError === null;
}

/**
 * Get the last load error, if any.
 * @returns {Error|null} The error object or null
 */
export function getLoadError() {
    return loadError;
}

/**
 * Load Preact and related libraries.
 * Uses single-instance pattern to avoid multiple Preact instances.
 *
 * @returns {Promise<{h, render, Fragment, Component, createContext, useState, useEffect, useRef, useCallback, useMemo, signal, computed, effect, html}>}
 */
export async function loadPreact() {
    // Return cached result if already loaded
    if (cachedPreact && cachedHooks && cachedSignals && cachedHtm) {
        return buildExports();
    }

    // Return existing promise if load is in progress
    if (loadPromise) {
        return loadPromise;
    }

    // Start loading
    loadPromise = doLoad();
    return loadPromise;
}

// ═══════════════════════════════════════════════════════════════════════════
// INTERNAL FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Perform the actual loading of libraries.
 */
async function doLoad() {
    loadError = null;

    try {
        // Try local vendor files first
        const results = await Promise.allSettled([
            tryImport(VENDOR_PATHS.preact, CDN_PATHS.preact, 'Preact'),
            tryImport(VENDOR_PATHS.preactHooks, CDN_PATHS.preactHooks, 'Preact Hooks'),
            tryImport(VENDOR_PATHS.signals, CDN_PATHS.signals, 'Preact Signals'),
            tryImport(VENDOR_PATHS.htm, CDN_PATHS.htm, 'HTM')
        ]);

        // Check for failures
        const failures = results.filter(r => r.status === 'rejected');
        if (failures.length > 0) {
            const errorMessages = failures.map(f => f.reason?.message || 'Unknown error');
            throw new Error(`Failed to load Preact libraries: ${errorMessages.join(', ')}`);
        }

        // Extract successful results
        [cachedPreact, cachedHooks, cachedSignals, cachedHtm] = results.map(r => r.value);

        console.log('[Preact-Loader] ✅ All libraries loaded successfully');
        console.log('[Preact-Loader] Versions:', VERSIONS);

        return buildExports();
    } catch (error) {
        loadError = error;
        loadPromise = null; // Allow retry
        console.error('[Preact-Loader] ❌ Failed to load:', error);
        throw error;
    }
}

/**
 * Try importing a module from local path, fallback to CDN.
 */
async function tryImport(localPath, cdnPath, name) {
    try {
        // Try local first
        const module = await import(localPath);
        console.log(`[Preact-Loader] ✅ ${name} loaded from local vendor`);
        return module;
    } catch (localError) {
        console.warn(`[Preact-Loader] ⚠️ ${name} local load failed, trying CDN...`, localError.message);

        try {
            const module = await import(cdnPath);
            console.log(`[Preact-Loader] ✅ ${name} loaded from CDN`);
            return module;
        } catch (cdnError) {
            console.error(`[Preact-Loader] ❌ ${name} CDN load also failed:`, cdnError.message);
            throw new Error(`${name}: Local failed (${localError.message}), CDN failed (${cdnError.message})`);
        }
    }
}

/**
 * Build the unified exports object.
 */
function buildExports() {
    // Configure HTM to use Preact's h function
    // HTM exports default function, not named 'htm'
    const htmFn = cachedHtm.default || cachedHtm.htm || cachedHtm;
    const html = htmFn.bind(cachedPreact.h);

    return {
        // Core Preact
        h: cachedPreact.h,
        render: cachedPreact.render,
        Fragment: cachedPreact.Fragment,
        Component: cachedPreact.Component,
        createContext: cachedPreact.createContext,

        // Hooks
        useState: cachedHooks.useState,
        useEffect: cachedHooks.useEffect,
        useRef: cachedHooks.useRef,
        useCallback: cachedHooks.useCallback,
        useMemo: cachedHooks.useMemo,
        useContext: cachedHooks.useContext,
        useReducer: cachedHooks.useReducer,

        // Signals
        signal: cachedSignals.signal,
        computed: cachedSignals.computed,
        effect: cachedSignals.effect,
        batch: cachedSignals.batch,

        // HTM (tagged template literal for JSX-like syntax)
        html
    };
}

/**
 * Reset the loader state (for testing or recovery).
 */
export function resetLoader() {
    cachedPreact = null;
    cachedHooks = null;
    cachedSignals = null;
    cachedHtm = null;
    loadPromise = null;
    loadError = null;
}
