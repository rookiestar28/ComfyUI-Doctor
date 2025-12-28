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

// Supported languages
const SUPPORTED_LANGUAGES = [
    { value: "en", text: "English" },
    { value: "zh_TW", text: "繁體中文" },
    { value: "zh_CN", text: "简体中文" },
    { value: "ja", text: "日本語" },
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

        // ========================================
        // Register Settings with ComfyUI Settings Panel
        // ========================================

        // --- General Settings ---

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

        // Language Selection
        app.ui.settings.addSetting({
            id: "Doctor.General.Language",
            name: "Suggestion Language",
            type: "combo",
            options: SUPPORTED_LANGUAGES,
            defaultValue: DEFAULTS.LANGUAGE,
            onChange: async (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] Language changed: ${oldVal} -> ${newVal}`);
                // Sync with backend
                try {
                    await DoctorAPI.setLanguage(newVal);
                } catch (e) {
                    console.error("[ComfyUI-Doctor] Failed to sync language with backend:", e);
                }
            },
        });

        // --- Behavior Settings ---

        // Poll Interval
        app.ui.settings.addSetting({
            id: "Doctor.Behavior.PollInterval",
            name: "Error Check Interval (ms)",
            type: "slider",
            attrs: { min: 500, max: 10000, step: 500 },
            defaultValue: DEFAULTS.POLL_INTERVAL,
            onChange: (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] Poll interval changed: ${oldVal} -> ${newVal}`);
                if (app.Doctor) {
                    app.Doctor.updatePollInterval(newVal);
                }
            },
        });

        // Auto-open on Error
        app.ui.settings.addSetting({
            id: "Doctor.Behavior.AutoOpenOnError",
            name: "Auto-open panel on error",
            type: "boolean",
            defaultValue: DEFAULTS.AUTO_OPEN_ON_ERROR,
            onChange: (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] Auto-open changed: ${oldVal} -> ${newVal}`);
                if (app.Doctor) {
                    app.Doctor.autoOpenOnError = newVal;
                }
            },
        });

        // Enable Notifications
        app.ui.settings.addSetting({
            id: "Doctor.Behavior.EnableNotifications",
            name: "Show error notifications",
            type: "boolean",
            defaultValue: DEFAULTS.ENABLE_NOTIFICATIONS,
            onChange: (newVal, oldVal) => {
                console.log(`[ComfyUI-Doctor] Notifications changed: ${oldVal} -> ${newVal}`);
                if (app.Doctor) {
                    app.Doctor.enableNotifications = newVal;
                }
            },
        });

        // --- LLM Settings ---

        // LLM Provider Preset
        app.ui.settings.addSetting({
            id: "Doctor.LLM.Provider",
            name: "AI Provider",
            type: "combo",
            options: [
                { value: "openai", text: "OpenAI" },
                { value: "deepseek", text: "DeepSeek" },
                { value: "groq", text: "Groq Cloud (LPU)" },
                { value: "gemini", text: "Google Gemini" },
                { value: "xai", text: "xAI Grok" },
                { value: "openrouter", text: "OpenRouter (Claude)" },
                { value: "ollama", text: "Ollama (Local)" },
                { value: "lmstudio", text: "LMStudio (Local)" },
                { value: "custom", text: "Custom" },
            ],
            defaultValue: "openai",
            tooltip: "Groq Cloud ≠ xAI Grok. OpenRouter supports Claude/Anthropic.",
            onChange: async (newVal) => {
                // Auto-fill Base URL
                const urlMap = {
                    "openai": "https://api.openai.com/v1",
                    "deepseek": "https://api.deepseek.com/v1",
                    "groq": "https://api.groq.com/openai/v1",
                    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
                    "xai": "https://api.x.ai/v1",
                    "openrouter": "https://openrouter.ai/api/v1",
                    "ollama": "http://localhost:11434/v1",
                    "lmstudio": "http://localhost:1234/v1",
                    "custom": ""
                };
                const newUrl = urlMap[newVal];
                if (newUrl) {
                    app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", newUrl);
                }

                // Auto-fetch and SHOW available models for local providers via custom dialog
                const isLocal = newVal === "ollama" || newVal === "lmstudio";
                if (isLocal && newUrl) {
                    setTimeout(async () => {
                        try {
                            const apiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
                            const response = await fetch('/doctor/list_models', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ base_url: newUrl, api_key: apiKey })
                            });
                            const result = await response.json();
                            if (result.success && result.models.length > 0) {
                                const modelNames = result.models.map(m => m.id).join('\n• ');
                                showSelectableDialog(
                                    `🤖 Available models (${result.models.length}):`,
                                    `• ${modelNames}`,
                                    `📋 Copy a model name to 'AI Model Name' field.`
                                );
                            } else if (!result.success) {
                                showSelectableDialog(
                                    '⚠️ Could not fetch models',
                                    result.message,
                                    'Make sure the service is running.'
                                );
                            }
                        } catch (e) {
                            showSelectableDialog(
                                `⚠️ Failed to connect to ${newVal}`,
                                e.message,
                                `Make sure the service is running on ${newUrl}`
                            );
                        }
                    }, 300);
                }
            }
        });

        app.ui.settings.addSetting({
            id: "Doctor.LLM.BaseUrl",
            name: "AI Base URL",
            type: "text",
            defaultValue: "https://api.openai.com/v1",
            tooltip: "API Endpoint. Ollama: http://localhost:11434/v1, LMStudio: http://localhost:1234/v1"
        });

        app.ui.settings.addSetting({
            id: "Doctor.LLM.ApiKey",
            name: "AI API Key",
            type: "text",
            defaultValue: "",
            tooltip: "Your API Key. Leave empty for local LLMs (Ollama/LMStudio)."
        });

        // AI Model Name - simple text input
        app.ui.settings.addSetting({
            id: "Doctor.LLM.Model",
            name: "AI Model Name",
            type: "text",
            defaultValue: "",
            tooltip: "Enter model name. Switch provider to see available models."
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

                    // Create sidebar content
                    container.innerHTML = '';
                    const content = document.createElement('div');
                    content.className = 'doctor-sidebar-content';
                    content.id = 'doctor-sidebar-tab-content';
                    content.innerHTML = `
                        <h3>
                            <span class="status-indicator" id="doctor-tab-status"></span>
                            🏥 ComfyUI Doctor
                        </h3>
                        <div id="doctor-tab-error-container">
                            <div class="no-errors">
                                <div class="icon">✅</div>
                                <div>No errors detected</div>
                                <div style="margin-top: 5px; font-size: 12px;">System running smoothly</div>
                            </div>
                        </div>
                    `;
                    container.appendChild(content);

                    // Store reference for updates
                    doctorUI.sidebarTabContent = content;
                    doctorUI.sidebarTabContainer = container;

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

