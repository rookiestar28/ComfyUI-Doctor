/**
 * F7: Smart Parameter Injection - Fix Handler Module
 *
 * Detects, renders, and applies parameter fixes suggested by the AI chat.
 * Provides one-click fix application with visual feedback and undo support.
 */

import { markComfyGraphDirty, resolveComfyFixTargetNode } from "./comfyui_frontend_compat.js";

export const FIX_TEXT_MAX_LENGTH = 4096;
const SAFE_WIDGET_TYPES = ['number', 'slider', 'combo', 'text', 'toggle', 'converted-widget'];
// Plain decimal numbers only: no hex, no partial parses ("12abc"), no blanks.
const DECIMAL_NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function invalid(errorKey) {
    return { ok: false, errorKey };
}

function parseNumberValue(raw, options) {
    let value = NaN;
    if (typeof raw === 'number') {
        value = raw;
    } else if (typeof raw === 'string' && DECIMAL_NUMBER.test(raw.trim())) {
        value = Number(raw.trim());
    }
    if (!Number.isFinite(value)) return invalid('fix_error_invalid_number');
    if (typeof options?.min === 'number' && value < options.min) return invalid('fix_error_invalid_value');
    if (typeof options?.max === 'number' && value > options.max) return invalid('fix_error_invalid_value');
    return { ok: true, value };
}

function parseToggleValue(raw) {
    if (typeof raw === 'boolean') return { ok: true, value: raw };
    if (raw === 1 || raw === 0) return { ok: true, value: raw === 1 };
    if (typeof raw === 'string') {
        const normalized = raw.trim().toLowerCase();
        if (normalized === 'true') return { ok: true, value: true };
        if (normalized === 'false') return { ok: true, value: false };
    }
    return invalid('fix_error_invalid_value');
}

function comboValues(widget) {
    const values = widget?.options?.values;
    try {
        const list = typeof values === 'function' ? values(widget) : values;
        return Array.isArray(list) ? list : null;
    } catch (_) {
        return null;
    }
}

function parseComboValue(raw, widget) {
    const values = comboValues(widget);
    if (values) {
        if (values.includes(raw)) return { ok: true, value: raw };
        if (typeof raw === 'number' && values.includes(String(raw))) return { ok: true, value: String(raw) };
        return invalid('fix_error_invalid_value');
    }
    return parseTextValue(raw);
}

function parseTextValue(raw) {
    if (typeof raw !== 'string' || raw.length > FIX_TEXT_MAX_LENGTH) return invalid('fix_error_invalid_value');
    return { ok: true, value: raw };
}

/**
 * Validate an LLM-suggested value for a widget. Returns {ok, value} or {ok: false, errorKey}.
 * Rejections never mutate anything.
 */
export function parseFixValue(widget, raw) {
    const widgetType = widget?.type || 'number';
    if (widgetType === 'number' || widgetType === 'slider') return parseNumberValue(raw, widget.options);
    if (widgetType === 'toggle') return parseToggleValue(raw);
    if (widgetType === 'combo') return parseComboValue(raw, widget);
    if (widgetType === 'text') return parseTextValue(raw);
    if (widgetType === 'converted-widget') {
        if (typeof widget.value === 'number') return parseNumberValue(raw, widget.options);
        if (typeof widget.value === 'boolean') return parseToggleValue(raw);
        return parseTextValue(raw);
    }
    return invalid('fix_error_unsafe_type');
}

const FALLBACK_ERRORS = {
    fix_error_node_not_found: 'Node not found',
    fix_error_widget_not_found: 'Widget not found',
    fix_error_unsafe_type: 'Unsafe widget type',
    fix_error_invalid_number: 'Invalid number value',
    fix_error_invalid_value: 'Invalid value for this widget',
};

function fixError(i18n, key) {
    return new Error(i18n?.[key] || FALLBACK_ERRORS[key]);
}

export class FixHandler {
    constructor(app) {
        this.app = app;  // ComfyUI app instance
        this.appliedFixes = [];  // History for undo
    }

    /**
     * Detect fix JSON in message content
     * Returns: {fixes: [...]} or null
     */
    detectFixes(content) {
        const regex = /```json\s*(\{[^`]*?"fixes"[^`]*?\})\s*```/gs;
        const match = regex.exec(content);
        if (!match) return null;

        try {
            const fixData = JSON.parse(match[1]);
            return this.validateFixes(fixData) ? fixData : null;
        } catch (e) {
            console.warn('[FixHandler] Invalid fix JSON:', e);
            return null;
        }
    }

    /**
     * Validate fix schema
     * Required keys: node_id, widget, to
     * Optional keys: from, reason
     */
    validateFixes(fixData) {
        if (!fixData.fixes || !Array.isArray(fixData.fixes)) {
            return false;
        }

        return fixData.fixes.every(fix => {
            // Check required fields
            if (!fix || fix.node_id === undefined || fix.node_id === null || fix.node_id === ''
                || typeof fix.widget !== 'string' || !fix.widget || fix.to === undefined) {
                return false;
            }

            // Validate node_id is string or number
            if (typeof fix.node_id !== 'string' && typeof fix.node_id !== 'number') {
                return false;
            }

            return true;
        });
    }

