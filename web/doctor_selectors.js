/**
 * Doctor Selectors
 * ================
 * Thin selector layer over doctorContext for decoupled state access.
 * 
 * Contract:
 * - **Read-only**: No mutations via selectors
 * - **Fixed return shape**: Each selector has consistent return type
 * - **Subscribable**: Subscriptions return unsubscribe functions
 *
 * @module doctor_selectors
 */

import { doctorContext } from './doctor_state.js';
import { app } from '../../../scripts/app.js';

// ═══════════════════════════════════════════════════════════════════════════
// READ-ONLY SELECTORS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get current chat messages.
 * @returns {Array<{id: string, role: string, content: string, timestamp: number}>}
 */
export function getMessages() {
    return doctorContext.state.messages || [];
}

/**
 * Get current workflow context.
 * @returns {{last_error?: string, node_context?: Object, analysis_metadata?: Object}|null}
 */
export function getWorkflowContext() {
    return doctorContext.state.workflowContext || null;
}

/**
 * Get current settings.
 * @returns {{apiKey: string, baseUrl: string, model: string, provider: string, language: string}}
 */
export function getSettings() {
    return doctorContext.state.settings || {
        apiKey: '',
        baseUrl: '',
        model: '',
        provider: 'openai',
        language: 'en'
    };
}

/**
 * Get processing state.
 * @returns {boolean}
 */
export function getIsProcessing() {
    return doctorContext.state.isProcessing || false;
}

/**
 * Get UI text translations.
 * @returns {Object<string, string>}
 */
export function getUIText() {
    return app?.Doctor?.uiText || {};
}

/**
 * Get selected nodes.
 * @returns {Array<{id: string, type: string}>}
 */
export function getSelectedNodes() {
    return doctorContext.state.selectedNodes || [];
}

/**
 * Get session ID.
 * @returns {string}
 */
export function getSessionId() {
    return doctorContext.state.sessionId || '';
}

/**
 * Get sanitization metadata from workflow context.
 * @returns {{privacy_mode: string, pii_found: boolean}|null}
 */
export function getSanitizationMetadata() {
    return doctorContext.state.workflowContext?.analysis_metadata?.sanitization || null;
}

// ═══════════════════════════════════════════════════════════════════════════
// SUBSCRIPTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Subscribe to message changes.
 * @param {(messages: Array) => void} callback
 * @returns {() => void} Unsubscribe function
 */
export function onMessagesChanged(callback) {
    return doctorContext.subscribe('messageAdded', () => {
        callback(getMessages());
    });
}

/**
 * Subscribe to state changes.
 * @param {(state: Object) => void} callback
 * @returns {() => void} Unsubscribe function
 */
export function onStateChanged(callback) {
    return doctorContext.subscribe('stateChanged', (data) => {
        // data contains {prev, current}, pass current
        const current = data?.current || doctorContext.state;
        callback(current);
    });
}

/**
 * Subscribe to processing state changes.
 * @param {(isProcessing: boolean) => void} callback
 * @returns {() => void} Unsubscribe function
 */
export function onProcessingChanged(callback) {
    return doctorContext.subscribe('change:isProcessing', (isProcessing) => {
        callback(isProcessing);
    });
}

/**
 * Subscribe to workflow context changes.
 * @param {(context: Object|null) => void} callback
 * @returns {() => void} Unsubscribe function
 */
export function onWorkflowContextChanged(callback) {
    return doctorContext.subscribe('change:workflowContext', (context) => {
        callback(context);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// NOTE: State mutation actions are in doctor_actions.js (not here)
// This module is READ-ONLY per the 5C.2 contract.
// ═══════════════════════════════════════════════════════════════════════════
