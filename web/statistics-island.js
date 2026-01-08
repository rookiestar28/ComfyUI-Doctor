/**
 * Preact component for ComfyUI-Doctor Statistics Dashboard.
 * Visualizes error trends, patterns, and resolution rates.
 * Replaces vanilla JS rendering in doctor_ui.js.
 */

import { loadPreact, isPreactEnabled } from './preact-loader.js';
import { DoctorAPI } from './doctor_api.js';
// 5C.2: Use selectors for UI text
import { getUIText, getWorkflowContext } from './doctor_selectors.js';
import { setState } from './doctor_actions.js';

let preactModules = null;
let islandMounted = false;
let currentContainer = null;

// =========================================================
// HELPERS
// =========================================================

function formatPatternName(patternId) {
    if (!patternId) return 'Unknown';
    return patternId
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase())
        .replace(/Oom/g, 'OOM')
        .replace(/Cuda/g, 'CUDA')
        .replace(/Vae/g, 'VAE')
        .replace(/Llm/g, 'LLM');
}

// =========================================================
// COMPONENTS
// =========================================================

function StatCard({ label, value, color, id }) {
    const { html } = preactModules;
    return html`
        <div class="stat-card" style="
            background: #2a2a2a;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
        ">
            <div id=${id} class="stat-value" style="font-size: 24px; font-weight: bold; color: ${color || '#eee'};">${value}</div>
            <div class="stat-label" style="font-size: 11px; color: #888; margin-top: 4px;">${label}</div>
        </div>
    `;
}

function ResolutionChart({ rates, uiText }) {
    const { html } = preactModules;
    const { resolved = 0, unresolved = 0, ignored = 0 } = rates || {};
    const total = resolved + unresolved + ignored || 1; // Avoid div by zero

    const getPercent = (val) => Math.round((val / total) * 100);

    return html`
        <div class="resolution-section" style="margin-bottom: 20px; padding: 12px; background: #222; border-radius: 6px;">
            <h5 style="margin: 0 0 10px 0; font-size: 11px; color: #aaa; text-transform: uppercase;">
                ${uiText?.stats_resolution_rate || 'Resolution Rate'}
            </h5>
            
            <!-- Simple Bar Chart instead of Pie for easier CSS -->
            <div style="display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 10px;">
                <div style="background: #4caf50; width: ${getPercent(resolved)}%"></div>
                <div style="background: #ff9800; width: ${getPercent(unresolved)}%"></div>
                <div style="background: #888888; width: ${getPercent(ignored)}%"></div>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 11px;">
                <span style="color: #4caf50;">
                    ✔ ${uiText?.stats_resolved || 'Resolved'}: <strong id="stats-resolved-count">${resolved}</strong>
                </span>
                <span style="color: #ff9800;">
                    ⚠ ${uiText?.stats_unresolved || 'Unresolved'}: <strong id="stats-unresolved-count">${unresolved}</strong>
                </span>
                <span style="color: #888;">
                    ⚪ ${uiText?.stats_ignored || 'Ignored'}: <strong id="stats-ignored-count">${ignored}</strong>
                </span>
            </div>
        </div>
    `;
}

/**
 * F15: Resolution Actions Component
 * Allows users to mark the latest error as resolved/unresolved/ignored.
 */
