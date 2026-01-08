/**
 * Doctor Actions
 * ===============
 * State mutation actions for doctorContext.
 * Separated from selectors to maintain read-only selector contract.
 *
 * @module doctor_actions
 */

import { doctorContext } from './doctor_state.js';

// ═══════════════════════════════════════════════════════════════════════════
// STATE MUTATIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Refresh settings from app.ui.settings.
 */
export function refreshSettings() {
    doctorContext.refreshSettings?.();
}

/**
 * Add a message to the chat.
 * @param {string} role - 'user' | 'assistant' | 'system'
 * @param {string} content - Message content
 * @param {Object} [metadata] - Optional metadata
 */
export function addMessage(role, content, metadata = {}) {
    return doctorContext.addMessage(role, content, metadata);
}

/**
 * Clear all messages.
 */
export function clearMessages() {
    doctorContext.clearMessages();
}

/**
 * Set processing state.
 * @param {boolean} isProcessing
 */
export function setProcessing(isProcessing) {
    doctorContext.setProcessing(isProcessing);
}

/**
 * Update state directly (use sparingly).
 * @param {Object} updates
 */
export function setState(updates) {
    doctorContext.setState(updates);
}
