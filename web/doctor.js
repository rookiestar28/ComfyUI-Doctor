/**
 * ComfyUI-Doctor Extension Entry Point
 * Registers settings with ComfyUI's settings panel and initializes the Doctor UI.
 */
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { DoctorUI } from "./doctor_ui.js";
import { DoctorAPI } from "./doctor_api.js";

// ═══════════════════════════════════════════════════════════════════════════
// CRITICAL: Frontend Default Configuration
// ═══════════════════════════════════════════════════════════════════════════
// ⚠️ WARNING: LANGUAGE must always be "en" (English)
//
// This default is used when:
//   1. User first installs ComfyUI-Doctor (no settings saved yet)
//   2. ComfyUI settings are reset/corrupted
//   3. DoctorUI constructor receives no language option
//
// MUST MATCH backend default in i18n.py (_current_language = "en")
//
// If these don't match:
//   ❌ Backend suggestions will be in different language than UI
//   ❌ Confusing experience for international users
//
// To change default for your installation:
//   → Modify ComfyUI Settings → Doctor → Language
//   → DO NOT change this hardcoded value
//
// Last Modified: 2026-01-03 (Fixed from "zh_TW" to "en")
// ═══════════════════════════════════════════════════════════════════════════
const DEFAULTS = {
    LANGUAGE: "en",  // ⚠️ DO NOT CHANGE - Must match i18n.py backend default
    POLL_INTERVAL: 2000,
    AUTO_OPEN_ON_ERROR: false,
    ENABLE_NOTIFICATIONS: true,
};

