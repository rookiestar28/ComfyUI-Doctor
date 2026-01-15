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
        <summary style="pointer-events: none; opacity: 0.7; margin-bottom: 15px;">📊 ${doctorUI.getUIText('statistics_title') || 'Error Statistics'}</summary>
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

    // Wire up Trust & Health button
    setupTrustHealthHandlers(statsPanel, doctorUI);

    // Wire up Telemetry controls
    setupTelemetryHandlers(statsPanel, doctorUI);

    if (typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }
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
