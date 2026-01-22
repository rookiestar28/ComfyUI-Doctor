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
// R5: Error Boundaries
import { createErrorBoundaryAsync } from './ErrorBoundary.js';

let preactModules = null;
let islandMounted = false;
let currentContainer = null;

// =========================================================
// R5: ERROR BOUNDARIES FEATURE FLAG
// =========================================================

/**
 * Check if Error Boundaries feature is enabled.
 * Must match the check in doctor.js.
 */
function isErrorBoundariesEnabled() {
    try {
        const setting = window.app?.ui?.settings?.getSettingValue?.(
            'Doctor.General.ErrorBoundaries',
            true // Default: enabled
        );
        return setting !== false;
    } catch (err) {
        return true; // Default to enabled if settings unavailable
    }
}

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

/**
 * F14: Diagnostics Section Component
 * Proactive health checks and intent signature display
 */
function DiagnosticsSection({ uiText, onDiagnosticsRun }) {
    const { html, useState, useCallback } = preactModules;

    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [expanded, setExpanded] = useState({});  // Track expanded issues

    // Fetch last report on mount
    const fetchLastReport = useCallback(async () => {
        try {
            const res = await fetch('/doctor/health_report');
            const data = await res.json();
            if (data.success && data.report) {
                setReport(data.report);
            }
        } catch (e) {
            console.warn('[DiagnosticsSection] Failed to fetch last report:', e);
        }
    }, []);

    // Run diagnostics
    const runDiagnostics = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // Get workflow from ComfyUI
            const workflow = window.app?.graph?.serialize?.() || {};

            const res = await fetch('/doctor/health_check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow,
                    scope: 'manual',
                    options: { include_intent: true, max_paths: 50 }
                })
            });
            const data = await res.json();
            if (data.success) {
                setReport(data.report);
                onDiagnosticsRun?.();
            } else {
                setError(data.error || 'Failed to run diagnostics');
            }
        } catch (e) {
            setError(e.message || 'Failed to run diagnostics');
        } finally {
            setLoading(false);
        }
    }, [onDiagnosticsRun]);

    // Load last report on component mount
    preactModules.useEffect(() => {
        fetchLastReport();
    }, [fetchLastReport]);

    // Locate node on canvas
    const handleLocateNode = useCallback((nodeId) => {
        // Doctor UI is at app.Doctor (see doctor.js line 223)
        if (nodeId != null && window.app?.Doctor?.locateNodeOnCanvas) {
            window.app.Doctor.locateNodeOnCanvas(nodeId);
        }
    }, []);

    // Acknowledge issue
    const handleAckIssue = useCallback(async (reportId, issueId, status) => {
        try {
            const res = await fetch('/doctor/health_ack', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report_id: reportId, issue_id: issueId, status })
            });
            const data = await res.json();
            if (data.success) {
                // Update local state
                setReport(prev => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        issues: prev.issues.map(issue =>
                            issue.issue_id === issueId ? { ...issue, status } : issue
                        )
                    };
                });
            }
        } catch (e) {
            console.error('[DiagnosticsSection] Ack error:', e);
        }
    }, []);

    // Toggle issue expansion
    const toggleExpand = useCallback((issueId) => {
        setExpanded(prev => ({ ...prev, [issueId]: !prev[issueId] }));
    }, []);

    // Health score badge color
    const getScoreColor = (score) => {
        if (score >= 80) return '#4caf50';
        if (score >= 50) return '#ff9800';
        return '#f44336';
    };

    // Severity colors
    const severityColors = {
        critical: '#f44336',
        warning: '#ff9800',
        info: '#2196f3'
    };

    // Severity icons
    const severityIcons = {
        critical: '🔴',
        warning: '🟡',
        info: '🔵'
    };

    return html`
        <div id="doctor-diagnostics-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 20px;">
            <!-- Header -->
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #aaa;">
                    🩺 <span>${uiText?.diagnostics_title || 'Diagnostics'}</span>
                </div>
                <button
                    id="doctor-run-diagnostics-btn"
                    onClick=${runDiagnostics}
                    disabled=${loading}
                    style="padding: 6px 12px; background: ${loading ? '#333' : '#2563eb'}; border: 1px solid ${loading ? '#444' : '#3b82f6'}; border-radius: 4px; color: #fff; cursor: ${loading ? 'not-allowed' : 'pointer'}; font-size: 12px; transition: all 0.2s;"
                >
                    ${loading ? '⏳ ' + (uiText?.diagnostics_running || 'Running...') : '▶ ' + (uiText?.diagnostics_run_btn || 'Run Diagnostics')}
                </button>
            </div>

            ${error ? html`
                <div style="padding: 10px; background: rgba(244, 67, 54, 0.1); border: 1px solid rgba(244, 67, 54, 0.3); border-radius: 4px; color: #ff6b6b; font-size: 12px; margin-bottom: 12px;">
                    ⚠️ ${error}
                </div>
            ` : null}

            ${report ? html`
                <!-- Health Score & Summary -->
                <div style="display: flex; gap: 12px; margin-bottom: 15px;">
                    <!-- Score Badge -->
                    <div style="flex: 0 0 80px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px; background: #1a1a1a; border-radius: 8px; border: 2px solid ${getScoreColor(report.health_score)};">
                        <div id="diagnostics-health-score" style="font-size: 28px; font-weight: bold; color: ${getScoreColor(report.health_score)};">
                            ${report.health_score}
                        </div>
                        <div style="font-size: 10px; color: #888; text-transform: uppercase;">
                            ${uiText?.diagnostics_score || 'Health'}
                        </div>
                    </div>

                    <!-- Counts -->
                    <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 6px;">
                        <div style="display: flex; gap: 12px; font-size: 12px;">
                            <span id="diagnostics-critical-count" style="color: ${severityColors.critical};">
                                ${severityIcons.critical} ${uiText?.diagnostics_critical || 'Critical'}: <strong>${report.counts?.critical || 0}</strong>
                            </span>
                            <span id="diagnostics-warning-count" style="color: ${severityColors.warning};">
                                ${severityIcons.warning} ${uiText?.diagnostics_warning || 'Warning'}: <strong>${report.counts?.warning || 0}</strong>
                            </span>
                            <span id="diagnostics-info-count" style="color: ${severityColors.info};">
                                ${severityIcons.info} ${uiText?.diagnostics_info || 'Info'}: <strong>${report.counts?.info || 0}</strong>
                            </span>
                        </div>
                        <div style="font-size: 11px; color: #666;">
                            ${uiText?.diagnostics_last_run || 'Last run'}: ${new Date(report.timestamp).toLocaleString()} (${report.duration_ms}ms)
                        </div>
                    </div>
                </div>

                <!-- Intent Banner -->
                ${report.intent_signature?.top_intents?.length > 0 ? html`
                    <div id="diagnostics-intent-banner" style="padding: 10px; background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 6px; margin-bottom: 15px;">
                        <div style="font-size: 12px; color: #93c5fd; margin-bottom: 6px;">
                            🎯 ${uiText?.diagnostics_likely_intent || 'Likely intent'}:
                            <strong style="color: #60a5fa;">${report.intent_signature.top_intents[0].intent_id}</strong>
                            <span style="color: #888; margin-left: 6px;">(${Math.round(report.intent_signature.top_intents[0].confidence * 100)}%)</span>
                        </div>
                        ${report.intent_signature.top_intents[0].evidence?.slice(0, 3).map(ev => html`
                            <div style="font-size: 11px; color: #666; padding-left: 20px;">
                                • ${ev.explain || ev.signal_id}
                            </div>
                        `)}
                    </div>
                ` : null}

                <!-- Issues List -->
                ${report.issues?.length > 0 ? html`
                    <div id="diagnostics-issues-list" style="display: flex; flex-direction: column; gap: 8px;">
                        <div style="font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 4px;">
                            ${uiText?.diagnostics_issues || 'Issues'} (${report.issues.length})
                        </div>
                        ${report.issues.map(issue => html`
                            <div
                                class="diagnostics-issue"
                                data-issue-id=${issue.issue_id}
                                style="padding: 10px; background: #1a1a1a; border-radius: 6px; border-left: 3px solid ${severityColors[issue.severity]};"
                            >
                                <!-- Issue Header -->
                                <div
                                    style="display: flex; align-items: center; justify-content: space-between; cursor: pointer;"
                                    onClick=${() => toggleExpand(issue.issue_id)}
                                >
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="font-size: 14px;">${severityIcons[issue.severity]}</span>
                                        <span style="font-size: 12px; color: #ddd; font-weight: 500;">${issue.title}</span>
                                        ${issue.status !== 'open' ? html`
                                            <span style="font-size: 10px; padding: 2px 6px; background: rgba(100,100,100,0.3); border-radius: 10px; color: #888;">
                                                ${issue.status}
                                            </span>
                                        ` : null}
                                    </div>
                                    <span style="color: #666; font-size: 12px;">${expanded[issue.issue_id] ? '▼' : '▶'}</span>
                                </div>

                                <!-- Issue Summary -->
                                <div style="font-size: 11px; color: #999; margin-top: 4px; padding-left: 22px;">
                                    ${issue.summary}
                                </div>

                                <!-- Expanded Details -->
                                ${expanded[issue.issue_id] ? html`
                                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #333;">
                                        <!-- Evidence -->
                                        ${issue.evidence?.length > 0 ? html`
                                            <div style="margin-bottom: 8px;">
                                                <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 4px;">
                                                    ${uiText?.diagnostics_evidence || 'Evidence'}
                                                </div>
                                                ${issue.evidence.map(ev => html`
                                                    <div style="font-size: 11px; color: #888; padding-left: 10px;">• ${ev}</div>
                                                `)}
                                            </div>
                                        ` : null}

                                        <!-- Recommendations -->
                                        ${issue.recommendation?.length > 0 ? html`
                                            <div style="margin-bottom: 8px;">
                                                <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 4px;">
                                                    ${uiText?.diagnostics_recommendation || 'Recommendation'}
                                                </div>
                                                ${issue.recommendation.map(rec => html`
                                                    <div style="font-size: 11px; color: #a8d08d; padding-left: 10px;">💡 ${rec}</div>
                                                `)}
                                            </div>
                                        ` : null}

                                        <!-- Actions -->
                                        <div style="display: flex; gap: 6px; margin-top: 8px;">
                                            ${issue.target?.node_id != null ? html`
                                                <button
                                                    onClick=${() => handleLocateNode(issue.target.node_id)}
                                                    style="padding: 4px 8px; background: #333; border: 1px solid #444; border-radius: 4px; color: #ccc; cursor: pointer; font-size: 10px;"
                                                >
                                                    📍 ${uiText?.diagnostics_locate_node || 'Locate Node'}
                                                </button>
                                            ` : null}
                                            ${issue.status === 'open' ? html`
                                                <button
                                                    onClick=${() => handleAckIssue(report.report_id, issue.issue_id, 'acknowledged')}
                                                    style="padding: 4px 8px; background: #333; border: 1px solid #444; border-radius: 4px; color: #ccc; cursor: pointer; font-size: 10px;"
                                                >
                                                    ✓ ${uiText?.diagnostics_ack || 'Acknowledge'}
                                                </button>
                                                <button
                                                    onClick=${() => handleAckIssue(report.report_id, issue.issue_id, 'ignored')}
                                                    style="padding: 4px 8px; background: #333; border: 1px solid #444; border-radius: 4px; color: #888; cursor: pointer; font-size: 10px;"
                                                >
                                                    ⚪ ${uiText?.diagnostics_ignore || 'Ignore'}
                                                </button>
                                            ` : null}
                                        </div>
                                    </div>
                                ` : null}
                            </div>
                        `)}
                    </div>
                ` : html`
                    <div id="diagnostics-no-issues" style="text-align: center; padding: 20px; color: #4caf50; font-size: 12px;">
                        ✅ ${uiText?.diagnostics_no_issues || 'No issues detected'}
                    </div>
                `}
            ` : html`
                <!-- Empty State -->
                <div id="diagnostics-empty-state" style="text-align: center; padding: 30px; color: #666; font-size: 12px;">
                    <div style="font-size: 32px; margin-bottom: 10px; opacity: 0.5;">🩺</div>
                    <div>${uiText?.diagnostics_empty || 'Run diagnostics to check your workflow health'}</div>
                </div>
            `}
        </div>
    `;
}

