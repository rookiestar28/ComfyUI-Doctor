/**
 * ComfyUI-Doctor Stats Tab Component
 * Provides statistics dashboard within the Doctor sidebar.
 * Uses Island Registry for standardized mount/unmount.
 */
import { app } from "../../../../scripts/app.js";
import { register, mount } from "../island_registry.js";
import { renderStatisticsIsland, unmountStatisticsIsland } from "../statistics-island.js";
import { isPreactEnabled } from "../preact-loader.js";

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
    `;

    container.appendChild(statsPanel);
    doctorUI.sidebarStatsPanel = statsPanel;

    if (typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }
}
