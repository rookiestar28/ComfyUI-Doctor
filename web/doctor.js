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

                // Auto-fetch and SHOW available models for local providers via alert
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
                                alert(`🤖 Available models (${result.models.length}):\n\n• ${modelNames}\n\n📋 Copy a model name to 'AI Model Name' field.`);
                            } else if (!result.success) {
                                alert(`⚠️ Could not fetch models:\n${result.message}\n\nMake sure the service is running.`);
                            }
                        } catch (e) {
                            alert(`⚠️ Failed to connect to ${newVal}:\n${e.message}\n\nMake sure the service is running on ${newUrl}`);
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

        // Sync initial language with backend
        try {
            await DoctorAPI.setLanguage(language);
        } catch (e) {
            console.error("[ComfyUI-Doctor] Failed to sync initial language:", e);
        }

        console.log("[ComfyUI-Doctor] Settings registered successfully");
    }
});