/**
 * Trust & Health Section Component (Moved from Settings tab)
 * Displays /doctor/health and /doctor/plugins info
 */
function TrustHealthSection({ uiText }) {
    const { html, useState } = preactModules;

    const [healthData, setHealthData] = useState(null);
    const [pluginsData, setPluginsData] = useState(null);
    const [loading, setLoading] = useState(false);

    const refreshTrustHealth = async () => {
        setLoading(true);
        try {
            const healthRes = await DoctorAPI.getHealth();
            setHealthData(healthRes?.success ? healthRes.health : { error: healthRes?.error || 'Failed' });

            const pluginsRes = await DoctorAPI.getPluginsReport();
            setPluginsData(pluginsRes?.success ? pluginsRes.plugins : { error: pluginsRes?.error || 'Failed' });
        } catch (e) {
            setHealthData({ error: e?.message || 'error' });
            setPluginsData(null);
        } finally {
            setLoading(false);
        }
    };

    const renderBadge = (trust) => {
        const colors = {
            trusted: { bg: 'rgba(76, 175, 80, 0.18)', border: 'rgba(76, 175, 80, 0.35)', fg: '#c8f7c5' },
            unsigned: { bg: 'rgba(255, 193, 7, 0.14)', border: 'rgba(255, 193, 7, 0.35)', fg: '#ffe5b4' },
            untrusted: { bg: 'rgba(244, 67, 54, 0.14)', border: 'rgba(244, 67, 54, 0.35)', fg: '#ffd6d6' },
            blocked: { bg: 'rgba(244, 67, 54, 0.20)', border: 'rgba(244, 67, 54, 0.45)', fg: '#ffbdbd' },
        };
        const c = colors[trust] || { bg: 'rgba(158,158,158,0.10)', border: 'rgba(158,158,158,0.25)', fg: '#ddd' };
        return html`<span style="display:inline-block; padding:2px 6px; border-radius:999px; font-size:11px; border:1px solid ${c.border}; background:${c.bg}; color:${c.fg};">${trust || 'unknown'}</span>`;
    };

    const healthText = healthData?.error
        ? `Health: ${healthData.error}`
        : healthData
            ? `Health: pipeline_status=${healthData.last_analysis?.pipeline_status || 'unknown'}, ssrf_blocked=${healthData.ssrf?.blocked_total ?? 0}, dropped_logs=${healthData.logger?.dropped_messages ?? 0}`
            : uiText?.trust_health_hint || 'Fetch /doctor/health and plugin trust report (scan-only).';

    return html`
        <div id="doctor-trust-health-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #aaa;">
                    🛡️ <span>${uiText?.trust_health_title || 'Trust & Health'}</span>
                </div>
                <button id="doctor-trust-health-refresh-btn" onClick=${refreshTrustHealth} disabled=${loading} style="padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 12px;" title="${uiText?.refresh_btn || 'Refresh'}">${loading ? '⏳' : '🔄'}</button>
            </div>
            <div id="doctor-health-output" style="margin-top: 10px; font-size: 12px; color: #bbb; line-height: 1.4;">
                ${healthText}
            </div>
            <div id="doctor-plugins-output" style="margin-top: 10px; font-size: 12px; color: #bbb; line-height: 1.4;">
                ${pluginsData?.error
            ? `Plugins: ${pluginsData.error}`
            : pluginsData?.plugins?.length > 0
                ? html`
                            <div style="color:#aaa; font-size:12px; margin-bottom:6px;">
                                Plugins: ${pluginsData.config?.enabled ? 'enabled' : 'disabled'}, allowlist=${pluginsData.config?.allowlist_count ?? 0}, signature=${pluginsData.config?.signature_required ? 'required' : 'optional'}
                            </div>
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                ${pluginsData.plugins.slice(0, 10).map(p => html`
                                    <div style="display:flex; align-items:center; gap:8px; padding:6px 8px; border:1px solid #333; border-radius:6px; background:#161616;">
                                        ${renderBadge(p.trust)}
                                        <div style="flex:1; min-width:0;">
                                            <div style="font-size:12px; color:#ddd; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${p.plugin_id || p.file || 'unknown'}</div>
                                            <div style="font-size:11px; color:#888; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${p.file || ''}${p.reason ? ` • ${p.reason}` : ''}</div>
                                        </div>
                                    </div>
                                `)}
                            </div>
                            <div style="margin-top:8px; font-size:11px; color:#888;">
                                Trust counts: ${Object.entries(pluginsData.trust_counts || {}).map(([k, v]) => `${k}=${v}`).join(', ') || 'none'}
                            </div>
                        `
                : ''
        }
            </div>
        </div>
    `;
}

