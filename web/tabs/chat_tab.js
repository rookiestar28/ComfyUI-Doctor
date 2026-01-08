/**
 * ComfyUI-Doctor Chat Tab Component
 * Provides AI chat interface within the Doctor sidebar.
 * Uses Island Registry for standardized mount/unmount.
 */
import { app } from "../../../../scripts/app.js";
import { register, mount } from "../island_registry.js";
import { renderChatIsland, unmountChatIsland } from "../chat-island.js";
import { isPreactEnabled } from "../preact-loader.js";

let isPreactMode = false;

// ═══════════════════════════════════════════════════════════════
// ISLAND REGISTRATION (5C.1)
// ═══════════════════════════════════════════════════════════════

register({
    id: 'chat',
    isEnabled: () => isPreactEnabled(),
    render: async (container, props) => {
        const success = await renderChatIsland(container, props, { replace: true });
        if (!success) throw new Error('ChatIsland render returned false');
    },
    unmount: (container) => {
        unmountChatIsland();
    },
    fallbackRender: (container, error) => {
        renderVanilla(container);
    },
    onError: (error) => {
        console.warn('[ChatTab] Island error:', error?.message);
    }
});

// ═══════════════════════════════════════════════════════════════
// TAB RENDER & ACTIVATE
// ═══════════════════════════════════════════════════════════════

export async function render(container) {
    const doctorUI = app.Doctor;

    // 5C.1: Use registry for mount - it handles Preact and fallback automatically
    isPreactMode = false;

    // Attempt Preact via Registry
    const success = await mount('chat', container, { uiText: doctorUI.uiText });

    if (success) {
        isPreactMode = true;
        // 5B.1: Set island active flag to gate DoctorUI DOM updates
        doctorUI.chatIslandActive = true;
        // Styles for container
        container.style.cssText = 'display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden;';
        // Clear vanilla references so DoctorUI doesn't try to manipulate removed DOM.
        doctorUI.sidebarErrorContext = null;
        doctorUI.sidebarSanitizationStatus = null;
        doctorUI.sidebarMessages = null;
        doctorUI.sidebarInput = null;
        doctorUI.sidebarSendBtn = null;
        doctorUI.sidebarClearBtn = null;
        doctorUI.updateSanitizationStatusVanilla = null;
    } else {
        // 5B.1: Ensure flag is false when Preact fails
        // Note: fallbackRender was already called by registry
        doctorUI.chatIslandActive = false;
    }
}

export function onActivate() {
    // Scroll to bottom logic
    const doctorUI = app.Doctor;

    if (isPreactMode) {
        // ChatIsland handles its own scrolling via Ref/Effects usually, 
        // but if we need to force it, we might need a handle.
        // For now assume ChatIsland auto-scrolls on mount/update.
        // HACK: Select the message container inside island and scroll it
        const msgContainer = document.querySelector('.chat-messages');
        if (msgContainer) {
            msgContainer.scrollTop = msgContainer.scrollHeight;
        }
    } else {
        // Vanilla Logic
        if (doctorUI.sidebarMessages) {
            doctorUI.sidebarMessages.scrollTop = doctorUI.sidebarMessages.scrollHeight;
        }
        // Refresh sanitization status
        const statusEl = document.getElementById('doctor-sanitization-status');
        if (statusEl) {
            // We need to export updateSanitizationStatus or make it accessible
            // It's defined locally in chat_tab.js. We need to keep it there for Vanilla.
            // We'll duplicate the update call logic here or make it a shared helper on doctorUI?
            if (doctorUI.updateSanitizationStatusVanilla) {
                doctorUI.updateSanitizationStatusVanilla(statusEl);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// VANILLA RENDERER (Legacy F13 Logic)
// ═══════════════════════════════════════════════════════════════

function renderVanilla(container) {
    const doctorUI = app.Doctor;
    // Container fills parent flex container and uses column layout
    container.style.cssText = 'display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden;';

    // 1. Error Context Area
    const errorContext = document.createElement('div');
    errorContext.id = 'doctor-error-context';
    errorContext.style.cssText = 'flex-shrink: 0; border-bottom: 1px solid var(--border-color, #444); display: none;';
    container.appendChild(errorContext);

    // 2. Sanitization Status Bar
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

    // 3. Messages Area
    const messages = document.createElement('div');
    messages.id = 'doctor-messages';
    messages.style.cssText = 'flex: 1 1 0; overflow-y: auto; overflow-x: hidden; padding: 10px; min-height: 0;';

    messages.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: #888;">
            <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
            <div>${doctorUI.getUIText('no_errors_detected')}</div>
            <div style="margin-top: 5px; font-size: 12px;">${doctorUI.getUIText('system_running_smoothly')}</div>
        </div>
    `;
    container.appendChild(messages);

    // 4. Input Area
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

    doctorUI.sidebarSendBtn._hasListener = true;
    doctorUI.sidebarClearBtn._hasListener = true;
    doctorUI.sidebarInput._hasListener = true;

    // Initial Updates
    if (doctorUI.lastErrorData) {
        doctorUI.updateSidebarTab(doctorUI.lastErrorData);
    }

    // Attach update helper to doctorUI for onActivate usage
    doctorUI.updateSanitizationStatusVanilla = (el) => updateSanitizationStatus(doctorUI, el);
    updateSanitizationStatus(doctorUI, sanitizationStatus);
}

function updateSanitizationStatus(doctorUI, statusEl) {
    const metadata = doctorUI.lastAnalysisMetadata?.sanitization;
    if (!metadata) {
        statusEl.style.display = 'none';
        return;
    }

    const privacyMode = metadata.privacy_mode || 'basic';
    const piiFound = metadata.pii_found === true;

    const privacyLabel = doctorUI.getUIText('sanitization_label') || 'Privacy';
    const modeLabel = doctorUI.getUIText(`sanitization_${privacyMode}`) || privacyMode;
    const piiLabel = piiFound
        ? (doctorUI.getUIText('sanitization_pii_found') || 'PII removed')
        : (doctorUI.getUIText('sanitization_pii_not_found') || 'No PII');

    const modeIcon = privacyMode === 'strict' ? '🔒' : (privacyMode === 'basic' ? '🔐' : '🔓');
    const piiIcon = piiFound ? '✓' : '';

    statusEl.innerHTML = `
        <span style="margin-right: 12px;">${modeIcon} ${privacyLabel}: <strong>${modeLabel}</strong></span>
        <span style="color: ${piiFound ? '#4caf50' : '#888'};">${piiIcon} ${piiLabel}</span>
    `;
    statusEl.style.display = 'block';

    if (privacyMode === 'strict') statusEl.style.background = 'rgba(76, 175, 80, 0.15)';
    else if (privacyMode === 'basic') statusEl.style.background = 'rgba(255, 193, 7, 0.1)';
    else statusEl.style.background = 'rgba(158, 158, 158, 0.1)';
}
