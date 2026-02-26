/**
 * ComfyUI-Doctor Stats Tab Component
 * Provides statistics dashboard within the Doctor sidebar.
 * Uses Island Registry for standardized mount/unmount.
 */
import { app } from "../../../../scripts/app.js";
import { register, mount } from "../island_registry.js";
import { renderStatisticsIsland, unmountStatisticsIsland } from "../statistics-island.js";
import { isPreactEnabled } from "../preact-loader.js";
import { DoctorAPI } from "../doctor_api.js";

let isPreactMode = false;

function escapeRegexLiteral(text) {
    return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function deriveSuggestionText(ctx) {
    const raw = ctx?.suggestion;
    if (!raw) return '';
    if (typeof raw === 'string') return raw;
    if (typeof raw === 'object') return raw.message || raw.summary || '';
    return '';
}

// ═══════════════════════════════════════════════════════════════
// ISLAND REGISTRATION (5C.1)
// ═══════════════════════════════════════════════════════════════

register({
    id: 'stats',
    isEnabled: () => isPreactEnabled(),
    render: async (container, props) => {
        const success = await renderStatisticsIsland(container, props, { replace: true });
        if (!success) throw new Error('StatisticsIsland render returned false');
    },
    unmount: (container) => {
        unmountStatisticsIsland();
    },
    fallbackRender: (container, error) => {
        renderVanilla(container);
    },
    onError: (error) => {
        console.warn('[StatsTab] Island error:', error?.message);
    }
});

// ═══════════════════════════════════════════════════════════════
// TAB RENDER & ACTIVATE
// ═══════════════════════════════════════════════════════════════

export async function render(container) {
    const doctorUI = app.Doctor;

    // 5C.1: Use registry for mount - it handles Preact and fallback automatically
    isPreactMode = false;

    // Try Preact Island via Registry
    const success = await mount('stats', container, { uiText: doctorUI.uiText });

    if (success) {
        isPreactMode = true;
        // 5B.1: Set island active flag to gate DoctorUI DOM updates
        doctorUI.statsIslandActive = true;
        doctorUI.sidebarStatsPanel = null;
    } else {
        // 5B.1: Ensure flag is false when Preact fails
        // Note: fallbackRender was already called by registry
        doctorUI.statsIslandActive = false;
    }
}

export function onActivate() {
    const doctorUI = app.Doctor;

    // Refresh for Vanilla only when running in vanilla mode.
    if (!isPreactMode && typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }

    // Refresh for Preact
    // Dispatch event to trigger refresh in island
    if (isPreactMode) {
        window.dispatchEvent(new CustomEvent('doctor-refresh-stats'));
    }
}

// ═══════════════════════════════════════════════════════════════
// VANILLA RENDERER (Legacy F13 Logic)
// ═══════════════════════════════════════════════════════════════

function renderVanilla(container) {
    const doctorUI = app.Doctor;

    const statsPanel = document.createElement('details');
    statsPanel.id = 'doctor-statistics-panel';
    statsPanel.className = 'stats-panel doctor-sidebar-content';
    statsPanel.open = true;

    statsPanel.style.cssText = `
        background: transparent;
        padding: 10px;
        margin: 0;
        max-height: none; 
        height: 100%;
        border-radius: 0;
    `;

    // Align empty-state copy with E2E expectations and UX.
    const topPatternsEmptyText = doctorUI.getUIText('stats_no_data') || 'No data yet';
    statsPanel.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <summary style="pointer-events: none; opacity: 0.7; list-style: none;">📊 ${doctorUI.getUIText('statistics_title') || 'Error Statistics'}</summary>
            <div style="display: flex; gap: 6px;">
                <button id="doctor-stats-reset-btn" title="${doctorUI.getUIText('stats_reset_btn') || 'Reset'}" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px;">🗑️</button>
                <button id="doctor-stats-refresh-btn" title="Refresh" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px;">🔄</button>
            </div>
        </div>
        <div id="doctor-stats-reset-message" style="display: none; margin-bottom: 10px; padding: 8px; border-radius: 4px; font-size: 12px;"></div>
        <div id="doctor-stats-content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stats-total">-</div>
                    <div class="stat-label">${doctorUI.getUIText('stats_total_errors') || 'Total (30d)'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stats-24h">-</div>
                    <div class="stat-label">${doctorUI.getUIText('stats_last_24h') || 'Last 24h'}</div>
                </div>
            </div>
            <div class="top-patterns" id="doctor-top-patterns" style="margin-top: 20px;">
                <h5>🔥 ${doctorUI.getUIText('stats_top_patterns') || 'Top Error Patterns'}</h5>
                <div class="stats-empty">${topPatternsEmptyText}</div>
            </div>
            <div class="category-breakdown" id="doctor-category-breakdown" style="margin-top: 20px;">
                <h5>📁 ${doctorUI.getUIText('stats_categories') || 'Categories'}</h5>
            </div>
            <details id="doctor-feedback-panel" style="margin-top: 20px; border-top: 1px solid #444; padding-top: 12px;">
                <summary style="cursor: pointer; color: #ccc; font-size: 13px; user-select: none;">
                    📨 ${doctorUI.getUIText('feedback_quick_title') || 'Quick Community Feedback (GitHub PR)'}
                </summary>
                <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
                    <div style="font-size: 11px; color: #888;">
                        ${doctorUI.getUIText('feedback_quick_hint') || 'Create a sanitized feedback PR with pattern candidate + verified suggestion. Server-side GitHub token required for submit.'}
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 110px; gap: 8px;">
                        <input id="doctor-feedback-pattern-id" placeholder="pattern id" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;" />
                        <select id="doctor-feedback-category" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;">
                            <option value="generic">generic</option>
                            <option value="workflow">workflow</option>
                            <option value="memory">memory</option>
                            <option value="model_loading">model_loading</option>
                            <option value="framework">framework</option>
                            <option value="validation">validation</option>
                            <option value="type">type</option>
                            <option value="execution">execution</option>
                        </select>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 80px; gap: 8px;">
                        <textarea id="doctor-feedback-pattern-regex" rows="2" placeholder="Regex pattern" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;resize:vertical;"></textarea>
                        <input id="doctor-feedback-priority" type="number" min="1" max="100" value="60" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;" />
                    </div>
                    <textarea id="doctor-feedback-suggestion" rows="3" placeholder="Verified suggestion / fix notes" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;resize:vertical;"></textarea>
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap;">
                        <label style="font-size:11px;color:#aaa;display:flex;align-items:center;gap:6px;">
                            <input id="doctor-feedback-include-stats" type="checkbox" checked />
                            Include statistics snapshot (30d)
                        </label>
                        <button id="doctor-feedback-autofill-btn" type="button" style="padding:5px 8px;background:#333;border:1px solid #444;border-radius:4px;color:#eee;font-size:11px;cursor:pointer;">↺ Autofill from latest error</button>
                    </div>
                    <input id="doctor-feedback-admin-token" type="password" placeholder="Admin token (optional if loopback/no DOCTOR_ADMIN_TOKEN)" style="padding:6px;background:#111;border:1px solid #444;border-radius:4px;color:#eee;font-size:12px;" />
                    <div style="display:flex; gap:8px;">
                        <button id="doctor-feedback-preview-btn" style="flex:1;padding:8px;background:#2d6cdf;border:none;border-radius:4px;color:white;font-size:12px;cursor:pointer;">Preview Sanitized Payload</button>
                        <button id="doctor-feedback-submit-btn" style="flex:1;padding:8px;background:#2e7d32;border:none;border-radius:4px;color:white;font-size:12px;cursor:pointer;">Create GitHub PR</button>
                    </div>
                    <div id="doctor-feedback-status" style="font-size:11px;color:#8bc34a;"></div>
                    <pre id="doctor-feedback-preview-output" style="margin:0;max-height:220px;overflow:auto;white-space:pre-wrap;word-break:break-word;background:#161616;border:1px solid #333;border-radius:4px;padding:8px;color:#bbb;font-size:11px;">Preview output will appear here.</pre>
                </div>
            </details>
        </div>
        <!-- Trust & Health Section -->
        <div id="doctor-trust-health-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 20px;">
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
        <!-- Anonymous Telemetry Section -->
        <div id="doctor-telemetry-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 15px;">
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
    `;

    container.appendChild(statsPanel);
    doctorUI.sidebarStatsPanel = statsPanel;

    // Wire up Stats Reset button
    setupStatsResetHandler(statsPanel, doctorUI);
    // Wire up F16 community feedback panel
    setupCommunityFeedbackHandlers(statsPanel, doctorUI);

    // Wire up Trust & Health button
    setupTrustHealthHandlers(statsPanel, doctorUI);

    // Wire up Telemetry controls
    setupTelemetryHandlers(statsPanel, doctorUI);

    if (typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }
}

// ═══════════════════════════════════════════════════════════════
// STATS RESET HANDLER (R16)
// ═══════════════════════════════════════════════════════════════

function setupStatsResetHandler(container, doctorUI) {
    const resetBtn = container.querySelector('#doctor-stats-reset-btn');
    const refreshBtn = container.querySelector('#doctor-stats-refresh-btn');
    const messageDiv = container.querySelector('#doctor-stats-reset-message');

    // Wire up refresh button (in vanilla mode)
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            if (typeof doctorUI.renderStatistics === 'function') {
                doctorUI.renderStatistics();
            }
        });
    }

    if (!resetBtn) return;

    resetBtn.addEventListener('click', async () => {
        const confirmText = doctorUI.getUIText('stats_reset_confirm') || 'Reset statistics? This will clear all error history.';
        if (!confirm(confirmText)) return;

        resetBtn.disabled = true;
        const original = resetBtn.textContent;
        resetBtn.textContent = '⏳';

        try {
            const result = await DoctorAPI.resetStatistics();
            if (result.success) {
                messageDiv.style.display = 'block';
                messageDiv.style.background = 'rgba(76, 175, 80, 0.2)';
                messageDiv.style.color = '#4caf50';
                messageDiv.textContent = doctorUI.getUIText('stats_reset_success') || 'Statistics reset successfully';
                // Refresh stats
                if (typeof doctorUI.renderStatistics === 'function') {
                    doctorUI.renderStatistics();
                }
            } else {
                messageDiv.style.display = 'block';
                messageDiv.style.background = 'rgba(244, 67, 54, 0.2)';
                messageDiv.style.color = '#f44336';
                messageDiv.textContent = result.message || doctorUI.getUIText('stats_reset_failed') || 'Failed to reset statistics';
            }
        } catch (e) {
            messageDiv.style.display = 'block';
            messageDiv.style.background = 'rgba(244, 67, 54, 0.2)';
            messageDiv.style.color = '#f44336';
            messageDiv.textContent = doctorUI.getUIText('stats_reset_failed') || 'Failed to reset statistics';
        } finally {
            resetBtn.disabled = false;
            resetBtn.textContent = original;
            setTimeout(() => { messageDiv.style.display = 'none'; }, 3000);
        }
    });
}

function setupCommunityFeedbackHandlers(container, doctorUI) {
    const patternIdInput = container.querySelector('#doctor-feedback-pattern-id');
    const categorySelect = container.querySelector('#doctor-feedback-category');
    const regexInput = container.querySelector('#doctor-feedback-pattern-regex');
    const priorityInput = container.querySelector('#doctor-feedback-priority');
    const suggestionInput = container.querySelector('#doctor-feedback-suggestion');
    const includeStatsInput = container.querySelector('#doctor-feedback-include-stats');
    const adminTokenInput = container.querySelector('#doctor-feedback-admin-token');
    const autofillBtn = container.querySelector('#doctor-feedback-autofill-btn');
    const previewBtn = container.querySelector('#doctor-feedback-preview-btn');
    const submitBtn = container.querySelector('#doctor-feedback-submit-btn');
    const statusDiv = container.querySelector('#doctor-feedback-status');
    const previewOutput = container.querySelector('#doctor-feedback-preview-output');

    if (!patternIdInput || !regexInput || !suggestionInput || !previewBtn || !submitBtn) return;

    const getSeed = () => {
        const ctx = doctorUI.lastErrorData || {};
        const summary = (ctx.error_summary || ctx.last_error || ctx.error || '').trim();
        const seedLine = (summary.split('\n').find(Boolean) || 'RuntimeError').slice(0, 180);
        return {
            patternId: 'community_user_feedback',
            category: 'generic',
            regex: escapeRegexLiteral(seedLine || 'RuntimeError'),
            suggestion: deriveSuggestionText(ctx),
            errorContext: ctx,
        };
    };

    const setStatus = (text, type = 'success') => {
        if (!statusDiv) return;
        statusDiv.style.color = type === 'error' ? '#ff6b6b' : '#8bc34a';
        statusDiv.innerHTML = text || '';
    };

    const buildPayload = async () => {
        const includeStats = !!includeStatsInput?.checked;
        let statsSnapshot = null;
        if (includeStats) {
            const statsResult = await DoctorAPI.getStatistics(30);
            if (statsResult?.success) {
                statsSnapshot = { ...(statsResult.statistics || {}), time_range_days: 30 };
            }
        }
        return {
            pattern_candidate: {
                id: patternIdInput.value,
                regex: regexInput.value,
                category: categorySelect?.value || 'generic',
                priority: Number(priorityInput?.value || 60),
                notes: 'Submitted via Doctor F16 Quick Community Feedback',
            },
            suggestion_candidate: {
                language: 'en',
                message: suggestionInput.value,
            },
            error_context: (doctorUI.lastErrorData || {}),
            include_stats: includeStats,
            stats_snapshot: statsSnapshot,
        };
    };

    const fillFromLatest = () => {
        const seed = getSeed();
        if (!patternIdInput.value) patternIdInput.value = seed.patternId;
        patternIdInput.value = seed.patternId;
        categorySelect.value = seed.category;
        regexInput.value = seed.regex;
        if (seed.suggestion) suggestionInput.value = seed.suggestion;
        if (previewOutput) previewOutput.textContent = 'Preview output will appear here.';
        setStatus('');
    };

    autofillBtn?.addEventListener('click', fillFromLatest);
    fillFromLatest();

    previewBtn.addEventListener('click', async () => {
        previewBtn.disabled = true;
        submitBtn.disabled = true;
        setStatus('Previewing...');
        try {
            const payload = await buildPayload();
            const result = await DoctorAPI.previewCommunityFeedback(payload);
            if (result?.success) {
                if (previewOutput) previewOutput.textContent = JSON.stringify(result.preview, null, 2);
                const warnings = (result.warnings || []).join(' | ');
                setStatus(warnings ? `Preview ready (${warnings})` : 'Preview ready');
            } else {
                if (previewOutput) previewOutput.textContent = JSON.stringify(result?.field_errors || result || {}, null, 2);
                setStatus(result?.error || 'Preview failed', 'error');
            }
        } catch (e) {
            setStatus(e?.message || 'Preview failed', 'error');
        } finally {
            previewBtn.disabled = false;
            submitBtn.disabled = false;
        }
    });

    submitBtn.addEventListener('click', async () => {
        previewBtn.disabled = true;
        submitBtn.disabled = true;
        setStatus('Creating GitHub PR...');
        try {
            const payload = await buildPayload();
            const result = await DoctorAPI.submitCommunityFeedback(payload, adminTokenInput?.value || '');
            if (result?.success) {
                const prUrl = result?.github?.pr_url;
                if (prUrl) {
                    setStatus(`GitHub PR created: <a href="${prUrl}" target="_blank" rel="noopener noreferrer" style="color:#7db7ff;">${prUrl}</a>`);
                } else {
                    setStatus('GitHub PR created');
                }
                if (previewOutput && result.preview) previewOutput.textContent = JSON.stringify(result.preview, null, 2);
            } else {
                if (previewOutput) previewOutput.textContent = JSON.stringify(result?.field_errors || result || {}, null, 2);
                setStatus(result?.message || result?.error || 'Submit failed', 'error');
            }
        } catch (e) {
            setStatus(e?.message || 'Submit failed', 'error');
        } finally {
            previewBtn.disabled = false;
            submitBtn.disabled = false;
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// TRUST & HEALTH HANDLERS (Moved from Settings tab)
// ═══════════════════════════════════════════════════════════════

function setupTrustHealthHandlers(container, doctorUI) {
    const trustHealthBtn = container.querySelector('#doctor-trust-health-refresh-btn');
    const healthOutput = container.querySelector('#doctor-health-output');
    const pluginsOutput = container.querySelector('#doctor-plugins-output');

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
}

// ═══════════════════════════════════════════════════════════════
// TELEMETRY HANDLERS (Moved from Settings tab)
// ═══════════════════════════════════════════════════════════════

function setupTelemetryHandlers(container, doctorUI) {
    const telemetryToggle = container.querySelector('#doctor-telemetry-toggle');
    const telemetryStats = container.querySelector('#doctor-telemetry-stats');
    const telemetryViewBtn = container.querySelector('#doctor-telemetry-view-btn');
    const telemetryClearBtn = container.querySelector('#doctor-telemetry-clear-btn');
    const telemetryExportBtn = container.querySelector('#doctor-telemetry-export-btn');

    const updateToggleSlider = (toggle) => {
        const slider = toggle?.nextElementSibling;
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

    const updateTelemetryStats = async () => {
        if (!telemetryStats) return;
        try {
            const res = await fetch('/doctor/telemetry/status');
            const data = await res.json();
            if (data.success) {
                if (telemetryToggle) {
                    telemetryToggle.checked = data.enabled;
                    updateToggleSlider(telemetryToggle);
                }
                const count = data.stats?.count || 0;
                telemetryStats.textContent = `${doctorUI.getUIText('telemetry_buffer_count')?.replace('{n}', count) || `Currently buffered: ${count} events`}`;
            }
        } catch (e) {
            telemetryStats.textContent = 'Status unavailable';
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
                        ? JSON.stringify(events.slice(-20), null, 2)
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
}
