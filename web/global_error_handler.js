/**
 * Global Error Handler
 * ====================
 * Captures uncaught exceptions and promise rejections from Doctor code.
 * Uses addEventListener (NOT assignment) to avoid breaking other extensions.
 *
 * R5: Frontend Error Boundaries - Phase 1: Console logging only (no telemetry)
 * @module global_error_handler
 */

import { sanitizeErrorData } from './privacy_utils.js';
// NO telemetry imports in Phase 1

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const DEDUP_WINDOW_MS = 5000;
const MAX_CACHE_ENTRIES = 200;

// Deduplication cache: hash -> { count, lastSeen, errorId }
const errorCache = new Map();

// ═══════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Generate a hash for deduplication.
 */
function hashError(message, source, lineno, colno) {
    return `${message}:${source}:${lineno}:${colno}`;
}

/**
 * Check if error is a duplicate within the dedup window.
 */
function isDuplicate(hash) {
    const now = Date.now();
    const cached = errorCache.get(hash);

    if (cached && (now - cached.lastSeen < DEDUP_WINDOW_MS)) {
        cached.count++;
        cached.lastSeen = now;
        return true;
    }

    return false;
}

/**
 * Add error to cache with LRU-style eviction.
 */
function addToCache(hash, errorId) {
    // Evict oldest entries if cache is full
    if (errorCache.size >= MAX_CACHE_ENTRIES) {
        let oldestHash = null;
        let oldestTime = Infinity;
        for (const [h, data] of errorCache.entries()) {
            if (data.lastSeen < oldestTime) {
                oldestTime = data.lastSeen;
                oldestHash = h;
            }
        }
        if (oldestHash) {
            errorCache.delete(oldestHash);
        }
    }

    errorCache.set(hash, { count: 1, lastSeen: Date.now(), errorId });
}

/**
 * Generate a unique error ID.
 */
function generateErrorId() {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 11);
    return `err-${timestamp}-${random}`;
}

/**
 * Check if error originates from Doctor code.
 * Filters out ComfyUI core and other extension errors to reduce noise.
 */
function isDoctorError(filename, stack) {
    if (!filename && !stack) return false;

    // Check filename for Doctor resources
    const doctorPatterns = [
        '/doctor',           // /extensions/ComfyUI-Doctor/...
        'doctor_',           // doctor_*.js files
        'ErrorBoundary',     // ErrorBoundary.js
        'chat-island',       // island files
        'statistics-island',
        'privacy_utils',
        'global_error_handler'
    ];

    const fullTrace = `${filename || ''} ${stack || ''}`;

    return doctorPatterns.some(pattern =>
        fullTrace.toLowerCase().includes(pattern.toLowerCase())
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Install global error handlers.
 * Uses addEventListener to avoid breaking other extensions.
 * Idempotent - safe to call multiple times.
 */
export function installGlobalErrorHandlers() {
    // Idempotent guard: prevent duplicate installation
    if (window.__doctorGlobalErrorHandlersInstalled) {
        console.warn('[ComfyUI-Doctor] Global error handlers already installed, skipping');
        return;
    }

    // 1. Uncaught exceptions
    window.addEventListener('error', (event) => {
        const { message, filename, lineno, colno, error } = event;

        // Filter: Only log Doctor errors (avoid ComfyUI/other extension noise)
        if (!isDoctorError(filename, error?.stack)) {
            return; // Not a Doctor error, ignore
        }

        const hash = hashError(message, filename, lineno, colno);

        if (isDuplicate(hash)) {
            return; // Duplicate, ignore
        }

        const errorId = generateErrorId();
        addToCache(hash, errorId);

        // Sanitize before logging
        const sanitized = sanitizeErrorData({
            message,
            source: filename,
            lineno,
            colno,
            stack: error?.stack
        });

        console.error(`[ComfyUI-Doctor] Uncaught exception (${errorId}):`, sanitized);

        // Phase 1: NO telemetry (console only)
        // Phase 2: Add reportToTelemetry(sanitized) if enabled
    });

    // 2. Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
        const message = event.reason?.message || String(event.reason);
        const stack = event.reason?.stack || '';

        // Filter: Only log Doctor errors
        if (!isDoctorError('', stack)) {
            return;
        }

        const hash = hashError(message, 'promise', 0, 0);

        if (isDuplicate(hash)) {
            return;
        }

        const errorId = generateErrorId();
        addToCache(hash, errorId);

        const sanitized = sanitizeErrorData({ message, stack });

        console.error(`[ComfyUI-Doctor] Unhandled rejection (${errorId}):`, sanitized);

        // Phase 1: NO telemetry
    });

    // Mark as installed
    window.__doctorGlobalErrorHandlersInstalled = true;

    console.log('[ComfyUI-Doctor] Global error handlers installed');
}

/**
 * Clear the error cache (for testing).
 */
export function _clearErrorCache() {
    errorCache.clear();
}

/**
 * Reset handlers (for testing).
 */
export function _resetHandlers() {
    window.__doctorGlobalErrorHandlersInstalled = false;
}
