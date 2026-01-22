/**
 * ComfyUI-Doctor Extension Entry Point
 * Registers settings with ComfyUI's settings panel and initializes the Doctor UI.
 */
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { DoctorUI } from "./doctor_ui.js";
import { DoctorAPI } from "./doctor_api.js";
import { isPreactEnabled, loadPreact, getLoadError } from "./preact-loader.js";
import { tabRegistry, TabManager } from "./doctor_tabs.js";
import * as ChatTab from "./tabs/chat_tab.js";
import * as StatsTab from "./tabs/stats_tab.js";
import * as SettingsTab from "./tabs/settings_tab.js";
// R5: Error Boundaries
import { installGlobalErrorHandlers } from "./global_error_handler.js";

// ═══════════════════════════════════════════════════════════════════════════
// A7: PREACT ISLANDS FEATURE FLAG
// ═══════════════════════════════════════════════════════════════════════════
// Controls whether Preact-based UI components (islands) are loaded.
// When disabled, the extension uses pure Vanilla JS fallback UI.
//
// How to disable: localStorage.setItem('doctor_preact_disabled', 'true')
// Last Modified: 2026-01-05 (A7 Phase 2)
// ═══════════════════════════════════════════════════════════════════════════
const PREACT_ISLANDS_ENABLED = localStorage.getItem('doctor_preact_disabled') !== 'true' && isPreactEnabled();

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

// ═══════════════════════════════════════════════════════════════════════════
// R5: ERROR BOUNDARIES FEATURE FLAG
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Check if Error Boundaries feature is enabled.
 * Used to gate global error handler installation and CSS injection.
 */
function isErrorBoundariesEnabled() {
    try {
        const setting = app?.ui?.settings?.getSettingValue?.(
            'Doctor.General.ErrorBoundaries',
            true // Default: enabled
        );
        return setting !== false;
    } catch (err) {
        return true; // Default to enabled if settings unavailable
    }
}

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

// ComfyUI Settings → About panel badges (ComfyUI_frontend AboutPanel.vue)
const DOCTOR_REPO_URL = "https://github.com/rookiestar28/ComfyUI-Doctor";
const DOCTOR_ABOUT_BADGES = [
    {
        label: "ComfyUI Doctor",
        url: DOCTOR_REPO_URL,
        icon: "pi pi-github",
    },
];