    /**
     * Render fix buttons in message DOM
     *
     * @param {HTMLElement} messageDiv - The chat message div
     * @param {Object} fixData - Fix data with {fixes: [...]}
     * @param {Object} i18n - Internationalization object
     */
    renderFixButtons(messageDiv, fixData, i18n) {
        const container = document.createElement('div');
        container.className = 'doctor-fix-container';

        fixData.fixes.forEach((fix, index) => {
            const btn = document.createElement('button');
            btn.className = 'doctor-fix-btn';

            // Format button text with i18n support
            const fromText = fix.from !== undefined ? ` ${String(fix.from)} →` : '';
            const buttonText = i18n?.fix_apply_button
                ? `${i18n.fix_apply_button}: ${fix.widget}${fromText} ${String(fix.to)}`
                : `⚡ Apply: ${fix.widget}${fromText} ${String(fix.to)}`;

            // CRITICAL: fix fields are LLM-controlled and prompt-injectable; never parse them as HTML
            // (innerHTML here executed injected handlers in the ComfyUI origin).
            btn.textContent = buttonText;
            btn.title = typeof fix.reason === 'string' && fix.reason
                ? fix.reason
                : (i18n?.fix_apply_tooltip || 'Apply parameter fix');
            btn.dataset.fixIndex = index;

            btn.onclick = () => this.applyFix(fix, btn, i18n);
            container.appendChild(btn);
        });

        messageDiv.appendChild(container);
    }

    /**
     * Apply fix to canvas widget
     *
     * @param {Object} fix - Fix data {node_id, widget, to, from?, reason?}
     * @param {HTMLButtonElement} button - The button element
     * @param {Object} i18n - Internationalization object
     */
    async applyFix(fix, button, i18n) {
        try {
            button.disabled = true;
            button.textContent = i18n?.fix_applying || 'Applying...';

            // Find the exact live node (no numeric coercion of LLM-provided ids)
            const node = resolveComfyFixTargetNode(fix.node_id, this.app);
            if (!node) {
                throw fixError(i18n, 'fix_error_node_not_found');
            }
            const nodeId = String(fix.node_id);

            // Find widget
            const widget = typeof fix.widget === 'string'
                ? node.widgets?.find(w => w.name === fix.widget)
                : null;
            if (!widget) {
                throw fixError(i18n, 'fix_error_widget_not_found');
            }

            // Validate widget type (security whitelist)
            if (!SAFE_WIDGET_TYPES.includes(widget.type || 'number')) {
                throw fixError(i18n, 'fix_error_unsafe_type');
            }

            // Strict value validation; rejections leave the graph untouched
            const parsed = parseFixValue(widget, fix.to);
            if (!parsed.ok) {
                throw fixError(i18n, parsed.errorKey);
            }
            const newValue = parsed.value;

            // Store for undo (the resolved node itself, not a re-parsed id)
            this.appliedFixes.push({
                node,
                node_id: nodeId,
                widget: fix.widget,
                oldValue: widget.value,
                newValue: newValue,
                timestamp: Date.now()
            });

            // Apply fix
            widget.value = newValue;

            // Trigger callback if exists
            if (widget.callback) {
                widget.callback(newValue);
            }

            // Redraw canvas
            markComfyGraphDirty(this.app, false, true);

            // Success state
            button.className = 'doctor-fix-btn applied';
            button.textContent = i18n?.fix_applied || '✓ Applied';

            // Flash node highlight
            this.flashNodeHighlight(node);

            // Log success
            // IMPORTANT: raw node IDs and widget values can contain private workflow content.
            console.log('[FixHandler] Applied fix');

        } catch (error) {
            console.error('[FixHandler] Apply failed:', error);
            button.className = 'doctor-fix-btn error';
            button.textContent = `✗ ${error.message}`;
        }
    }

    /**
     * Flash visual highlight on node
     *
     * @param {Object} node - Resolved node to highlight
     */
    flashNodeHighlight(node) {
        if (!node) return;

        const originalColor = node.color;
        const originalBgColor = node.bgcolor;

        // Set highlight colors (blue theme)
        node.color = "#2563eb";
        node.bgcolor = "#dbeafe";
        markComfyGraphDirty(this.app, true, true);

        // Restore after animation
        setTimeout(() => {
            node.color = originalColor;
            node.bgcolor = originalBgColor;
            markComfyGraphDirty(this.app, true, true);
        }, 800);
    }

    /**
     * Undo last applied fix
     * Can be called from browser console for debugging/manual undo
     *
     * @returns {boolean} - True if undo was successful
     */
    undoLastFix() {
        if (this.appliedFixes.length === 0) {
            console.warn('[FixHandler] No fixes to undo');
            return false;
        }

        const last = this.appliedFixes.pop();
        const widget = last.node?.widgets?.find(w => w.name === last.widget);

        if (!widget) {
            console.error('[FixHandler] Cannot undo: widget not found');
            return false;
        }

        widget.value = last.oldValue;
        if (widget.callback) {
            widget.callback(last.oldValue);
        }

        markComfyGraphDirty(this.app, false, true);
        console.log('[FixHandler] Undone fix');

        return true;
    }

    /**
     * Get fix application history
     *
     * @returns {Array} - Array of applied fixes
     */
    getHistory() {
        return [...this.appliedFixes];
    }

    /**
     * Clear fix history
     */
    clearHistory() {
        this.appliedFixes = [];
    }
}

// Export for global access (testing, console use)
if (typeof window !== 'undefined') {
    window.FixHandler = FixHandler;
}
