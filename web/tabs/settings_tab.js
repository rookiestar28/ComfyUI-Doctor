import { app } from "../../../../scripts/app.js";
import { DoctorAPI } from "../doctor_api.js";

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

    // Get current settings values
    const currentLanguage = app.ui.settings.getSettingValue("Doctor.General.Language", DEFAULTS.LANGUAGE);
    const currentProvider = app.ui.settings.getSettingValue("Doctor.LLM.Provider", "openai");
    const currentBaseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
    const currentApiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
    const currentModel = app.ui.settings.getSettingValue("Doctor.LLM.Model", "");
    const currentPrivacyMode = app.ui.settings.getSettingValue("Doctor.Privacy.Mode", "basic");

    const settingsPanel = document.createElement('div');
    settingsPanel.id = 'doctor-settings-panel';
    // Remove 'display: none' and 'background' styling that was for the collapsible panel
    settingsPanel.style.cssText = `
        padding: 15px;
        height: 100%;
        overflow-y: auto;
    `;

    settingsPanel.innerHTML = `
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
                <label style="display: block; font-size: 13px; color: #aaa; margin-bottom: 5px;">${doctorUI.getUIText('api_key_label')}</label>
                <input type="password" id="doctor-apikey-input" value="${currentApiKey}" placeholder="${doctorUI.getUIText('api_key_placeholder')}" style="width: 100%; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee; font-size: 13px; box-sizing: border-box;" />
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
            <div id="doctor-trust-health-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 5px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                    <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #aaa;">
                        🛡️ <span>${doctorUI.getUIText('trust_health_title') || 'Trust & Health'}</span>
                    </div>
                    <button id="doctor-trust-health-refresh-btn" style="padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 12px;" title="${doctorUI.getUIText('refresh_btn') || 'Refresh'}">🔄</button>
                </div>
                <div id="doctor-health-output" style="margin-top: 10px; font-size: 12px; color: #bbb; line-height: 1.4;">
                    ${doctorUI.getUIText('trust_health_hint') || 'Fetch /doctor/health and plugin trust report (scan-only).'}
                </div>
                <div id="doctor-plugins-output" style="margin-top: 10px; font-size: 12px; color: #bbb; line-height: 1.4;"></div>
            </div>
            <div id="doctor-telemetry-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 5px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                    <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #aaa;">
                        📊 <span>${doctorUI.getUIText('telemetry_label') || 'Anonymous Telemetry'}</span>
                    </div>
                    <label class="doctor-toggle" style="position: relative; display: inline-block; width: 40px; height: 22px;">
                        <input type="checkbox" id="doctor-telemetry-toggle" style="opacity: 0; width: 0; height: 0;">
                        <span class="doctor-toggle-slider" style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #444; transition: .3s; border-radius: 22px;"></span>
                    </label>
                </div>
                <div style="font-size: 12px; color: #888; margin-top: 5px;">${doctorUI.getUIText('telemetry_description') || 'Send anonymous usage data to help improve Doctor'}</div>
                <div id="doctor-telemetry-stats" style="font-size: 11px; color: #666; margin-top: 5px;"></div>
                <div style="display: flex; gap: 8px; margin-top: 10px;">
                    <button id="doctor-telemetry-view-btn" style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${doctorUI.getUIText('telemetry_view_buffer') || 'View Buffer'}</button>
                    <button id="doctor-telemetry-clear-btn" style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${doctorUI.getUIText('telemetry_clear_all') || 'Clear All'}</button>
                    <button id="doctor-telemetry-export-btn" style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${doctorUI.getUIText('telemetry_export') || 'Export'}</button>
                </div>
                <div style="font-size: 11px; color: #666; margin-top: 5px;">${doctorUI.getUIText('telemetry_upload_none') || 'Upload destination: None (local only)'}</div>
            </div>
            <button id="doctor-save-settings-btn" style="width: 100%; padding: 10px; background: #4caf50; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; font-size: 14px; margin-top: 10px;">💾 ${doctorUI.getUIText('save_settings_btn')}</button>
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
    const trustHealthBtn = settingsPanel.querySelector('#doctor-trust-health-refresh-btn');
    const healthOutput = settingsPanel.querySelector('#doctor-health-output');
    const pluginsOutput = settingsPanel.querySelector('#doctor-plugins-output');

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

    const renderTrustBadge = (trust) => {
        const map = {
            trusted: { fg: '#c8f7c5', bg: 'rgba(76, 175, 80, 0.18)', border: 'rgba(76, 175, 80, 0.35)' },
            unsigned: { fg: '#ffe5b4', bg: 'rgba(255, 193, 7, 0.14)', border: 'rgba(255, 193, 7, 0.35)' },
            untrusted: { fg: '#ffd6d6', bg: 'rgba(244, 67, 54, 0.14)', border: 'rgba(244, 67, 54, 0.35)' },
            blocked: { fg: '#ffbdbd', bg: 'rgba(244, 67, 54, 0.20)', border: 'rgba(244, 67, 54, 0.45)' },
        };
        const s = map[trust] || { fg: '#ddd', bg: 'rgba(158,158,158,0.10)', border: 'rgba(158,158,158,0.25)' };
        const el = document.createElement('span');
        el.textContent = trust || 'unknown';
        el.style.cssText = `display:inline-block; padding:2px 6px; border-radius:999px; font-size:11px; border:1px solid ${s.border}; background:${s.bg}; color:${s.fg};`;
        return el;
    };

    const refreshTrustHealth = async () => {
        if (!trustHealthBtn) return;

        trustHealthBtn.disabled = true;
        const original = trustHealthBtn.textContent;
        trustHealthBtn.textContent = '⏳';

        try {
            // Health
            const healthRes = await DoctorAPI.getHealth();
            if (healthRes?.success && healthRes.health) {
                const h = healthRes.health;
                const pipelineStatus = h.last_analysis?.pipeline_status || 'unknown';
                const ssrfBlocked = h.ssrf?.blocked_total ?? h.ssrf?.blocked ?? 0;
                const dropped = h.logger?.dropped_messages ?? 0;
                healthOutput.textContent = `Health: pipeline_status=${pipelineStatus}, ssrf_blocked=${ssrfBlocked}, dropped_logs=${dropped}`;
            } else {
                const msg = healthRes?.error || 'Failed to load /doctor/health';
                healthOutput.textContent = `Health: ${msg}`;
            }

            // Plugins
            const pluginsRes = await DoctorAPI.getPluginsReport();
            pluginsOutput.innerHTML = '';
            if (pluginsRes?.success && pluginsRes.plugins) {
                const payload = pluginsRes.plugins;
                const header = document.createElement('div');
                header.style.cssText = 'color:#aaa; font-size:12px; margin-bottom:6px;';
                const trustCounts = payload.trust_counts || {};
                const enabled = payload.config?.enabled ? 'enabled' : 'disabled';
                const allowlistCount = payload.config?.allowlist_count ?? 0;
                const sigRequired = payload.config?.signature_required ? 'required' : 'optional';
                header.textContent = `Plugins: ${enabled}, allowlist=${allowlistCount}, signature=${sigRequired}`;
                pluginsOutput.appendChild(header);

                const list = document.createElement('div');
                list.style.cssText = 'display:flex; flex-direction:column; gap:6px;';

                const items = payload.plugins || [];
                if (!items.length) {
                    const empty = document.createElement('div');
                    empty.style.cssText = 'color:#888; font-size:12px;';
                    empty.textContent = doctorUI.getUIText('plugins_none_found') || 'No plugins found.';
                    list.appendChild(empty);
                } else {
                    items.slice(0, 10).forEach((p) => {
                        const row = document.createElement('div');
                        row.style.cssText = 'display:flex; align-items:center; gap:8px; padding:6px 8px; border:1px solid #333; border-radius:6px; background:#161616;';

                        const name = document.createElement('div');
                        name.style.cssText = 'flex:1; min-width:0;';
                        const title = document.createElement('div');
                        title.style.cssText = 'font-size:12px; color:#ddd; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;';
                        title.textContent = p.plugin_id || p.file || 'unknown';
                        const sub = document.createElement('div');
                        sub.style.cssText = 'font-size:11px; color:#888; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;';
                        sub.textContent = `${p.file || ''}${p.reason ? ` • ${p.reason}` : ''}`;
                        name.appendChild(title);
                        name.appendChild(sub);

                        row.appendChild(renderTrustBadge(p.trust));
                        row.appendChild(name);
                        list.appendChild(row);
                    });
                }

                pluginsOutput.appendChild(list);

                const summary = document.createElement('div');
                summary.style.cssText = 'margin-top:8px; font-size:11px; color:#888;';
                summary.textContent = `Trust counts: ${Object.entries(trustCounts).map(([k, v]) => `${k}=${v}`).join(', ') || 'none'}`;
                pluginsOutput.appendChild(summary);
            } else {
                const msg = pluginsRes?.error || 'Failed to load /doctor/plugins';
                pluginsOutput.textContent = `Plugins: ${msg}`;
            }
        } catch (e) {
            healthOutput.textContent = `Health: ${e?.message || 'error'}`;
            pluginsOutput.textContent = '';
        } finally {
            trustHealthBtn.textContent = original;
            trustHealthBtn.disabled = false;
        }
    };

    if (trustHealthBtn) {
        trustHealthBtn.onclick = () => refreshTrustHealth();
    }

    // ---- Telemetry Controls ----
    const telemetryToggle = settingsPanel.querySelector('#doctor-telemetry-toggle');
    const telemetryStats = settingsPanel.querySelector('#doctor-telemetry-stats');
    const telemetryViewBtn = settingsPanel.querySelector('#doctor-telemetry-view-btn');
    const telemetryClearBtn = settingsPanel.querySelector('#doctor-telemetry-clear-btn');
    const telemetryExportBtn = settingsPanel.querySelector('#doctor-telemetry-export-btn');

    const updateTelemetryStats = async () => {
        try {
            const res = await fetch('/doctor/telemetry/status');
            const data = await res.json();
            if (data.success) {
                telemetryToggle.checked = data.enabled;
                updateToggleSlider(telemetryToggle);
                const count = data.stats?.count || 0;
                const oldest = data.stats?.oldest ? new Date(data.stats.oldest).toLocaleDateString() : '-';
                telemetryStats.textContent = `${doctorUI.getUIText('telemetry_buffer_count')?.replace('{n}', count) || `Currently buffered: ${count} events`}`;
            }
        } catch (e) {
            telemetryStats.textContent = 'Status unavailable';
        }
    };

    const updateToggleSlider = (toggle) => {
        const slider = toggle.nextElementSibling;
        if (slider) {
            if (toggle.checked) {
                slider.style.background = '#4caf50';
                slider.innerHTML = '<span style="position:absolute;left:4px;top:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.3s;transform:translateX(18px);"></span>';
            } else {
                slider.style.background = '#444';
                slider.innerHTML = '<span style="position:absolute;left:4px;top:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.3s;"></span>';
            }
        }
    };

    if (telemetryToggle) {
        telemetryToggle.onchange = async () => {
            try {
                const res = await fetch('/doctor/telemetry/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: telemetryToggle.checked })
                });
                const data = await res.json();
                telemetryToggle.checked = data.enabled;
                updateToggleSlider(telemetryToggle);
                updateTelemetryStats();
            } catch (e) {
                console.error('[ComfyUI-Doctor] Telemetry toggle error:', e);
            }
        };
        updateToggleSlider(telemetryToggle);
    }

    if (telemetryViewBtn) {
        telemetryViewBtn.onclick = async () => {
            try {
                const res = await fetch('/doctor/telemetry/buffer');
                const data = await res.json();
                if (data.success) {
                    const events = data.events || [];
                    const content = events.length > 0
                        ? JSON.stringify(events.slice(-20), null, 2) // Show last 20
                        : 'No events buffered';
                    alert(`Telemetry Buffer (${events.length} events):\n\n${content.slice(0, 2000)}`);
                }
            } catch (e) {
                alert('Failed to load buffer');
            }
        };
    }

    if (telemetryClearBtn) {
        telemetryClearBtn.onclick = async () => {
            if (!confirm(doctorUI.getUIText('telemetry_confirm_clear') || 'Clear all telemetry data?')) {
                return;
            }
            try {
                const res = await fetch('/doctor/telemetry/clear', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    telemetryClearBtn.textContent = '✅';
                    setTimeout(() => {
                        telemetryClearBtn.textContent = doctorUI.getUIText('telemetry_clear_all') || 'Clear All';
                    }, 1500);
                    updateTelemetryStats();
                }
            } catch (e) {
                telemetryClearBtn.textContent = '❌';
                setTimeout(() => {
                    telemetryClearBtn.textContent = doctorUI.getUIText('telemetry_clear_all') || 'Clear All';
                }, 1500);
            }
        };
    }

    if (telemetryExportBtn) {
        telemetryExportBtn.onclick = async () => {
            try {
                const res = await fetch('/doctor/telemetry/export');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'telemetry_export.json';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                telemetryExportBtn.textContent = '✅';
                setTimeout(() => {
                    telemetryExportBtn.textContent = doctorUI.getUIText('telemetry_export') || 'Export';
                }, 1500);
            } catch (e) {
                telemetryExportBtn.textContent = '❌';
                setTimeout(() => {
                    telemetryExportBtn.textContent = doctorUI.getUIText('telemetry_export') || 'Export';
                }, 1500);
            }
        };
    }

    // Load telemetry status on init
    updateTelemetryStats();

    const saveBtn = settingsPanel.querySelector('#doctor-save-settings-btn');
    saveBtn.onclick = async () => {
        const langSelect = settingsPanel.querySelector('#doctor-language-select');
        const modelValue = manualToggle.checked ? modelInputManual.value : modelSelect.value;
        const providerVal = providerSelect.value;
        const baseUrlVal = baseUrlInput.value;
        const apiKeyVal = apiKeyInput.value;
        const privacyVal = privacySelect.value;

        try {
            app.ui.settings.setSettingValue("Doctor.General.Language", langSelect.value);
            app.ui.settings.setSettingValue("Doctor.LLM.Provider", providerVal);
            app.ui.settings.setSettingValue("Doctor.LLM.BaseUrl", baseUrlVal);
            app.ui.settings.setSettingValue("Doctor.LLM.ApiKey", apiKeyVal);
            app.ui.settings.setSettingValue("Doctor.LLM.Model", modelValue);
            app.ui.settings.setSettingValue("Doctor.Privacy.Mode", privacyVal);

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
}