app.registerExtension({
    name: "ComfyUI-Doctor",
    aboutPageBadges: DOCTOR_ABOUT_BADGES,

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

        // R5: Error Boundaries Feature Flag
        app.ui.settings.addSetting({
            id: "Doctor.General.ErrorBoundaries",
            name: "Enable Error Boundaries (requires restart)",
            type: "boolean",
            defaultValue: true,
            onChange: (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] ErrorBoundaries changed: ${oldVal} -> ${newVal}`);
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
        app.Doctor.providerDefaults = PROVIDER_DEFAULTS;

        // NOTE (UI tooltip): Wait for UI text before sidebar registration to avoid "[Missing]" labels.
        // Do not remove this await unless registerSidebarTab no longer uses getUIText().
        if (doctorUI.uiTextReady) {
            await doctorUI.uiTextReady;
        }

        // Populate Doctor version for ComfyUI Settings → About badge (best effort).
        // Note: AboutPanel badges are computed and may not be reactive to later updates.
        // Updating immediately after uiTextReady should be early enough for typical usage.
        try {
            const meta = doctorUI?.meta;
            if (meta?.repository) DOCTOR_ABOUT_BADGES[0].url = meta.repository;
            if (meta?.version && meta.version !== "unknown") {
                DOCTOR_ABOUT_BADGES[0].label = `ComfyUI Doctor v${meta.version}`;
            }
        } catch (e) {
            // no-op: keep fallback badge label/url
        }

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
                                max-height: 200px;
                                overflow-y: auto;
                                flex-shrink: 0;
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

                        // F13: Tab System Styles
                        const tabStyle = document.createElement('style');
                        tabStyle.textContent = `
                            .doctor-tab-bar {
                                display: flex;
                                border-bottom: 1px solid var(--border-color, #444);
                                background: rgba(0,0,0,0.2);
                            }
                            .doctor-tab-button {
                                flex: 1;
                                text-align: center;
                                padding: 10px;
                                cursor: pointer;
                                color: #888;
                                border-bottom: 2px solid transparent;
                                transition: all 0.2s;
                            }
                            .doctor-tab-button:hover {
                                background: rgba(255,255,255,0.05);
                                color: #ddd;
                            }
                            .doctor-tab-button.active {
                                color: #4caf50;
                                border-bottom-color: #4caf50;
                                background: rgba(76, 175, 80, 0.1);
                            }
                            .doctor-tab-pane {
                                height: 100%;
                                display: none;
                                overflow: hidden;
                                /* Ensure flex children can fill height */
                                box-sizing: border-box;
                            }
                            .doctor-tab-pane[style*="display: block"] {
                                display: flex !important;
                                flex-direction: column;
                            }
                        `;
                        document.head.appendChild(tabStyle);
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

                    // Create sidebar content - TAB BASED STRUCTURE (F13)
                    container.innerHTML = '';
                    container.style.cssText = 'display: flex; flex-direction: column; height: 100%; background: var(--bg-color, #1a1a2e);';

                    // 1. Header
                    const header = document.createElement('div');
                    header.style.cssText = 'padding: 12px 15px; border-bottom: 1px solid var(--border-color, #444); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;';
                    header.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="status-indicator" id="doctor-tab-status" style="width: 10px; height: 10px; border-radius: 50%; background: #4caf50; display: inline-block;"></span>
                            <span style="font-size: 16px; font-weight: bold; color: var(--fg-color, #eee);">🏥 ${app.Doctor.getUIText('sidebar_doctor_title')}</span>
                        </div>
                    `;
                    container.appendChild(header);

                    // 2. Tab Bar
                    const tabBar = document.createElement('div');
                    tabBar.id = 'doctor-tab-bar';
                    tabBar.className = 'doctor-tab-bar';
                    container.appendChild(tabBar);

                    // 3. Tab Content
                    const content = document.createElement('div');
                    content.id = 'doctor-tab-content';
                    // ⚠️ CRITICAL: min-height: 0 required for nested flex scrolling
                    content.style.cssText = 'flex: 1 1 0; overflow: hidden; position: relative; min-height: 0;';
                    container.appendChild(content);

                    // Register Tabs
                    const getTxt = (k, f) => app.Doctor.getUIText(k) || f;

                    try {
                        console.log("[ComfyUI-Doctor] Registering Chat tab...");
                        tabRegistry.register({
                            id: 'chat',
                            icon: '💬',
                            label: getTxt('tab_chat', 'Chat'),
                            order: 10,
                            render: ChatTab.render,
                            onActivate: ChatTab.onActivate
                        });

                        console.log("[ComfyUI-Doctor] Registering Stats tab...");
                        tabRegistry.register({
                            id: 'stats',
                            icon: '📊',
                            label: getTxt('tab_stats', 'Stats'),
                            order: 20,
                            render: StatsTab.render,
                            onActivate: StatsTab.onActivate
                        });

                        console.log("[ComfyUI-Doctor] Registering Settings tab...");
                        tabRegistry.register({
                            id: 'settings',
                            icon: '⚙️',
                            label: getTxt('tab_settings', 'Settings'),
                            order: 30,
                            render: SettingsTab.render
                        });

                        console.log("[ComfyUI-Doctor] Initializing TabManager...");
                        // Init Manager - pass DOM elements directly (not IDs)
                        // ⚠️ CRITICAL: document.getElementById() fails in ComfyUI's Vue context
                        const manager = new TabManager(tabRegistry, content, tabBar);
                        manager.init();
                        console.log("[ComfyUI-Doctor] ✅ TabManager initialized successfully");

                        // Store references
                        doctorUI.sidebarTabContainer = content;
                        doctorUI.tabManager = manager;

                        // Update status dot if error exists
                        if (doctorUI.lastErrorData) {
                            const statusDot = header.querySelector('#doctor-tab-status');
                        }
                    } catch (tabError) {
                        console.error("[ComfyUI-Doctor] ❌ Tab initialization failed:", tabError);
                        // Show error message in sidebar content
                        content.innerHTML = `
                            <div style="padding: 20px; color: #ff5555;">
                                <h4>⚠️ Tab Initialization Error</h4>
                                <p style="font-size: 12px; white-space: pre-wrap;">${tabError.message}</p>
                                <p style="font-size: 10px; color: #888;">Check browser console for details</p>
                            </div>
                        `;
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

        // ═══════════════════════════════════════════════════════════════════
        // R5: ERROR BOUNDARIES INITIALIZATION
        // ═══════════════════════════════════════════════════════════════════
        if (isErrorBoundariesEnabled()) {
            // 1. Inject Error Boundary CSS
            if (!document.getElementById('doctor-error-boundary-styles')) {
                const link = document.createElement('link');
                link.id = 'doctor-error-boundary-styles';
                link.rel = 'stylesheet';
                link.href = new URL('./error_boundary.css', import.meta.url).href;
                document.head.appendChild(link);
            }

            // 2. Install global error handlers
            installGlobalErrorHandlers();

            console.log('[ComfyUI-Doctor] ✅ Error boundaries active');
        } else {
            console.log('[ComfyUI-Doctor] Error boundaries disabled by user setting');
        }
    }
});
