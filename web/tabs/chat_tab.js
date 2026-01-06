/**
 * ComfyUI-Doctor Chat Tab Component
 * Provides AI chat interface within the Doctor sidebar.
 *
 * ═══════════════════════════════════════════════════════════════
 * CRITICAL CSS NOTES (2026-01-06):
 * ═══════════════════════════════════════════════════════════════
 * 1. Container MUST use flex: 1; min-height: 0; (not height: 100%)
 *    because parent .doctor-tab-pane is a flex container.
 *
 * 2. Messages area MUST use min-height: 0 for overflow-y: auto
 *    to work properly in nested flex layouts.
 *
 * 3. DO NOT use height: 100% on flex children - use flex: 1 instead.
 *
 * See: .planning/260106-F13_SIDEBAR_TAB_REFACTORING_IMPLEMENTATION_RECORD.md
 * ═══════════════════════════════════════════════════════════════
 */
import { app } from "../../../../scripts/app.js";

export function render(container) {
    const doctorUI = app.Doctor;
    // Container fills parent flex container and uses column layout
    // ⚠️ Parent .doctor-tab-pane is display: flex, so use flex: 1 not height: 100%
    container.style.cssText = 'display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden;';

    // 1. Error Context Area
    // Separator line at bottom to distinguish from messages
    const errorContext = document.createElement('div');
    errorContext.id = 'doctor-error-context';
    errorContext.style.cssText = 'flex-shrink: 0; border-bottom: 1px solid var(--border-color, #444); display: none;';
    container.appendChild(errorContext);

    // 2. Sanitization Status Bar (F13 requirement)
    // Shows privacy mode and PII detection status from analysis_metadata.sanitization
    const sanitizationStatus = document.createElement('div');
    sanitizationStatus.id = 'doctor-sanitization-status';
    sanitizationStatus.style.cssText = `
        flex-shrink: 0;
        background: rgba(76, 175, 80, 0.1);
        border-bottom: 1px solid var(--border-color, #444);
        padding: 6px 10px;
        font-size: 11px;
        color: #888;
        display: none;
    `;
    container.appendChild(sanitizationStatus);

    // 3. Messages Area (AI Chat)
    // ⚠️ CRITICAL: min-height: 0 is required for flex child scrolling to work
    const messages = document.createElement('div');
    messages.id = 'doctor-messages';
    messages.style.cssText = 'flex: 1 1 0; overflow-y: auto; overflow-x: hidden; padding: 10px; min-height: 0;';

    // Default Empty State
    messages.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: #888;">
            <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
            <div>${doctorUI.getUIText('no_errors_detected')}</div>
            <div style="margin-top: 5px; font-size: 12px;">${doctorUI.getUIText('system_running_smoothly')}</div>
        </div>
    `;
    container.appendChild(messages);

    // 4. Input Area (Sticky at Bottom)
    const inputArea = document.createElement('div');
    inputArea.id = 'doctor-input-area';
    inputArea.style.cssText = 'border-top: 1px solid var(--border-color, #444); background: var(--bg-color, #252525); padding: 10px; position: sticky; bottom: 0; flex-shrink: 0;';
    inputArea.innerHTML = `
        <textarea id="doctor-input" placeholder="${doctorUI.getUIText('ask_ai_placeholder')}"
            style="width: 100%; min-height: 60px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; padding: 8px; font-family: inherit; font-size: 13px; resize: vertical;"
            rows="2"></textarea>
        <div style="display: flex; gap: 8px; margin-top: 8px;">
            <button id="doctor-send-btn" style="flex: 1; background: #4caf50; color: white; border: none; border-radius: 4px; padding: 8px; cursor: pointer; font-weight: bold;">${doctorUI.getUIText('send_btn')}</button>
            <button id="doctor-clear-btn" style="background: #666; color: white; border: none; border-radius: 4px; padding: 8px; cursor: pointer;">${doctorUI.getUIText('clear_btn')}</button>
        </div>
    `;
    container.appendChild(inputArea);

    // Store references for DoctorUI logic
    doctorUI.sidebarErrorContext = errorContext;
    doctorUI.sidebarSanitizationStatus = sanitizationStatus;
    doctorUI.sidebarMessages = messages;
    doctorUI.sidebarInput = inputArea.querySelector('#doctor-input');
    doctorUI.sidebarSendBtn = inputArea.querySelector('#doctor-send-btn');
    doctorUI.sidebarClearBtn = inputArea.querySelector('#doctor-clear-btn');

    // Attach Event Listeners
    doctorUI.sidebarSendBtn.addEventListener('click', () => doctorUI.handleSendMessage());
    doctorUI.sidebarClearBtn.addEventListener('click', () => doctorUI.handleClearChat());
    doctorUI.sidebarInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            doctorUI.handleSendMessage();
        }
    });

    // Mark as having listeners so updateSidebarTab doesn't double attach
    doctorUI.sidebarSendBtn._hasListener = true;
    doctorUI.sidebarClearBtn._hasListener = true;
    doctorUI.sidebarInput._hasListener = true;

    // Initial Content Update
    if (doctorUI.lastErrorData) {
        doctorUI.updateSidebarTab(doctorUI.lastErrorData);
    }

    // Initial Sanitization Status Update
    updateSanitizationStatus(doctorUI, sanitizationStatus);
}

/**
 * Update the sanitization status display based on last analysis metadata.
 * @param {Object} doctorUI - The DoctorUI instance
 * @param {HTMLElement} statusEl - The status bar element
 */
function updateSanitizationStatus(doctorUI, statusEl) {
    // Try to get analysis_metadata from last error data or fetch from API
    const metadata = doctorUI.lastAnalysisMetadata?.sanitization;

    if (!metadata) {
        statusEl.style.display = 'none';
        return;
    }

    const privacyMode = metadata.privacy_mode || 'basic';
    const piiFound = metadata.pii_found === true;

    // Get localized labels
    const privacyLabel = doctorUI.getUIText('sanitization_label') || 'Privacy';
    const modeLabel = doctorUI.getUIText(`sanitization_${privacyMode}`) || privacyMode;
    const piiLabel = piiFound
        ? (doctorUI.getUIText('sanitization_pii_found') || 'PII removed')
        : (doctorUI.getUIText('sanitization_pii_not_found') || 'No PII');

    // Icon based on mode
    const modeIcon = privacyMode === 'strict' ? '🔒' : (privacyMode === 'basic' ? '🔐' : '🔓');
    const piiIcon = piiFound ? '✓' : '';

    statusEl.innerHTML = `
        <span style="margin-right: 12px;">${modeIcon} ${privacyLabel}: <strong>${modeLabel}</strong></span>
        <span style="color: ${piiFound ? '#4caf50' : '#888'};">${piiIcon} ${piiLabel}</span>
    `;
    statusEl.style.display = 'block';

    // Update background based on mode
    if (privacyMode === 'strict') {
        statusEl.style.background = 'rgba(76, 175, 80, 0.15)';
    } else if (privacyMode === 'basic') {
        statusEl.style.background = 'rgba(255, 193, 7, 0.1)';
    } else {
        statusEl.style.background = 'rgba(158, 158, 158, 0.1)';
    }
}

export function onActivate() {
    const doctorUI = app.Doctor;
    // Scroll to bottom
    if (doctorUI.sidebarMessages) {
        doctorUI.sidebarMessages.scrollTop = doctorUI.sidebarMessages.scrollHeight;
    }

    // Refresh sanitization status
    const statusEl = document.getElementById('doctor-sanitization-status');
    if (statusEl) {
        updateSanitizationStatus(doctorUI, statusEl);
    }
}