/**
 * Telemetry Section Component (Moved from Settings tab)
 * Toggle, view buffer, clear, export telemetry data
 */
function TelemetrySection({ uiText }) {
    const { html, useState, useEffect } = preactModules;

    const [enabled, setEnabled] = useState(false);
    const [bufferCount, setBufferCount] = useState(0);
    const [message, setMessage] = useState(null);

    const updateStatus = async () => {
        try {
            const res = await fetch('/doctor/telemetry/status');
            const data = await res.json();
            if (data.success) {
                setEnabled(data.enabled);
                setBufferCount(data.stats?.count || 0);
            }
        } catch (e) {
            console.warn('[TelemetrySection] Status unavailable');
        }
    };

    useEffect(() => { updateStatus(); }, []);

    const handleToggle = async () => {
        try {
            const res = await fetch('/doctor/telemetry/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !enabled })
            });
            const data = await res.json();
            setEnabled(data.enabled);
            updateStatus();
        } catch (e) {
            console.error('[TelemetrySection] Toggle error:', e);
        }
    };

    const handleView = async () => {
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

    const handleClear = async () => {
        if (!confirm(uiText?.telemetry_confirm_clear || 'Clear all telemetry data?')) return;
        try {
            const res = await fetch('/doctor/telemetry/clear', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                setMessage({ type: 'success', text: '✅' });
                setTimeout(() => setMessage(null), 1500);
                updateStatus();
            }
        } catch (e) {
            setMessage({ type: 'error', text: '❌' });
            setTimeout(() => setMessage(null), 1500);
        }
    };

    const handleExport = async () => {
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
            setMessage({ type: 'success', text: '✅' });
            setTimeout(() => setMessage(null), 1500);
        } catch (e) {
            setMessage({ type: 'error', text: '❌' });
            setTimeout(() => setMessage(null), 1500);
        }
    };

    const toggleStyle = enabled
        ? 'background: #4caf50;'
        : 'background: #444;';
    const knobTransform = enabled ? 'transform: translateX(18px);' : '';

    return html`
        <div id="doctor-telemetry-panel" style="border-top: 1px solid #444; padding-top: 15px; margin-top: 15px;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #aaa;">
                    📊 <span>${uiText?.telemetry_label || 'Anonymous Telemetry'}</span>
                </div>
                <label style="position: relative; display: inline-block; width: 40px; height: 22px; cursor: pointer;" onClick=${handleToggle}>
                    <span style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; ${toggleStyle} transition: .3s; border-radius: 22px;">
                        <span style="position:absolute;left:4px;top:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.3s;${knobTransform}"></span>
                    </span>
                </label>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 5px;">${uiText?.telemetry_description || 'Send anonymous usage data to help improve Doctor'}</div>
            <div id="doctor-telemetry-stats" style="font-size: 11px; color: #666; margin-top: 5px;">
                ${uiText?.telemetry_buffer_count?.replace('{n}', bufferCount) || `Currently buffered: ${bufferCount} events`}
            </div>
            <div style="display: flex; gap: 8px; margin-top: 10px;">
                <button id="doctor-telemetry-view-btn" onClick=${handleView} style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${uiText?.telemetry_view_buffer || 'View Buffer'}</button>
                <button id="doctor-telemetry-clear-btn" onClick=${handleClear} style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${message?.text === '✅' && message?.type === 'success' ? '✅' : (uiText?.telemetry_clear_all || 'Clear All')}</button>
                <button id="doctor-telemetry-export-btn" onClick=${handleExport} style="flex: 1; padding: 6px 10px; background: #333; border: 1px solid #444; border-radius: 4px; color: #eee; cursor: pointer; font-size: 11px;">${uiText?.telemetry_export || 'Export'}</button>
            </div>
            <div style="font-size: 11px; color: #666; margin-top: 5px;">${uiText?.telemetry_upload_none || 'Upload destination: None (local only)'}</div>
        </div>
    `;
}