// Provider default URLs (will be fetched from backend on init)
let PROVIDER_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
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
            name: "Enable Doctor (requires restart)",  // Hardcoded: doctorUI not created yet (fixed 2026-01-03)
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
            name: "ℹ️ Configure Doctor settings in the sidebar (left panel)",  // Hardcoded: doctorUI not created yet (fixed 2026-01-03)
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
                title: doctorUI.getUIText('sidebar_doctor_title'),
                tooltip: doctorUI.getUIText('sidebar_doctor_tooltip'),
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
                            /* F4: Statistics Dashboard Styles */
                            .doctor-sidebar-content .stats-panel {
                                background: rgba(0,0,0,0.2);
                                border-radius: 8px;
                                padding: 12px;
                                margin: 10px 0;
                            }
                            .doctor-sidebar-content .stats-panel summary {
                                cursor: pointer;
                                font-weight: bold;
                                font-size: 13px;
                                color: #ddd;
                                display: flex;
                                align-items: center;
                                gap: 6px;
                            }
                            .doctor-sidebar-content .stats-grid {
                                display: grid;
                                grid-template-columns: 1fr 1fr;
                                gap: 8px;
                                margin-top: 10px;
                            }
                            .doctor-sidebar-content .stat-card {
                                background: rgba(255,255,255,0.05);
                                border: 1px solid #444;
                                border-radius: 6px;
                                padding: 10px;
                                text-align: center;
                                transition: transform 0.2s, box-shadow 0.2s;
                            }
                            .doctor-sidebar-content .stat-card:hover {
                                transform: translateY(-2px);
                                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                            }
                            .doctor-sidebar-content .stat-card .stat-value {
                                font-size: 24px;
                                font-weight: bold;
                                color: #f44;
                            }
                            .doctor-sidebar-content .stat-card .stat-label {
                                font-size: 11px;
                                color: #888;
                                margin-top: 4px;
                            }
                            .doctor-sidebar-content .top-patterns {
                                margin-top: 10px;
                            }
                            .doctor-sidebar-content .top-patterns h5 {
                                margin: 0 0 8px 0;
                                font-size: 12px;
                                color: #aaa;
                            }
                            .doctor-sidebar-content .pattern-item {
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                padding: 6px 8px;
                                background: rgba(255,68,68,0.1);
                                border-radius: 4px;
                                margin-bottom: 4px;
                                font-size: 12px;
                            }
                            .doctor-sidebar-content .pattern-item .pattern-name {
                                color: #ff6b6b;
                                flex: 1;
                            }
                            .doctor-sidebar-content .pattern-item .pattern-count {
                                background: #f44;
                                color: white;
                                padding: 2px 6px;
                                border-radius: 10px;
                                font-size: 10px;
                                font-weight: bold;
                            }
                            .doctor-sidebar-content .category-bar {
                                margin-bottom: 6px;
                            }
                            .doctor-sidebar-content .category-bar .bar-label {
                                font-size: 11px;
                                color: #aaa;
                                display: flex;
                                justify-content: space-between;
                                margin-bottom: 2px;
                            }
                            .doctor-sidebar-content .category-bar .bar-track {
                                height: 6px;
                                background: #333;
                                border-radius: 3px;
                                overflow: hidden;
                            }
                            .doctor-sidebar-content .category-bar .bar-fill {
                                height: 100%;
                                border-radius: 3px;
                                transition: width 0.3s ease;
                            }
                            .doctor-sidebar-content .stats-empty {
                                text-align: center;
                                padding: 20px;
                                color: #666;
                                font-size: 12px;
                            }
                        `;
                        document.head.appendChild(style);
                    }

                    // ═══════════════════════════════════════════════════════════════
                    // LEFT SIDEBAR PANEL - Doctor Sidebar (Main UI)
                    // ═══════════════════════════════════════════════════════════════
                    // LOCATION: Left side of ComfyUI (accessed via 🏥 Doctor icon)
                    // DO NOT CONFUSE WITH: Right error panel (doctor_ui.js)
                    //
                    // STRUCTURE:
                    // 1. Header (🏥 Doctor + ⚙️ Settings toggle)
                    // 2. Settings Panel (collapsible)
                    // 3. Error Context Card (shows suggestion when error occurs)
                    // 4. Messages Area (AI chat interface)
                    // 5. Input Area (sticky at bottom)
                    //
                    // IMPORTANT NOTES:
                    // - Error Context Card displays CONCISE SUGGESTION ONLY
                    // - Suggestion extraction logic in doctor_ui.js:updateSidebarTab()
                    // - Full error details sent to LLM, only actionable advice shown here
                    // ═══════════════════════════════════════════════════════════════

                    // Create sidebar content - SIMPLIFIED STRUCTURE with Settings Panel
                    container.innerHTML = '';
                    container.style.cssText = 'display: flex; flex-direction: column; height: 100%; background: var(--bg-color, #1a1a2e);';

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 1: HEADER with Settings Toggle
                    // ═══════════════════════════════════════════════════════════════
                    const header = document.createElement('div');
                    header.style.cssText = 'padding: 12px 15px; border-bottom: 1px solid var(--border-color, #444); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;';
                    header.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="status-indicator" id="doctor-tab-status" style="width: 10px; height: 10px; border-radius: 50%; background: #4caf50; display: inline-block;"></span>
                            <span style="font-size: 16px; font-weight: bold; color: var(--fg-color, #eee);">🏥 ${app.Doctor.getUIText('sidebar_doctor_title')}</span>
                        </div>
                        <span id="doctor-settings-toggle" style="cursor: pointer; font-size: 18px; color: #888; user-select: none;" title="Toggle Settings">⚙️</span>
                    `;
                    container.appendChild(header);

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 2: SETTINGS PANEL (collapsible)
                    // ═══════════════════════════════════════════════════════════════
                    // Contains: Language, AI Provider, Base URL, API Key, Model Name
                    // Toggle: Click ⚙️ icon in header
                    // State: Persisted in localStorage ('doctor_settings_expanded')
                    // ═══════════════════════════════════════════════════════════════
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
                    const currentPrivacyMode = app.ui.settings.getSettingValue("Doctor.Privacy.Mode", "basic");

                    settingsPanel.innerHTML = `
                        <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #ddd;">${app.Doctor.getUIText('settings_title')}</h4>
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">${app.Doctor.getUIText('language_label')}</label>
                                <select id="doctor-language-select" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                                    ${SUPPORTED_LANGUAGES.map(lang =>
                        `<option value="${lang.value}" ${lang.value === currentLanguage ? 'selected' : ''}>${lang.text}</option>`
                    ).join('')}
                                </select>
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">${app.Doctor.getUIText('ai_provider_label')}</label>
                                <select id="doctor-provider-select" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                                    <option value="openai" ${currentProvider === 'openai' ? 'selected' : ''}>OpenAI</option>
                                    <option value="anthropic" ${currentProvider === 'anthropic' ? 'selected' : ''}>Anthropic Claude</option>
                                    <option value="deepseek" ${currentProvider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
                                    <option value="groq" ${currentProvider === 'groq' ? 'selected' : ''}>Groq Cloud (LPU)</option>
                                    <option value="gemini" ${currentProvider === 'gemini' ? 'selected' : ''}>Google Gemini</option>
                                    <option value="xai" ${currentProvider === 'xai' ? 'selected' : ''}>xAI Grok</option>
                                    <option value="openrouter" ${currentProvider === 'openrouter' ? 'selected' : ''}>OpenRouter</option>
                                    <option value="ollama" ${currentProvider === 'ollama' ? 'selected' : ''}>Ollama (Local)</option>
                                    <option value="lmstudio" ${currentProvider === 'lmstudio' ? 'selected' : ''}>LMStudio (Local)</option>
                                    <option value="custom" ${currentProvider === 'custom' ? 'selected' : ''}>Custom</option>
                                </select>
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">${app.Doctor.getUIText('base_url_label')}</label>
                                <input type="text" id="doctor-baseurl-input" value="${currentBaseUrl}" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">${app.Doctor.getUIText('api_key_label')}</label>
                                <input type="password" id="doctor-apikey-input" value="${currentApiKey}" placeholder="${app.Doctor.getUIText('api_key_placeholder')}" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; color: #aaa; margin-bottom: 3px;">${app.Doctor.getUIText('model_name_label')}</label>
                                <div style="display: flex; gap: 5px; align-items: center;">
                                    <select id="doctor-model-select" style="flex: 1; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;">
                                        <option value="">${app.Doctor.getUIText('loading_models')}</option>
                                    </select>
                                    <button id="doctor-refresh-models-btn" style="padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 13px;" title="Refresh model list">🔄</button>
                                </div>
                                <div style="margin-top: 5px;">
                                    <label style="font-size: 11px; color: #888; cursor: pointer;">
                                        <input type="checkbox" id="doctor-manual-model-toggle" style="margin-right: 3px;">
                                        ${app.Doctor.getUIText('enter_model_manually')}
                                    </label>
                                </div>
                                <input type="text" id="doctor-model-input-manual" value="${currentModel}" placeholder="${app.Doctor.getUIText('model_manual_placeholder')}" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box; margin-top: 5px; display: none;" />
                            </div>
                            <div style="border-top: 1px solid #444; padding-top: 10px; margin-top: 5px;">
                                <label style="display: flex; align-items: center; gap: 5px; font-size: 12px; color: #aaa; margin-bottom: 3px;">
                                    🔒 <span id="doctor-privacy-label">${app.Doctor.getUIText('privacy_mode')}</span>
                                </label>
                                <select id="doctor-privacy-select" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                                    <option value="none" ${currentPrivacyMode === 'none' ? 'selected' : ''} id="privacy-none-option">${app.Doctor.getUIText('privacy_mode_none')}</option>
                                    <option value="basic" ${currentPrivacyMode === 'basic' ? 'selected' : ''} id="privacy-basic-option">${app.Doctor.getUIText('privacy_mode_basic')}</option>
                                    <option value="strict" ${currentPrivacyMode === 'strict' ? 'selected' : ''} id="privacy-strict-option">${app.Doctor.getUIText('privacy_mode_strict')}</option>
                                </select>
                                <div id="doctor-privacy-hint" style="font-size: 11px; color: #888; margin-top: 3px;">${app.Doctor.getUIText('privacy_mode_hint')}</div>
                            </div>
                            <button id="doctor-save-settings-btn" style="width: 100%; padding: 8px; background: #4caf50; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; font-size: 13px; margin-top: 5px;">💾 ${app.Doctor.getUIText('save_settings_btn')}</button>
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
                    const modelSelect = settingsPanel.querySelector('#doctor-model-select');
                    const refreshModelsBtn = settingsPanel.querySelector('#doctor-refresh-models-btn');
                    const manualToggle = settingsPanel.querySelector('#doctor-manual-model-toggle');
                    const modelInputManual = settingsPanel.querySelector('#doctor-model-input-manual');
                    const apiKeyInput = settingsPanel.querySelector('#doctor-apikey-input');

                    // Load models from API
                    const loadModels = async () => {
                        const baseUrl = baseUrlInput.value;
                        const apiKey = apiKeyInput.value;

                        if (!baseUrl) {
                            modelSelect.innerHTML = '<option value="">Please set Base URL first</option>';
                            return;
                        }

                        // Show loading state
                        refreshModelsBtn.textContent = '⏳';
                        refreshModelsBtn.disabled = true;
                        modelSelect.disabled = true;

                        try {
                            const result = await DoctorAPI.listModels(baseUrl, apiKey);

                            if (result.success && result.models.length > 0) {
                                // Populate dropdown
                                modelSelect.innerHTML = '';
                                result.models.forEach(model => {
                                    const option = document.createElement('option');
                                    option.value = model.id;
                                    option.textContent = model.name;
                                    modelSelect.appendChild(option);
                                });

                                // Restore current selection if available
                                if (currentModel) {
                                    const modelExists = result.models.find(m => m.id === currentModel);
                                    if (modelExists) {
                                        modelSelect.value = currentModel;
                                    } else {
                                        // Add current model as first option if not in list
                                        const option = document.createElement('option');
                                        option.value = currentModel;
                                        option.textContent = `${currentModel} (current)`;
                                        option.selected = true;
                                        modelSelect.insertBefore(option, modelSelect.firstChild);
                                    }
                                }

                                console.log(`[ComfyUI-Doctor] Loaded ${result.models.length} models from ${baseUrl}`);
                            } else {
                                modelSelect.innerHTML = '<option value="">No models found - use manual input</option>';
                            }
                        } catch (error) {
                            console.error('[ComfyUI-Doctor] Failed to load models:', error);
                            modelSelect.innerHTML = '<option value="">Error loading models - use manual input</option>';
                        } finally {
                            refreshModelsBtn.textContent = '🔄';
                            refreshModelsBtn.disabled = false;
                            modelSelect.disabled = false;
                        }
                    };

                    // Refresh button click handler
                    refreshModelsBtn.onclick = () => loadModels();

                    // Manual input toggle
                    manualToggle.onchange = () => {
                        if (manualToggle.checked) {
                            modelSelect.style.display = 'none';
                            refreshModelsBtn.style.display = 'none';
                            modelInputManual.style.display = 'block';
                            modelInputManual.value = modelSelect.value || currentModel;
                        } else {
                            modelSelect.style.display = 'block';
                            refreshModelsBtn.style.display = 'block';
                            modelInputManual.style.display = 'none';
                        }
                    };

                    // Provider change: auto-fill Base URL and reload models
                    providerSelect.onchange = () => {
                        baseUrlInput.value = PROVIDER_DEFAULTS[providerSelect.value] || "";
                        if (baseUrlInput.value && !manualToggle.checked) {
                            loadModels();
                        }
                    };

                    // Auto-load models on initialization
                    if (currentBaseUrl && !manualToggle.checked) {
                        loadModels();
                    }

                    // Privacy mode translations update
                    const privacySelect = settingsPanel.querySelector('#doctor-privacy-select');
                    const updatePrivacyTranslations = (lang) => {
                        const privacyLabel = settingsPanel.querySelector('#doctor-privacy-label');
                        const privacyHint = settingsPanel.querySelector('#doctor-privacy-hint');
                        const noneOption = settingsPanel.querySelector('#privacy-none-option');
                        const basicOption = settingsPanel.querySelector('#privacy-basic-option');
                        const strictOption = settingsPanel.querySelector('#privacy-strict-option');

                        fetch(`/doctor/ui_text?lang=${lang}`)
                            .then(res => res.json())
                            .then(text => {
                                privacyLabel.textContent = text.privacy_mode || "Privacy Mode";
                                privacyHint.textContent = text.privacy_mode_hint || "Controls what sensitive information is removed before sending to AI";
                                noneOption.textContent = text.privacy_mode_none || "None (No sanitization)";
                                basicOption.textContent = text.privacy_mode_basic || "Basic (Recommended)";
                                strictOption.textContent = text.privacy_mode_strict || "Strict (Maximum privacy)";
                            })
                            .catch(err => console.error('[ComfyUI-Doctor] Failed to load privacy translations:', err));
                    };

                    // Save settings button
                    const saveBtn = settingsPanel.querySelector('#doctor-save-settings-btn');
                    saveBtn.onclick = async () => {
                        const langSelect = settingsPanel.querySelector('#doctor-language-select');

                        // Get model value from either dropdown or manual input
                        const modelValue = manualToggle.checked
                            ? modelInputManual.value
                            : modelSelect.value;

                        try {
                            // Save to ComfyUI Settings
                            app.ui.settings.setSettingValue("Doctor.General.Language", langSelect.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.Provider", providerSelect.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", baseUrlInput.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.ApiKey", apiKeyInput.value);
                            app.ui.settings.setSettingValue("Doctor.LLM.Model", modelValue);
                            app.ui.settings.setSettingValue("Doctor.Privacy.Mode", privacySelect.value);

                            // Update privacy translations on language change
                            updatePrivacyTranslations(langSelect.value);

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

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 2.5: STATISTICS PANEL (F4 Dashboard)
                    // ═══════════════════════════════════════════════════════════════
                    // PURPOSE: Display error statistics and trends
                    // UPDATED BY: doctor_ui.js:renderStatistics()
                    // STATE: Persisted in localStorage ('doctor_stats_expanded')
                    // ═══════════════════════════════════════════════════════════════
                    const statsExpanded = localStorage.getItem('doctor_stats_expanded') === 'true';
                    const statsPanel = document.createElement('details');
                    statsPanel.id = 'doctor-statistics-panel';
                    statsPanel.className = 'stats-panel doctor-sidebar-content';
                    statsPanel.open = statsExpanded;
                    statsPanel.innerHTML = `
                        <summary>📊 ${app.Doctor.getUIText('statistics_title') || 'Error Statistics'}</summary>
                        <div id="doctor-stats-content">
                            <div class="stats-grid">
                                <div class="stat-card">
                                    <div class="stat-value" id="stats-total">-</div>
                                    <div class="stat-label">${app.Doctor.getUIText('stats_total_errors') || 'Total (30d)'}</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-value" id="stats-24h">-</div>
                                    <div class="stat-label">${app.Doctor.getUIText('stats_last_24h') || 'Last 24h'}</div>
                                </div>
                            </div>
                            <div class="top-patterns" id="doctor-top-patterns">
                                <h5>🔥 ${app.Doctor.getUIText('stats_top_patterns') || 'Top Error Patterns'}</h5>
                                <div class="stats-empty">${app.Doctor.getUIText('stats_loading') || 'Loading...'}</div>
                            </div>
                            <div class="category-breakdown" id="doctor-category-breakdown" style="margin-top: 10px;">
                                <h5>📁 ${app.Doctor.getUIText('stats_categories') || 'Categories'}</h5>
                            </div>
                        </div>
                    `;
                    container.appendChild(statsPanel);

                    // Persist stats panel state
                    statsPanel.addEventListener('toggle', () => {
                        localStorage.setItem('doctor_stats_expanded', statsPanel.open);
                    });

                    // Store reference for refresh
                    doctorUI.sidebarStatsPanel = statsPanel;

                    // Initial load of statistics
                    if (typeof doctorUI.renderStatistics === 'function') {
                        doctorUI.renderStatistics();
                    }

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 3: ERROR CONTEXT AREA
                    // ═══════════════════════════════════════════════════════════════
                    // PURPOSE: Shows error suggestion when an error occurs
                    // UPDATED BY: doctor_ui.js:updateSidebarTab()
                    //
                    // DISPLAY CONTENT:
                    // - 💡 Suggestion: CONCISE actionable advice ONLY (last sentence)
                    // - Timestamp: When error occurred
                    // - Node Context: Node ID and name
                    // - ✨ Analyze with AI button
                    //
                    // IMPORTANT: Suggestion is extracted to show ONLY actionable part
                    // Full error context is sent to LLM but NOT displayed here
                    // See: doctor_ui.js Lines 240-258 for extraction logic
                    // ═══════════════════════════════════════════════════════════════
                    const errorContext = document.createElement('div');
                    errorContext.id = 'doctor-error-context';
                    errorContext.style.cssText = 'flex-shrink: 0; border-bottom: 1px solid var(--border-color, #444); display: none;';
                    container.appendChild(errorContext);

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 4: MESSAGES AREA (AI Chat Interface)
                    // ═══════════════════════════════════════════════════════════════
                    // PURPOSE: Display AI chat messages and conversation history
                    // UPDATED BY: doctor_ui.js chat methods
                    // LAYOUT: flex-1 to fill remaining space, scrollable
                    // ═══════════════════════════════════════════════════════════════
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

                    // ═══════════════════════════════════════════════════════════════
                    // SECTION 5: INPUT AREA (Sticky at Bottom)
                    // ═══════════════════════════════════════════════════════════════
                    // PURPOSE: User input for AI chat questions
                    // LAYOUT: Fixed at bottom using sticky positioning
                    // CONTROLS: Textarea + Send/Clear buttons
                    // ═══════════════════════════════════════════════════════════════
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

