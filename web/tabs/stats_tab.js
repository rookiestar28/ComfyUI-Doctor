import { app } from "../../../../scripts/app.js";
import { renderStatisticsIsland } from "../statistics-island.js";

let isPreactMode = false;

// Vanilla Fallback Logic
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

export async function render(container) {
    const doctorUI = app.Doctor;

    // Render Vanilla immediately so stats are visible even if Preact is slow/disabled.
    isPreactMode = false;
    renderVanilla(container);

    // Try Preact Island (replace vanilla when ready)
    const success = await renderStatisticsIsland(container, { uiText: doctorUI.uiText }, { replace: true });

    if (success) {
        isPreactMode = true;
        // 5B.1: Set island active flag to gate DoctorUI DOM updates
        doctorUI.statsIslandActive = true;
        doctorUI.sidebarStatsPanel = null;
    } else {
        // 5B.1: Ensure flag is false when Preact fails
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
