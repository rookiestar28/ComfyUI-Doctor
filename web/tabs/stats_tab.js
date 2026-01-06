import { app } from "../../../../scripts/app.js";

export function render(container) {
    const doctorUI = app.Doctor;

    // We use a <details> element to maintain compatibility with existing CSS structure,
    // but we force it open and remove height constraints for the tab view.
    const statsPanel = document.createElement('details');
    statsPanel.id = 'doctor-statistics-panel';
    statsPanel.className = 'stats-panel doctor-sidebar-content';
    statsPanel.open = true;

    // Override styles to fit tab view (full height, no scroll internal if tab scrolls)
    statsPanel.style.cssText = `
        background: transparent;
        padding: 10px;
        margin: 0;
        max-height: none; 
        height: 100%;
        border-radius: 0;
    `;

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
                <div class="stats-empty">${doctorUI.getUIText('stats_loading') || 'Loading...'}</div>
            </div>
            <div class="category-breakdown" id="doctor-category-breakdown" style="margin-top: 20px;">
                <h5>📁 ${doctorUI.getUIText('stats_categories') || 'Categories'}</h5>
            </div>
        </div>
    `;

    container.appendChild(statsPanel);

    // Store reference so doctor_ui.js can update it
    doctorUI.sidebarStatsPanel = statsPanel;

    // Initial Load
    if (typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }
}

export function onActivate() {
    const doctorUI = app.Doctor;
    // Refresh stats when tab is activated
    if (typeof doctorUI.renderStatistics === 'function') {
        doctorUI.renderStatistics();
    }
}
