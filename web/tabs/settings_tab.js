import { app } from "../../../../scripts/app.js";
import { DoctorAPI } from "../doctor_api.js";
import { getRuntimeApiKey, setRuntimeApiKey } from "../llm_key_store.js";

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

export function render(container) {
    const doctorUI = app.Doctor;
    const DEFAULTS = { LANGUAGE: "en" }; // Minimal fallback

    // One-time CSS injection for small UI helpers (tooltips etc.)
    if (!document.getElementById('doctor-settings-tip-styles')) {
        const style = document.createElement('style');
        style.id = 'doctor-settings-tip-styles';
        style.textContent = `
            .doctor-tip {
                position: relative;
                display: inline-flex;
                align-items: center;
                flex-shrink: 0;
            }
            .doctor-tip-icon {
                width: 18px;
                height: 18px;
                border-radius: 50%;
                border: 1px solid #555;
                background: #222;
                color: #ddd;
                font-size: 12px;
                line-height: 16px;
                padding: 0;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                user-select: none;
            }
            .doctor-tip-icon:hover {
                border-color: #666;
                background: #2a2a2a;
                color: #fff;
            }
            .doctor-tip-popover {
                display: none;
                position: absolute;
                right: 0;
                top: 22px;
                background: #1a1a1a;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 10px;
                width: 280px;
                max-width: 280px;
                z-index: 1000;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            }
            .doctor-tip:hover .doctor-tip-popover,
            .doctor-tip:focus-within .doctor-tip-popover {
                display: block;
            }
            .doctor-tip-link {
                display: block;
                color: #7db7ff;
                text-decoration: underline;
                overflow-wrap: anywhere;
                word-break: normal;
                font-size: 12px;
            }
        `;
        document.head.appendChild(style);
    }

    // Get current settings values
    const currentLanguage = app.ui.settings.getSettingValue("Doctor.General.Language", DEFAULTS.LANGUAGE);
    const currentProvider = app.ui.settings.getSettingValue("Doctor.LLM.Provider", "openai");
    const currentBaseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
    // S8: API key is session-only; never read from persisted ComfyUI settings.
    const currentApiKey = getRuntimeApiKey();
    const currentModel = app.ui.settings.getSettingValue("Doctor.LLM.Model", "");
    const currentPrivacyMode = app.ui.settings.getSettingValue("Doctor.Privacy.Mode", "basic");
    // F17: Read auto-open setting with strict null check (false is a valid stored value)
    // Must handle string "false" from ComfyUI storage - same logic as doctor.js line 212
    const storedAutoOpen = app.ui.settings.getSettingValue("Doctor.Behavior.AutoOpenOnError", null);
    const currentAutoOpenOnError = storedAutoOpen === null ? true : Boolean(storedAutoOpen) && storedAutoOpen !== "false" && storedAutoOpen !== "0";

    const settingsPanel = document.createElement('div');
    settingsPanel.id = 'doctor-settings-panel';
    // Remove 'display: none' and 'background' styling that was for the collapsible panel
    settingsPanel.style.cssText = `
        padding: 15px;
        height: 100%;
        overflow-y: auto;
    `;

    // S8: Migration notice — show once per session when legacy key was imported
    const migrationNotice = (app.Doctor && app.Doctor.legacyApiKeyMigrated)
        ? `<div style="padding: 10px; margin-bottom: 15px; background: rgba(33,150,243,0.12); border: 1px solid #2196f3; border-radius: 6px; font-size: 12px; color: #90caf9; line-height: 1.5;">
            ℹ️ <strong>API Key Migrated</strong><br>
            Your previously saved API key has been moved to session memory and cleared from stored settings.<br>
            For permanent storage, use <code>DOCTOR_LLM_API_KEY</code> environment variable or the <strong>Advanced Key Store</strong> below.
           </div>`
        : '';

    settingsPanel.innerHTML = `
        ${migrationNotice}
        <h4 style="margin: 0 0 20px 0; font-size: 16px; color: #ddd; border-bottom: 1px solid #444; padding-bottom: 10px;">${doctorUI.getUIText('settings_title') || 'Settings'}</h4>
        <div style="display: flex; flex-direction: column; gap: 15px;">
            <div>
                <label style="display: block; font-size: 13px; color: #aaa; margin-bottom: 5px;">${doctorUI.getUIText('language_label')}</label>
                <select id="doctor-language-select" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                    ${SUPPORTED_LANGUAGES.map(lang =>
        `<option value="${lang.value}" ${lang.value === currentLanguage ? 'selected' : ''}>${lang.text}</option>`
    ).join('')}
                </select>
            </div>
            <div>
                <label style="display: block; font-size: 13px; color: #aaa; margin-bottom: 5px;">${doctorUI.getUIText('ai_provider_label')}</label>
                <select id="doctor-provider-select" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
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
                <label style="display: block; font-size: 13px; color: #aaa; margin-bottom: 5px;">${doctorUI.getUIText('base_url_label')}</label>
                <input type="text" id="doctor-baseurl-input" value="${currentBaseUrl}" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
            </div>
            <div>
                <label style="display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: #aaa; margin-bottom: 5px;">
                    <span>${doctorUI.getUIText('api_key_label')}</span>
                    <span class="doctor-tip">
                        <button type="button" class="doctor-tip-icon" aria-label="API key tip">?</button>
                        <div class="doctor-tip-popover" role="tooltip">
                            <div style="font-size: 12px; color: #ddd; line-height: 1.4; margin-bottom: 6px;">${doctorUI.getUIText('api_key_tip')}</div>
                            <a class="doctor-tip-link" href="https://github.com/rookiestar28/ComfyUI-Doctor" target="_blank" rel="noopener noreferrer">https://github.com/rookiestar28/ComfyUI-Doctor</a>
                        </div>
                    </span>
                </label>
                <input type="password" id="doctor-apikey-input" value="${currentApiKey}" placeholder="${doctorUI.getUIText('api_key_placeholder')}" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
                <div style="font-size: 11px; color: #888; margin-top: 4px;">⚡ Session-only — cleared on reload. Use Advanced Key Store below to persist.</div>
            </div>
            <div>
                <label style="display: block; font-size: 13px; color: #aaa; margin-bottom: 5px;">${doctorUI.getUIText('model_name_label')}</label>
                <div style="display: flex; gap: 5px; align-items: center;">
                    <select id="doctor-model-select" style="flex: 1; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;">
                        <option value="">${doctorUI.getUIText('loading_models')}</option>
                    </select>
                    <button id="doctor-refresh-models-btn" style="padding: 8px 12px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 13px;" title="Refresh model list">🔄</button>
                </div>
                <div style="margin-top: 5px;">
                    <label style="font-size: 12px; color: #888; cursor: pointer;">
                        <input type="checkbox" id="doctor-manual-model-toggle" style="margin-right: 3px;">
                        ${doctorUI.getUIText('enter_model_manually')}
                    </label>
                </div>
                <input type="text" id="doctor-model-input-manual" value="${currentModel}" placeholder="${doctorUI.getUIText('model_manual_placeholder')}" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box; margin-top: 5px; display: none;" />
            </div>
            <div style="border-top: 1px solid #444; padding-top: 15px; margin-top: 5px;">
                <label style="display: flex; align-items: center; gap: 5px; font-size: 13px; color: #aaa; margin-bottom: 5px;">
                    🔒 <span id="doctor-privacy-label">${doctorUI.getUIText('privacy_mode')}</span>
                </label>
                <select id="doctor-privacy-select" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px;">
                    <option value="none" ${currentPrivacyMode === 'none' ? 'selected' : ''} id="privacy-none-option">${doctorUI.getUIText('privacy_mode_none')}</option>
                    <option value="basic" ${currentPrivacyMode === 'basic' ? 'selected' : ''} id="privacy-basic-option">${doctorUI.getUIText('privacy_mode_basic')}</option>
                    <option value="strict" ${currentPrivacyMode === 'strict' ? 'selected' : ''} id="privacy-strict-option">${doctorUI.getUIText('privacy_mode_strict')}</option>
                </select>
                <div id="doctor-privacy-hint" style="font-size: 12px; color: #888; margin-top: 5px;">${doctorUI.getUIText('privacy_mode_hint')}</div>
            </div>
            <div style="border-top: 1px solid #444; padding-top: 15px; margin-top: 5px;">
                <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: #aaa; cursor: pointer;">
                    <input type="checkbox" id="doctor-auto-open-toggle" ${currentAutoOpenOnError ? 'checked' : ''} style="width: 16px; height: 16px; cursor: pointer;">
                    <span>${doctorUI.getUIText('auto_open_on_error_label') || 'Auto-open error report panel on new errors'}</span>
                </label>
                <div style="font-size: 12px; color: #888; margin-top: 5px; margin-left: 24px;">${doctorUI.getUIText('auto_open_on_error_hint') || 'When enabled, the right-side error report panel will automatically open when a new error is detected'}</div>
            </div>
            <button id="doctor-save-settings-btn" style="width: 100%; padding: 10px; background: #4caf50; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; font-size: 14px; margin-top: 10px;">💾 ${doctorUI.getUIText('save_settings_btn')}</button>
            <details id="doctor-key-store-section" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 15px;">
                <summary style="cursor: pointer; font-size: 13px; color: #aaa; user-select: none;">🔐 Advanced Key Store (Server-side)</summary>
                <div style="margin-top: 10px; padding: 10px; background: #1a1a1a; border-radius: 6px; border: 1px solid #333;">
                    <div style="font-size: 11px; color: #f0ad4e; margin-bottom: 10px; line-height: 1.4; padding: 8px; background: rgba(240,173,78,0.1); border-radius: 4px;">
                        ⚠️ Server store saves keys as plaintext JSON on disk (protected by OS file permissions).<br>
                        ENV vars always take higher priority. Use only in trusted localhost/single-user environments.
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: #888; margin-bottom: 4px;">Provider</label>
                            <select id="doctor-keystore-provider" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 12px;">
                                <option value="openai">OpenAI</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="deepseek">DeepSeek</option>
                                <option value="groq">Groq</option>
                                <option value="gemini">Google Gemini</option>
                                <option value="xai">xAI</option>
                                <option value="openrouter">OpenRouter</option>
                                <option value="generic">Generic (fallback)</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: #888; margin-bottom: 4px;">API Key</label>
                            <input type="password" id="doctor-keystore-key" placeholder="sk-..." style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 12px; box-sizing: border-box;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: #888; margin-bottom: 4px;">Admin Token (if configured)</label>
                            <input type="password" id="doctor-keystore-admin" placeholder="optional" style="width: 100%; padding: 6px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 12px; box-sizing: border-box;" />
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button id="doctor-keystore-save-btn" style="flex: 1; padding: 8px; background: #2196f3; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px;">💾 Save to Server</button>
                            <button id="doctor-keystore-delete-btn" style="flex: 1; padding: 8px; background: #e53935; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px;">🗑️ Delete</button>
                        </div>
                        <div id="doctor-keystore-status" style="font-size: 11px; color: #888; margin-top: 4px;"></div>
                        <div id="doctor-keystore-providers-grid" style="margin-top: 8px;"></div>
                    </div>
                </div>
            </details>
        </div>
    `;
    container.appendChild(settingsPanel);

    // --- Interaction Logic ---

    const providerSelect = settingsPanel.querySelector('#doctor-provider-select');
    const baseUrlInput = settingsPanel.querySelector('#doctor-baseurl-input');
    const modelSelect = settingsPanel.querySelector('#doctor-model-select');
    const refreshModelsBtn = settingsPanel.querySelector('#doctor-refresh-models-btn');
    const manualToggle = settingsPanel.querySelector('#doctor-manual-model-toggle');
    const modelInputManual = settingsPanel.querySelector('#doctor-model-input-manual');
    const apiKeyInput = settingsPanel.querySelector('#doctor-apikey-input');

    // Load models logic
    const loadModels = async () => {
        const baseUrl = baseUrlInput.value;
        const apiKey = apiKeyInput.value;

        if (!baseUrl) {
            modelSelect.innerHTML = '<option value="">Please set Base URL first</option>';
            return;
        }

        refreshModelsBtn.textContent = '⏳';
        refreshModelsBtn.disabled = true;
        modelSelect.disabled = true;

        try {
            const result = await DoctorAPI.listModels(baseUrl, apiKey);

            if (result.success && result.models.length > 0) {
                modelSelect.innerHTML = '';
                result.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.name;
                    modelSelect.appendChild(option);
                });

                // Restore selection
                // Logic: if manual is checked, we don't care about dropdown value.
                // But if we toggle back, we might want current value.
                // Also handle "currentModel not in list"

                // Get fresh currentModel from settings in case it changed via manual input previously
                const storedModel = app.ui.settings.getSettingValue("Doctor.LLM.Model", "");

                if (storedModel) {
                    const modelExists = result.models.find(m => m.id === storedModel);
                    if (modelExists) {
                        modelSelect.value = storedModel;
                    } else {
                        const option = document.createElement('option');
                        option.value = storedModel;
                        option.textContent = `${storedModel} (current)`;
                        option.selected = true;
                        modelSelect.insertBefore(option, modelSelect.firstChild);
                    }
                }
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

    refreshModelsBtn.onclick = () => loadModels();

    manualToggle.onchange = () => {
        const storedModel = app.ui.settings.getSettingValue("Doctor.LLM.Model", "");
        if (manualToggle.checked) {
            modelSelect.style.display = 'none';
            refreshModelsBtn.style.display = 'none';
            modelInputManual.style.display = 'block';
            modelInputManual.value = modelSelect.value || storedModel;
        } else {
            modelSelect.style.display = 'block';
            refreshModelsBtn.style.display = 'block';
            modelInputManual.style.display = 'none';
        }
    };

    // Provider Defaults access (assuming stored in doctorUI or passed in somehow)
    // We will access app.Doctor.providerDefaults if available
    providerSelect.onchange = () => {
        const defaults = doctorUI.providerDefaults || {};
        baseUrlInput.value = defaults[providerSelect.value] || "";
        if (baseUrlInput.value && !manualToggle.checked) {
            loadModels();
        }
    };

    // Auto-load
    if (currentBaseUrl && !manualToggle.checked) {
        loadModels();
    }

    // Privacy Mode Translations
    const privacySelect = settingsPanel.querySelector('#doctor-privacy-select');
    const updatePrivacyTranslations = (lang) => {
        // We can fetch from API or rely on getUIText if we refresh UI text.
        // doctorUI.loadUIText() reloads and updates this.uiText.
        // We can subscribe to that or just re-render?
        // doctor.js implementation fetched directly.
        fetch(`/doctor/ui_text?lang=${lang}`)
            .then(res => res.json())
            .then(text => {
                const map = text.text || text; // Handle structure
                const pLabel = settingsPanel.querySelector('#doctor-privacy-label');
                const pHint = settingsPanel.querySelector('#doctor-privacy-hint');
                const opts = {
                    none: settingsPanel.querySelector('#privacy-none-option'),
                    basic: settingsPanel.querySelector('#privacy-basic-option'),
                    strict: settingsPanel.querySelector('#privacy-strict-option')
                };

                if (map.privacy_mode) pLabel.textContent = map.privacy_mode;
                if (map.privacy_mode_hint) pHint.textContent = map.privacy_mode_hint;
                if (map.privacy_mode_none) opts.none.textContent = map.privacy_mode_none;
                if (map.privacy_mode_basic) opts.basic.textContent = map.privacy_mode_basic;
                if (map.privacy_mode_strict) opts.strict.textContent = map.privacy_mode_strict;
            })
            .catch(e => console.error(e));
    };

    const saveBtn = settingsPanel.querySelector('#doctor-save-settings-btn');
    const autoOpenToggle = settingsPanel.querySelector('#doctor-auto-open-toggle');
    saveBtn.onclick = async () => {
        const langSelect = settingsPanel.querySelector('#doctor-language-select');
        const modelValue = manualToggle.checked ? modelInputManual.value : modelSelect.value;
        const providerVal = providerSelect.value;
        const baseUrlVal = baseUrlInput.value;
        const apiKeyVal = apiKeyInput.value;
        const privacyVal = privacySelect.value;
        const autoOpenVal = autoOpenToggle.checked;

        try {
            app.ui.settings.setSettingValue("Doctor.General.Language", langSelect.value);
            app.ui.settings.setSettingValue("Doctor.LLM.Provider", providerVal);
            app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", baseUrlVal);
            // S8: API key is session-only — store in memory, NOT in ComfyUI settings.
            setRuntimeApiKey(apiKeyVal);
            app.ui.settings.setSettingValue("Doctor.LLM.Model", modelValue);
            app.ui.settings.setSettingValue("Doctor.Privacy.Mode", privacyVal);
            // F17: Save auto-open setting and apply immediately
            app.ui.settings.setSettingValue("Doctor.Behavior.AutoOpenOnError", autoOpenVal);
            doctorUI.autoOpenOnError = autoOpenVal;

            // Reload UI Text for new language (which also updates privacy text eventually)
            // doctorUI.updateUILanguage() -> will update info card etc.
            // We need to trigger language sync.
            await DoctorAPI.setLanguage(langSelect.value);

            // Manually update privacy fields now for immediate feedback or rely on reload?
            updatePrivacyTranslations(langSelect.value);

            // Ideally, reload the whole doctor UI or re-fetch uiText.
            // doctorUI.loadUIText() handles it.
            // Since doctorUI.language is what it uses, update it.
            doctorUI.language = langSelect.value;
            await doctorUI.loadUIText(); // Reloads and updates UI

            // Visual Feedback
            const originalText = saveBtn.textContent;
            saveBtn.textContent = '✅ Saved, please refresh the UI to apply changes';
            setTimeout(() => {
                saveBtn.textContent = originalText;
            }, 4000);

        } catch (e) {
            console.error('Failed to save settings:', e);
            saveBtn.textContent = '❌ Error';
            setTimeout(() => {
                saveBtn.textContent = '💾 Save Settings';
            }, 2000);
        }
    };

    // ---- S8: Advanced Key Store Interaction ----
    const keystoreSection = settingsPanel.querySelector('#doctor-key-store-section');
    const keystoreProviderSelect = settingsPanel.querySelector('#doctor-keystore-provider');
    const keystoreKeyInput = settingsPanel.querySelector('#doctor-keystore-key');
    const keystoreAdminInput = settingsPanel.querySelector('#doctor-keystore-admin');
    const keystoreSaveBtn = settingsPanel.querySelector('#doctor-keystore-save-btn');
    const keystoreDeleteBtn = settingsPanel.querySelector('#doctor-keystore-delete-btn');
    const keystoreStatus = settingsPanel.querySelector('#doctor-keystore-status');
    const keystoreGrid = settingsPanel.querySelector('#doctor-keystore-providers-grid');

    const SOURCE_BADGES = {
        env: { label: 'ENV', color: '#4caf50', bg: 'rgba(76,175,80,0.15)' },
        server_store: { label: 'Server', color: '#2196f3', bg: 'rgba(33,150,243,0.15)' },
        none: { label: 'None', color: '#888', bg: 'rgba(136,136,136,0.1)' },
    };

    const renderProvidersGrid = (providers) => {
        if (!keystoreGrid || !providers) return;
        const entries = Object.entries(providers);
        if (!entries.length) {
            keystoreGrid.innerHTML = '<div style="font-size: 11px; color: #666;">No providers configured.</div>';
            return;
        }
        keystoreGrid.innerHTML = `
            <div style="font-size: 11px; color: #aaa; margin-bottom: 4px;">Provider Status:</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
                ${entries.map(([id, info]) => {
            const badge = SOURCE_BADGES[info.source] || SOURCE_BADGES.none;
            return `<div style="display: flex; align-items: center; gap: 4px; padding: 3px 6px; background: ${badge.bg}; border-radius: 3px; font-size: 11px;">
                        <span style="color: #ccc;">${id}</span>
                        <span style="color: ${badge.color}; font-weight: 600;">${badge.label}</span>
                    </div>`;
        }).join('')}
            </div>`;
    };

    const loadKeystoreStatus = async () => {
        try {
            const adminToken = keystoreAdminInput?.value?.trim() || '';
            const result = await DoctorAPI.getSecretsStatus(adminToken);
            if (result.success) {
                renderProvidersGrid(result.providers);
            } else {
                keystoreGrid.innerHTML = `<div style="font-size: 11px; color: #e53935;">Failed: ${result.error || result.message || 'unknown'}</div>`;
            }
        } catch (e) {
            keystoreGrid.innerHTML = `<div style="font-size: 11px; color: #e53935;">Error: ${e.message}</div>`;
        }
    };

    // Auto-load status when section is opened
    if (keystoreSection) {
        keystoreSection.addEventListener('toggle', () => {
            if (keystoreSection.open) loadKeystoreStatus();
        });
    }

    if (keystoreSaveBtn) {
        keystoreSaveBtn.onclick = async () => {
            const provider = keystoreProviderSelect?.value;
            const key = keystoreKeyInput?.value?.trim();
            const adminToken = keystoreAdminInput?.value?.trim() || '';
            if (!provider || !key) {
                keystoreStatus.innerHTML = '<span style="color: #f0ad4e;">Provider and API Key are required.</span>';
                return;
            }
            keystoreSaveBtn.disabled = true;
            keystoreSaveBtn.textContent = '⏳ Saving...';
            try {
                const result = await DoctorAPI.saveSecret(provider, key, adminToken);
                if (result.success) {
                    keystoreStatus.innerHTML = `<span style="color: #4caf50;">✅ Saved ${provider} key to server.</span>`;
                    keystoreKeyInput.value = '';
                    await loadKeystoreStatus();
                } else {
                    keystoreStatus.innerHTML = `<span style="color: #e53935;">❌ ${result.error || result.message || 'Save failed'}</span>`;
                }
            } catch (e) {
                keystoreStatus.innerHTML = `<span style="color: #e53935;">❌ ${e.message}</span>`;
            }
            keystoreSaveBtn.disabled = false;
            keystoreSaveBtn.textContent = '💾 Save to Server';
        };
    }

    if (keystoreDeleteBtn) {
        keystoreDeleteBtn.onclick = async () => {
            const provider = keystoreProviderSelect?.value;
            const adminToken = keystoreAdminInput?.value?.trim() || '';
            if (!provider) return;
            if (!confirm(`Delete server-stored key for "${provider}"?`)) return;
            keystoreDeleteBtn.disabled = true;
            keystoreDeleteBtn.textContent = '⏳ Deleting...';
            try {
                const result = await DoctorAPI.clearSecret(provider, adminToken);
                if (result.success) {
                    keystoreStatus.innerHTML = `<span style="color: #4caf50;">✅ Deleted ${provider} key.</span>`;
                    await loadKeystoreStatus();
                } else {
                    keystoreStatus.innerHTML = `<span style="color: #e53935;">❌ ${result.error || result.message || 'Delete failed'}</span>`;
                }
            } catch (e) {
                keystoreStatus.innerHTML = `<span style="color: #e53935;">❌ ${e.message}</span>`;
            }
            keystoreDeleteBtn.disabled = false;
            keystoreDeleteBtn.textContent = '🗑️ Delete';
        };
    }
}
