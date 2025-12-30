/**
 * ComfyUI-Doctor Extension Entry Point
 * Registers settings with ComfyUI's settings panel and initializes the Doctor UI.
 */
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { DoctorUI } from "./doctor_ui.js";
import { DoctorAPI } from "./doctor_api.js";

// Default values
const DEFAULTS = {
    LANGUAGE: "zh_TW",
    POLL_INTERVAL: 2000,
    AUTO_OPEN_ON_ERROR: false,
    ENABLE_NOTIFICATIONS: true,
};

// Provider default URLs (will be fetched from backend on init)
let PROVIDER_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://127.0.0.1:11434",
    "lmstudio": "http://localhost:1234/v1",
    "custom": ""
};

// Fetch provider defaults from backend (supports env vars)
async function loadProviderDefaults() {
    try {
        const response = await fetch('/doctor/provider_defaults');
        if (response.ok) {
            const defaults = await response.json();
            PROVIDER_DEFAULTS = { ...PROVIDER_DEFAULTS, ...defaults };
            console.log('[ComfyUI-Doctor] Provider defaults loaded:', PROVIDER_DEFAULTS);
        }
    } catch (error) {
        console.warn('[ComfyUI-Doctor] Failed to load provider defaults, using fallback:', error);
    }
}

// Supported languages
const SUPPORTED_LANGUAGES = [
    { value: "en", text: "English" },
    { value: "zh_TW", text: "繁體中文" },
    { value: "zh_CN", text: "简体中文" },
    { value: "ja", text: "日本語" },
    { value: "de", text: "Deutsch" },
    { value: "fr", text: "Français" },
    { value: "it", text: "Italiano" },
    { value: "es", text: "Español" },
    { value: "ko", text: "한국어" },
];

/**
 * Show a custom dialog with selectable/copyable text (replaces native alert).
 * @param {string} title - Dialog title
 * @param {string} content - Main content (can contain newlines)
 * @param {string} footer - Footer text/hint
 */
