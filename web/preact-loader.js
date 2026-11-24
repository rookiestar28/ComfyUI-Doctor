/**
 * Preact Loader Utility
 * =====================
 * Provides a centralized, single-instance loader for Preact and related libraries.
 * Ensures consistent loading from the shipped local vendor files only (there is no remote fallback).
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
 * Checks both the hardcoded flag and localStorage override.
 * @returns {boolean} True if Preact is enabled
 */
export function isPreactEnabled() {
    // Check localStorage override (user can disable via developer tools)
    if (localStorage.getItem('doctor_preact_disabled') === 'true') {
        return false;
    }
    return PREACT_ENABLED;
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
        // Load the shipped local vendor files; a failure rejects and the island registry renders the vanilla UI.
        const results = await Promise.allSettled([
            tryImport(VENDOR_PATHS.preact, 'Preact'),
            tryImport(VENDOR_PATHS.preactHooks, 'Preact Hooks'),
            tryImport(VENDOR_PATHS.signals, 'Preact Signals'),
            tryImport(VENDOR_PATHS.htm, 'HTM')
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
 * Import one module from its shipped local vendor path.
 *
 * IMPORTANT: there is deliberately no remote (CDN) fallback. A fallback would load unpinned third-party code
 * without any integrity check into the ComfyUI page origin whenever a local file is missing or blocked, which
 * is a remote code execution path for a rare failure. A failed import rejects instead, and the island registry
 * degrades to the vanilla UI (covered by the "No Remote Module Load" case in tests/e2e/specs/preact-loader.spec.js
 * and tests/test_s33_no_remote_module_load.py).
 */
async function tryImport(localPath, name) {
    try {
        const module = await import(localPath);
        console.log(`[Preact-Loader] ✅ ${name} loaded from local vendor`);
        return module;
    } catch (localError) {
        console.error(`[Preact-Loader] ❌ ${name} local vendor load failed:`, localError.message);
        throw new Error(`${name}: local vendor file failed to load (${localError.message})`);
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