function ResolutionActions({ uiText, onStatusUpdate }) {
    const { html, useState, useEffect, useRef } = preactModules;

    const [timestamp, setTimestamp] = useState(null);
    const [currentStatus, setCurrentStatus] = useState(null);
    const [updating, setUpdating] = useState(false);
    const [message, setMessage] = useState(null);

    // Track the last seen timestamp to detect new errors
    const lastSeenTimestamp = useRef(null);
    // Track if user has manually set status (prevents polling from overwriting)
    const userSetStatus = useRef(false);

    // Subscribe to workflowContext for timestamp
    useEffect(() => {
        const updateFromContext = () => {
            const ctx = getWorkflowContext();
            if (ctx?.timestamp) {
                // Only reset status when a NEW error arrives (different timestamp)
                if (ctx.timestamp !== lastSeenTimestamp.current) {
                    lastSeenTimestamp.current = ctx.timestamp;
                    setTimestamp(ctx.timestamp);
                    // Only use context status for new errors, default to unresolved
                    setCurrentStatus(ctx.resolution_status || 'unresolved');
                    userSetStatus.current = false; // Reset user flag for new error
                }
                // If same timestamp and user has set status, preserve it
            } else {
                setTimestamp(null);
                setCurrentStatus(null);
                lastSeenTimestamp.current = null;
                userSetStatus.current = false;
            }
        };

        updateFromContext();

        // Poll for context updates (simpler than full subscription for now)
        const interval = setInterval(updateFromContext, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleMarkStatus = async (status) => {
        if (!timestamp || updating) return;

        setUpdating(true);
        setMessage(null);

        try {
            const result = await DoctorAPI.markResolved(timestamp, status);
            if (result.success) {
                setCurrentStatus(status);
                userSetStatus.current = true; // Prevent polling from overwriting
                const ctx = getWorkflowContext();
                if (ctx?.timestamp === timestamp) {
                    setState({ workflowContext: { ...ctx, resolution_status: status } });
                }
                setMessage({ type: 'success', text: uiText?.status_update_success || 'Status updated' });
                // Trigger stats refresh
                onStatusUpdate?.();
            } else {
                setMessage({ type: 'error', text: result.message || uiText?.status_update_failed || 'Failed to update status' });
            }
        } catch (e) {
            setMessage({ type: 'error', text: uiText?.status_update_failed || 'Failed to update status' });
        } finally {
            setUpdating(false);
            // Clear message after 3 seconds
            setTimeout(() => setMessage(null), 3000);
        }
    };

    const disabled = !timestamp || updating;

    const btnStyle = (status) => `
        padding: 6px 10px;
        border: 1px solid ${currentStatus === status ? '#4caf50' : '#555'};
        border-radius: 4px;
        background: ${currentStatus === status ? 'rgba(76, 175, 80, 0.2)' : 'transparent'};
        color: ${disabled ? '#666' : '#ccc'};
        cursor: ${disabled ? 'not-allowed' : 'pointer'};
        font-size: 11px;
        transition: all 0.2s;
    `;

    return html`
        <div id="resolution-actions" class="resolution-actions" style="margin-bottom: 20px; padding: 12px; background: #222; border-radius: 6px;">
            <h5 style="margin: 0 0 10px 0; font-size: 11px; color: #aaa; text-transform: uppercase;">
                ${uiText?.mark_as || 'Mark as'}
            </h5>
            
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button 
                    id="btn-mark-resolved"
                    onClick=${() => handleMarkStatus('resolved')}
                    disabled=${disabled}
                    style=${btnStyle('resolved')}
                    title=${disabled ? (uiText?.no_error_to_mark || 'No error to mark') : ''}
                >
                    ${uiText?.mark_resolved_btn || '✔ Resolved'}
                </button>
                <button 
                    id="btn-mark-unresolved"
                    onClick=${() => handleMarkStatus('unresolved')}
                    disabled=${disabled}
                    style=${btnStyle('unresolved')}
                    title=${disabled ? (uiText?.no_error_to_mark || 'No error to mark') : ''}
                >
                    ${uiText?.mark_unresolved_btn || '⚠ Unresolved'}
                </button>
                <button 
                    id="btn-mark-ignored"
                    onClick=${() => handleMarkStatus('ignored')}
                    disabled=${disabled}
                    style=${btnStyle('ignored')}
                    title=${disabled ? (uiText?.no_error_to_mark || 'No error to mark') : ''}
                >
                    ${uiText?.mark_ignored_btn || '⚪ Ignored'}
                </button>
            </div>
            
            ${message ? html`
                <div style="margin-top: 8px; font-size: 11px; color: ${message.type === 'success' ? '#4caf50' : '#ff6b6b'};">
                    ${message.text}
                </div>
            ` : null}
            
            ${disabled && !updating ? html`
                <div style="margin-top: 8px; font-size: 10px; color: #666; font-style: italic;">
                    ${uiText?.no_error_to_mark || 'No error to mark'}
                </div>
            ` : null}
        </div>
    `;
}

function PatternList({ patterns, uiText }) {
    const { html } = preactModules;
    // Keep output stable for UI/tests by limiting to 5 items.
    const topPatterns = (patterns || []).slice(0, 5);

    return html`
        <div id="doctor-top-patterns" class="top-patterns" style="margin-top: 20px;">
            <h5 style="margin: 0 0 10px 0; color: #eee; font-size: 13px;">
                🔥 ${uiText?.stats_top_patterns || 'Top Error Patterns'}
            </h5>
            ${(topPatterns.length === 0)
            ? html`<div class="stats-empty" style="text-align: center; padding: 20px; color: #666;">${uiText?.stats_no_data || 'No data yet'}</div>`
            : html`
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        ${topPatterns.map(p => html`
                            <div class="pattern-item" style="
                                display: flex; 
                                justify-content: space-between; 
                                align-items: center; 
                                padding: 8px; 
                                background: #2a2a2a; 
                                border-radius: 4px;
                                border-left: 3px solid #f44;
                            ">
                                <span class="pattern-name" style="font-size: 12px; color: #ddd; word-break: break-all;">
                                    ${formatPatternName(p.pattern_id)}
                                </span>
                                <span class="pattern-count" style="font-weight: bold; font-size: 12px; background: rgba(255, 68, 68, 0.2); color: #f44; padding: 2px 6px; border-radius: 10px;">
                                    ${p.count}
                                </span>
                            </div>
                        `)}
                    </div>
                `
        }
        </div>
    `;
}

function CategoryBreakdown({ breakdown, total, uiText }) {
    const { html } = preactModules;

    if (!breakdown) return null;

    const colors = {
        'memory': '#f44',
        'model_loading': '#ff9800',
        'workflow': '#2196f3',
        'framework': '#9c27b0',
        'generic': '#607d8b'
    };

    const categories = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);

    return html`
        <div id="doctor-category-breakdown" class="category-breakdown" style="margin-top: 20px;">
            <h5 style="margin: 0 0 10px 0; color: #eee; font-size: 13px;">
                📁 ${uiText?.stats_categories || 'Categories'}
            </h5>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                ${categories.map(([cat, count]) => {
        const percent = Math.round((count / (total || 1)) * 100);
        const color = colors[cat] || '#888';
        const label = uiText?.[`category_${cat}`] || cat.replace(/_/g, ' ');

        return html`
                        <div class="category-bar" style="font-size: 11px;">
                            <div class="bar-label" style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                                <span>${label}</span>
                                <span class="bar-label-count">${count} (${percent}%)</span>
                            </div>
                            <div class="bar-track" style="height: 6px; background: #333; border-radius: 3px; overflow: hidden;">
                                <div class="bar-fill" style="height: 100%; width: ${percent}%; background: ${color};"></div>
                            </div>
                        </div>
                    `;
    })}
            </div>
        </div>
    `;
}

function StatisticsIsland({ uiText }) {
    const { html, useState, useEffect } = preactModules;

    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchStats = async () => {
        setLoading(true);
        const result = await DoctorAPI.getStatistics(30);
        if (result.success) {
            setStats(result.statistics);
            setError(null);
        } else {
            setError(result.error || 'Failed to load');
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchStats();
        // Listen for error events/manual refresh
        const handleRefresh = () => fetchStats();
        window.addEventListener('doctor-refresh-stats', handleRefresh);
        return () => window.removeEventListener('doctor-refresh-stats', handleRefresh);
    }, []);

    if (loading) {
        // Return dummy containers to satisfy E2E "toBeHidden" checks if they query early
        // OR render a loading state inside the main container if it exists
        return html`
            <div id="doctor-statistics-panel" class="statistics-island" style="padding: 10px; height: 100%; color: #eee;">
                 <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h4 style="margin: 0; opacity: 0.7;">📊 ${uiText?.statistics_title || 'Error Statistics'}</h4>
                </div>
                <div id="doctor-stats-content" style="display: flex; justify-content: center; align-items: center; height: 80%; color: #888; font-style: italic;">
                    ${uiText?.stats_loading || 'Loading stats...'}
                </div>
            </div>
        `;
    }

    if (error) {
        return html`
            <div id="doctor-statistics-panel" class="statistics-island" style="padding: 10px; height: 100%; color: #eee;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h4 style="margin: 0; opacity: 0.7;">📊 ${uiText?.statistics_title || 'Error Statistics'}</h4>
                </div>
                <div id="doctor-stats-content" style="text-align: center; padding: 20px; color: #ff6b6b;">
                    <div style="font-size: 24px; margin-bottom: 10px;">⚠️</div>
                    <div>${uiText?.stats_error || 'Error loading statistics'}</div>
                    <div style="font-size: 11px; margin-top: 5px; color: #888;">${error}</div>
                    <button onClick=${fetchStats} style="margin-top:15px; background:transparent; border:1px solid #555; color:#ccc; padding:5px 10px; border-radius:4px; cursor:pointer;">Retry</button>
                </div>
            </div>
        `;
    }

    if (!stats) return null;

    return html`
        <div id="doctor-statistics-panel" class="statistics-island" style="
            padding: 10px; 
            height: 100%; 
            overflow-y: auto;
            color: #eee;
        ">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h4 style="margin: 0; display: flex; align-items: center; gap: 6px; opacity: 0.7; font-size: 14px;">
                    📊 ${uiText?.statistics_title || 'Error Statistics'}
                </h4>
                <button onClick=${fetchStats} title="Refresh" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px;">🔄</button>
            </div>

            <div id="doctor-stats-content">
                <!-- Grid -->
                <div class="stats-grid" style="
                    display: grid; 
                    grid-template-columns: 1fr 1fr; 
                    gap: 10px; 
                    margin-bottom: 20px;
                ">
                    <${StatCard} 
                        id="stats-total"
                        label=${uiText?.stats_total_errors || 'Total (30d)'} 
                        value=${stats.total_errors}
                        color="#4caf50"
                    />
                    <${StatCard} 
                        id="stats-24h"
                        label=${uiText?.stats_last_24h || 'Last 24h'} 
                        value=${stats.trend?.last_24h}
                        color="#ff9800"
                    />
                </div>

                <!-- Resolution Chart -->
                <${ResolutionChart} rates=${stats.resolution_rate} uiText=${uiText} />

                <!-- F15: Resolution Actions -->
                <${ResolutionActions} uiText=${uiText} onStatusUpdate=${fetchStats} />

                <!-- Top Patterns -->
                <${PatternList} patterns=${stats.top_patterns} uiText=${uiText} />

                <!-- Category Breakdown -->
                <${CategoryBreakdown} breakdown=${stats.category_breakdown} total=${stats.total_errors} uiText=${uiText} />
            </div>
        </div>
    `;
}

// =========================================================
// EXPORTS
// =========================================================

export async function renderStatisticsIsland(container, props = {}, options = {}) {
    if (!container) return false;
    currentContainer = container;

    if (!isPreactEnabled()) {
        console.warn('Preact is disabled.');
        return false;
    }

    try {
        preactModules = await loadPreact();
        const { render, html } = preactModules;
        if (options.replace) {
            container.innerHTML = '';
        }
        render(html`<${StatisticsIsland} ...${props} />`, container);
        islandMounted = true;
        return true;
    } catch (e) {
        console.error("StatisticsIsland render failed:", e);
        return false;
    }
}

export function unmountStatisticsIsland() {
    if (islandMounted && currentContainer && preactModules) {
        preactModules.render(null, currentContainer);
        islandMounted = false;
        currentContainer = null;
    }
}