function StatisticsIsland({ uiText }) {
    const { html, useState, useEffect } = preactModules;

    // ⚠️ R5: E2E test injection point (production-safe double-guard)
    const isTestHarness = window.location.pathname.includes('test-harness.html') ||
        typeof window.__testMocks !== 'undefined';
    if (isTestHarness &&
        typeof window.__testErrorInjection !== 'undefined' &&
        window.__testErrorInjection.enabled &&
        window.__testErrorInjection.throwIn === 'statistics') {

        if (window.__testErrorInjection.mode === 'always') {
            throw new Error('E2E Test: Permanent statistics crash');
        } else if (window.__testErrorInjection.mode === 'once') {
            window.__testErrorInjection.mode = 'off'; // One-time
            throw new Error('E2E Test: One-time statistics crash');
        }
    }

    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    // R16: Reset state - declared before early-returns to ensure stable hooks order
    const [resetting, setResetting] = useState(false);
    const [resetMessage, setResetMessage] = useState(null);

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

    // R16: Reset handler
    const handleReset = async () => {
        if (!confirm(uiText?.stats_reset_confirm || 'Reset statistics? This will clear all error history.')) return;
        setResetting(true);
        setResetMessage(null);
        try {
            const result = await DoctorAPI.resetStatistics();
            if (result.success) {
                setResetMessage({ type: 'success', text: uiText?.stats_reset_success || 'Statistics reset successfully' });
                fetchStats(); // Refresh to show empty state
            } else {
                setResetMessage({ type: 'error', text: result.message || uiText?.stats_reset_failed || 'Failed to reset statistics' });
            }
        } catch (e) {
            setResetMessage({ type: 'error', text: uiText?.stats_reset_failed || 'Failed to reset statistics' });
        } finally {
            setResetting(false);
            setTimeout(() => setResetMessage(null), 3000);
        }
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
                <div style="display: flex; gap: 6px;">
                    <button id="doctor-stats-reset-btn" onClick=${handleReset} disabled=${resetting} title="${uiText?.stats_reset_btn || 'Reset'}" style="background: none; border: none; color: ${resetting ? '#666' : '#888'}; cursor: ${resetting ? 'not-allowed' : 'pointer'}; font-size: 14px;">🗑️</button>
                    <button onClick=${fetchStats} title="Refresh" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px;">🔄</button>
                </div>
            </div>
            ${resetMessage ? html`
                <div style="margin-bottom: 10px; padding: 8px; border-radius: 4px; font-size: 12px; background: ${resetMessage.type === 'success' ? 'rgba(76, 175, 80, 0.2)' : 'rgba(244, 67, 54, 0.2)'}; color: ${resetMessage.type === 'success' ? '#4caf50' : '#f44336'};">
                    ${resetMessage.text}
                </div>
            ` : null}

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

                <!-- F14: Diagnostics Section -->
                <${DiagnosticsSection} uiText=${uiText} onDiagnosticsRun=${fetchStats} />

                <!-- Trust & Health Section (Moved from Settings) -->
                <${TrustHealthSection} uiText=${uiText} />

                <!-- Anonymous Telemetry Section (Moved from Settings) -->
                <${TelemetrySection} uiText=${uiText} />
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

        // R5: Wrap with ErrorBoundary if feature is enabled
        if (isErrorBoundariesEnabled()) {
            const ErrorBoundary = await createErrorBoundaryAsync();
            render(html`
                <${ErrorBoundary}
                    islandId="statistics"
                    uiText=${props.uiText || {}}
                >
                    <${StatisticsIsland} ...${props} />
                </${ErrorBoundary}>
            `, container);
        } else {
            // Render without ErrorBoundary (fallback to island_registry try-catch)
            render(html`<${StatisticsIsland} ...${props} />`, container);
        }

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