function showSelectableDialog(title, content, footer = '') {
    // Remove existing dialog if any
    const existing = document.getElementById('doctor-selectable-dialog');
    if (existing) existing.remove();

    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'doctor-selectable-dialog';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
    `;

    // Create dialog box
    const dialog = document.createElement('div');
    dialog.style.cssText = `
        background: #1a1a2e;
        border: 1px solid #444;
        border-radius: 12px;
        padding: 20px;
        max-width: 500px;
        max-height: 70vh;
        overflow-y: auto;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
        color: #eee;
        font-family: system-ui, -apple-system, sans-serif;
    `;

    // Title
    const titleEl = document.createElement('h3');
    titleEl.style.cssText = 'margin: 0 0 15px 0; font-size: 16px; color: #fff;';
    titleEl.textContent = title;
    dialog.appendChild(titleEl);

    // Content area (selectable)
    const contentEl = document.createElement('pre');
    contentEl.style.cssText = `
        background: #111;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        margin: 0 0 15px 0;
        font-size: 13px;
        line-height: 1.6;
        color: #ddd;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 300px;
        overflow-y: auto;
        user-select: text;
        cursor: text;
        font-family: 'Consolas', 'Monaco', monospace;
    `;
    contentEl.textContent = content;
    dialog.appendChild(contentEl);

    // Footer hint
    if (footer) {
        const footerEl = document.createElement('div');
        footerEl.style.cssText = 'font-size: 12px; color: #888; margin-bottom: 15px;';
        footerEl.textContent = footer;
        dialog.appendChild(footerEl);
    }

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '確定';
    closeBtn.style.cssText = `
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 20px;
        cursor: pointer;
        font-size: 14px;
        width: 100%;
        transition: opacity 0.2s;
    `;
    closeBtn.onmouseover = () => closeBtn.style.opacity = '0.8';
    closeBtn.onmouseout = () => closeBtn.style.opacity = '1';
    closeBtn.onclick = () => overlay.remove();
    dialog.appendChild(closeBtn);

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Close on overlay click (not dialog)
    overlay.onclick = (e) => {
        if (e.target === overlay) overlay.remove();
    };

    // Close on Escape key
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}
app.registerExtension({
    name: "ComfyUI-Doctor",

    async setup() {
        console.log("[ComfyUI-Doctor] 🟢 Frontend Extension Initialized");

        // Load provider defaults from backend (supports env vars)
        await loadProviderDefaults();

        // ========================================
        // Register Settings with ComfyUI Settings Panel (Simplified for F8)
        // ========================================

        // Enable/Disable Extension
        app.ui.settings.addSetting({
            id: "Doctor.General.Enable",
            name: "Enable Doctor (requires restart)",
            type: "boolean",
            defaultValue: true,
            onChange: (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] Enable changed: ${oldVal} -> ${newVal}`);
            },
        });

        // Check if extension is enabled
        const isEnabled = app.ui.settings.getSettingValue("Doctor.General.Enable", true);
        if (!isEnabled) {
            console.log("[ComfyUI-Doctor] Extension disabled via settings");
            return;
        }

        // Initialize default values for backward compatibility
        if (!app.ui.settings.getSettingValue("Doctor.General.Language")) {
            app.ui.settings.setSettingValue("Doctor.General.Language", DEFAULTS.LANGUAGE);
        }
        if (!app.ui.settings.getSettingValue("Doctor.Behavior.PollInterval")) {
            app.ui.settings.setSettingValue("Doctor.Behavior.PollInterval", DEFAULTS.POLL_INTERVAL);
        }
        if (!app.ui.settings.getSettingValue("Doctor.Behavior.AutoOpenOnError")) {
            app.ui.settings.setSettingValue("Doctor.Behavior.AutoOpenOnError", DEFAULTS.AUTO_OPEN_ON_ERROR);
        }
        if (!app.ui.settings.getSettingValue("Doctor.Behavior.EnableNotifications")) {
            app.ui.settings.setSettingValue("Doctor.Behavior.EnableNotifications", DEFAULTS.ENABLE_NOTIFICATIONS);
        }
        if (!app.ui.settings.getSettingValue("Doctor.LLM.Provider")) {
            app.ui.settings.setSettingValue("Doctor.LLM.Provider", "openai");
        }
        if (!app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl")) {
            app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
        }
        if (!app.ui.settings.getSettingValue("Doctor.LLM.ApiKey")) {
            app.ui.settings.setSettingValue("Doctor.LLM.ApiKey", "");
        }
        if (!app.ui.settings.getSettingValue("Doctor.LLM.Model")) {
            app.ui.settings.setSettingValue("Doctor.LLM.Model", "");
        }

        // Show info message directing users to sidebar
        app.ui.settings.addSetting({
            id: "Doctor.Info",
            name: "ℹ️ Configure Doctor settings in the sidebar (left panel)",
            type: "text",
            defaultValue: "",
            attrs: { readonly: true, disabled: true }
        });
        // ========================================

        // Get current settings values
        const language = app.ui.settings.getSettingValue("Doctor.General.Language", DEFAULTS.LANGUAGE);
        const pollInterval = app.ui.settings.getSettingValue("Doctor.Behavior.PollInterval", DEFAULTS.POLL_INTERVAL);
        const autoOpenOnError = app.ui.settings.getSettingValue("Doctor.Behavior.AutoOpenOnError", DEFAULTS.AUTO_OPEN_ON_ERROR);
        const enableNotifications = app.ui.settings.getSettingValue("Doctor.Behavior.EnableNotifications", DEFAULTS.ENABLE_NOTIFICATIONS);

        // Create Doctor UI instance with settings
        const doctorUI = new DoctorUI({
            language,
            pollInterval,
            autoOpenOnError,
            enableNotifications,
            api,  // Pass ComfyUI API for event subscription
        });

        // Store reference on app for settings callbacks
        app.Doctor = doctorUI;

        // ========================================
        // Register Sidebar Tab (Modern ComfyUI API)
        // ========================================
        // Check if the new sidebar API is available (ComfyUI 2024+)
        if (app.extensionManager && typeof app.extensionManager.registerSidebarTab === 'function') {
            app.extensionManager.registerSidebarTab({
                id: "comfyui-doctor",
                icon: "pi pi-heart-fill",  // PrimeVue icon
                title: "Doctor",
                tooltip: "ComfyUI Doctor - Error Diagnostics",
                type: "custom",
                render: (container) => {
                    // Add styles for the sidebar content if not already added
                    if (!document.getElementById('doctor-sidebar-styles')) {
                        const style = document.createElement('style');
                        style.id = 'doctor-sidebar-styles';
                        style.textContent = `
                            .doctor-sidebar-content {
                                padding: 15px;
                                height: 100%;
                                overflow-y: auto;
                                background: var(--bg-color, #1a1a2e);
                                color: var(--fg-color, #eee);
                                font-family: system-ui, -apple-system, sans-serif;
                            }
                            .doctor-sidebar-content h3 {
                                margin: 0 0 15px 0;
                                font-size: 18px;
                                display: flex;
                                align-items: center;
                                gap: 8px;
                            }
                            .doctor-sidebar-content .status-indicator {
                                width: 10px;
                                height: 10px;
                                border-radius: 50%;
                                background: #4caf50;
                                display: inline-block;
                            }
                            .doctor-sidebar-content .status-indicator.error {
                                background: #ff4444;
                                animation: pulse 1s infinite;
                            }
                            @keyframes pulse {
                                0%, 100% { opacity: 1; }
                                50% { opacity: 0.5; }
                            }
                            .doctor-sidebar-content .error-card {
                                background: rgba(255, 68, 68, 0.1);
                                border: 1px solid #ff4444;
                                border-radius: 8px;
                                padding: 12px;
                                margin-bottom: 12px;
                            }
                            .doctor-sidebar-content .error-card .error-type {
                                font-weight: bold;
                                color: #ff6b6b;
                                margin-bottom: 5px;
                            }
                            .doctor-sidebar-content .error-card .error-message {
                                font-size: 13px;
                                color: #ddd;
                                word-break: break-word;
                            }
                            .doctor-sidebar-content .error-card .error-time {
                                font-size: 11px;
                                color: #888;
                                margin-top: 8px;
                            }
                            .doctor-sidebar-content .node-context {
                                background: rgba(0,0,0,0.2);
                                border-radius: 4px;
                                padding: 8px;
                                margin-top: 8px;
                                font-size: 12px;
                            }
                            .doctor-sidebar-content .node-context span {
                                display: block;
                                margin-bottom: 3px;
                            }
                            .doctor-sidebar-content .action-btn {
                                background: #333;
                                color: #eee;
                                border: 1px solid #555;
                                padding: 8px 12px;
                                border-radius: 4px;
                                cursor: pointer;
                                font-size: 12px;
                                margin-top: 8px;
                                width: 100%;
                                text-align: center;
                                transition: background 0.2s;
                            }
                            .doctor-sidebar-content .action-btn:hover {
                                background: #444;
                            }
                            .doctor-sidebar-content .action-btn.primary {
                                background: #2563eb;
                                border-color: #3b82f6;
                            }
                            .doctor-sidebar-content .action-btn.primary:hover {
                                background: #1d4ed8;
                            }
                            .doctor-sidebar-content .no-errors {
                                text-align: center;
                                padding: 40px 20px;
                                color: #888;
                            }
                            .doctor-sidebar-content .no-errors .icon {
                                font-size: 48px;
                                margin-bottom: 10px;
                            }
                            .doctor-sidebar-content .ai-response {
                                background: rgba(37, 99, 235, 0.1);
                                border: 1px solid #2563eb;
                                border-radius: 8px;
                                padding: 12px;
                                margin-top: 12px;
                                font-size: 13px;
                                line-height: 1.5;
                            }
                            .doctor-sidebar-content .ai-response h4 {
                                margin: 0 0 8px 0;
                                color: #60a5fa;
                            }
                        `;
                        document.head.appendChild(style);
                    }

                    // Create sidebar content - SIMPLIFIED STRUCTURE with Settings Panel
                    container.innerHTML = '';
                    container.style.cssText = 'display: flex; flex-direction: column; height: 100%; background: var(--bg-color, #1a1a2e);';

                    // HEADER with Settings Toggle
                    const header = document.createElement('div');
                    header.style.cssText = 'padding: 12px 15px; border-bottom: 1px solid var(--border-color, #444); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;';
                    header.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="status-indicator" id="doctor-tab-status" style="width: 10px; height: 10px; border-radius: 50%; background: #4caf50; display: inline-block;"></span>
                            <span style="font-size: 16px; font-weight: bold; color: var(--fg-color, #eee);">🏥 Doctor</span>
                        </div>
                        <span id="doctor-settings-toggle" style="cursor: pointer; font-size: 18px; color: #888; user-select: none;" title="Toggle Settings">⚙️</span>
                    `;
                    container.appendChild(header);

                    // SETTINGS PANEL (collapsible)
                    const settingsExpanded = localStorage.getItem('doctor_settings_expanded') === 'true';
                    const settingsPanel = document.createElement('div');
                    settingsPanel.id = 'doctor-settings-panel';
                    settingsPanel.style.cssText = `
                        padding: 15px;
                        border-bottom: 1px solid var(--border-color, #444);
                        background: rgba(0,0,0,0.2);
                        flex-shrink: 0;
                        display: ${settingsExpanded ? 'block' : 'none'};
                    `;

                    // Get current settings values
                    const currentLanguage = app.ui.settings.getSettingValue("Doctor.General.Language", DEFAULTS.LANGUAGE);
                    const currentProvider = app.ui.settings.getSettingValue("Doctor.LLM.Provider", "openai");
                    const currentBaseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
                    const currentApiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
                    const currentModel = app.ui.settings.getSettingValue("Doctor.LLM.Model", "");

                    settingsPanel.innerHTML = `
                        <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #ddd;">Settings</h4>
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">Language</label>
                                <select id="doctor-language-select" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                                    ${SUPPORTED_LANGUAGES.map(lang =>
                                        `<option value="${lang.value}" ${lang.value === currentLanguage ? 'selected' : ''}>${lang.text}</option>`
                                    ).join('')}
                                </select>
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">AI Provider</label>
                                <select id="doctor-provider-select" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                                    <option value="openai" ${currentProvider === 'openai' ? 'selected' : ''}>OpenAI</option>
                                    <option value="deepseek" ${currentProvider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
                                    <option value="groq" ${currentProvider === 'groq' ? 'selected' : ''}>Groq Cloud (LPU)</option>
                                    <option value="gemini" ${currentProvider === 'gemini' ? 'selected' : ''}>Google Gemini</option>
                                    <option value="xai" ${currentProvider === 'xai' ? 'selected' : ''}>xAI Grok</option>
                                    <option value="openrouter" ${currentProvider === 'openrouter' ? 'selected' : ''}>OpenRouter (Claude)</option>
                                    <option value="ollama" ${currentProvider === 'ollama' ? 'selected' : ''}>Ollama (Local)</option>
                                    <option value="lmstudio" ${currentProvider === 'lmstudio' ? 'selected' : ''}>LMStudio (Local)</option>
                                    <option value="custom" ${currentProvider === 'custom' ? 'selected' : ''}>Custom</option>
                                </select>
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">Base URL</label>
                                <input type="text" id="doctor-baseurl-input" value="${currentBaseUrl}" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">API Key</label>
                                <input type="password" id="doctor-apikey-input" value="${currentApiKey}" placeholder="Leave empty for local LLMs" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">Model Name</label>
                                <input type="text" id="doctor-model-input" value="${currentModel}" placeholder="e.g., gpt-4o, deepseek-chat" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                            </div>
                            <button id="doctor-save-settings-btn" style="width: 100%; padding: 8px; background: #4caf50; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; font-size: 13px; margin-top: 5px;">💾 Save Settings</button>
                        </div>
                    `;
                    container.appendChild(settingsPanel);

                    // Settings toggle functionality
                    const settingsToggle = header.querySelector('#doctor-settings-toggle');
                    const updateToggleIcon = (expanded) => {
                        settingsToggle.style.color = expanded ? '#4caf50' : '#888';
                    };
                    updateToggleIcon(settingsExpanded);

                    settingsToggle.onclick = () => {
                        const isExpanded = settingsPanel.style.display === 'block';
                        settingsPanel.style.display = isExpanded ? 'none' : 'block';
                        localStorage.setItem('doctor_settings_expanded', !isExpanded);
                        updateToggleIcon(!isExpanded);
                    };

                    // Provider change auto-fills Base URL (using backend defaults)
                    const providerSelect = settingsPanel.querySelector('#doctor-provider-select');
                    const baseUrlInput = settingsPanel.querySelector('#doctor-baseurl-input');
                    providerSelect.onchange = () => {
                        baseUrlInput.value = PROVIDER_DEFAULTS[providerSelect.value] || "";
                    };

                    // Save settings button
                    const saveBtn = settingsPanel.querySelector('#doctor-save-settings-btn');
                    saveBtn.onclick = async () => {
                        const langSelect = settingsPanel.querySelector('#doctor-language-select');
                        const apiKeyInput = settingsPanel.querySelector('#doctor-apikey-input');
                        const modelInput = settingsPanel.querySelector('#doctor-model-input');

                        try {
                            // Save to ComfyUI Settings
                            app.ui.settings.setSettingValue("Doctor.General.Language", langSelect.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.Provider", providerSelect.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", baseUrlInput.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.ApiKey", apiKeyInput.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.Model", modelInput.value);

                            // Sync language with backend
                            await DoctorAPI.setLanguage(langSelect.value);

                            // Visual feedback
                            const originalText = saveBtn.textContent;
                            saveBtn.textContent = '✅ Saved!';
                            saveBtn.style.background = '#4caf50';
                            setTimeout(() => {
                                saveBtn.textContent = originalText;
                                saveBtn.style.background = '#4caf50';
                            }, 2000);
                        } catch (e) {
                            console.error('[ComfyUI-Doctor] Failed to save settings:', e);
                            saveBtn.textContent = '❌ Error';
                            saveBtn.style.background = '#f44336';
                            setTimeout(() => {
                                saveBtn.textContent = '💾 Save Settings';
                                saveBtn.style.background = '#4caf50';
                            }, 2000);
                        }
                    };

                    // ERROR CONTEXT AREA (shows error details when available)
                    const errorContext = document.createElement('div');
                    errorContext.id = 'doctor-error-context';
                    errorContext.style.cssText = 'flex-shrink: 0; border-bottom: 1px solid var(--border-color, #444); display: none;';
                    container.appendChild(errorContext);

                    // MESSAGES AREA (flex-1 to fill remaining space)
                    const messages = document.createElement('div');
                    messages.id = 'doctor-messages';
                    messages.style.cssText = 'flex: 1; overflow-y: auto; padding: 10px; min-height: 0;';
                    messages.innerHTML = `
                        <div style="text-align: center; padding: 40px 20px; color: #888;">
                            <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
                            <div>No errors detected</div>
                            <div style="margin-top: 5px; font-size: 12px;">System running smoothly</div>
                        </div>
                    `;
                    container.appendChild(messages);

                    // INPUT AREA (fixed at bottom using sticky positioning)
                    const inputArea = document.createElement('div');
                    inputArea.id = 'doctor-input-area';
                    inputArea.style.cssText = 'border-top: 1px solid var(--border-color, #444); background: var(--bg-color, #252525); padding: 10px; position: sticky; bottom: 0; flex-shrink: 0;';
                    inputArea.innerHTML = `
                        <textarea id="doctor-input" placeholder="Ask AI about this error..."
                            style="width: 100%; min-height: 60px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; padding: 8px; font-family: inherit; font-size: 13px; resize: vertical;"
                            rows="2"></textarea>
                        <div style="display: flex; gap: 8px; margin-top: 8px;">
                            <button id="doctor-send-btn" style="flex: 1; background: #4caf50; color: white; border: none; border-radius: 4px; padding: 8px; cursor: pointer; font-weight: bold;">Send</button>
                            <button id="doctor-clear-btn" style="background: #666; color: white; border: none; border-radius: 4px; padding: 8px; cursor: pointer;">Clear</button>
                        </div>
                    `;
                    container.appendChild(inputArea);

                    // Store references
                    doctorUI.sidebarTabContainer = container;
                    doctorUI.sidebarErrorContext = errorContext;
                    doctorUI.sidebarMessages = messages;
                    doctorUI.sidebarInput = inputArea.querySelector('#doctor-input');
                    doctorUI.sidebarSendBtn = inputArea.querySelector('#doctor-send-btn');
                    doctorUI.sidebarClearBtn = inputArea.querySelector('#doctor-clear-btn');

                    // Update content if there's already an error
                    if (doctorUI.lastErrorData) {
                        doctorUI.updateSidebarTab(doctorUI.lastErrorData);
                    }
                }
            });
            console.log("[ComfyUI-Doctor] ✅ Sidebar tab registered successfully");
        } else {
            console.log("[ComfyUI-Doctor] Sidebar API not available, using legacy menu button");
        }

        // Sync initial language with backend
        try {
            await DoctorAPI.setLanguage(language);
        } catch (e) {
            console.error("[ComfyUI-Doctor] Failed to sync initial language:", e);
        }

        console.log("[ComfyUI-Doctor] Settings registered successfully");
    }
});

