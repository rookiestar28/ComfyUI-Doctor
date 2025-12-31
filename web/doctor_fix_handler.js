/**
 * F7: Smart Parameter Injection - Fix Handler Module
 *
 * Detects, renders, and applies parameter fixes suggested by the AI chat.
 * Provides one-click fix application with visual feedback and undo support.
 */

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
            if (!fix.node_id || !fix.widget || fix.to === undefined) {
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
            const fromText = fix.from !== undefined ? ` ${fix.from} →` : '';
            const buttonText = i18n?.fix_apply_button
                ? `${i18n.fix_apply_button}: ${fix.widget}${fromText} ${fix.to}`
                : `⚡ Apply: ${fix.widget}${fromText} ${fix.to}`;

            btn.innerHTML = buttonText;
            btn.title = fix.reason || (i18n?.fix_apply_tooltip || 'Apply parameter fix');
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

            // Find node
            const nodeId = parseInt(fix.node_id);
            const node = this.app.graph.getNodeById(nodeId);

            if (!node) {
                throw new Error(i18n?.fix_error_node_not_found || `Node ${nodeId} not found`);
            }

            // Find widget
            const widget = node.widgets?.find(w => w.name === fix.widget);
            if (!widget) {
                throw new Error(
                    i18n?.fix_error_widget_not_found || `Widget "${fix.widget}" not found`
                );
            }

            // Validate widget type (security whitelist)
            const safeTypes = ['number', 'slider', 'combo', 'text', 'toggle', 'converted-widget'];
            const widgetType = widget.type || 'number';

            if (!safeTypes.includes(widgetType)) {
                throw new Error(
                    i18n?.fix_error_unsafe_type || `Unsafe widget type: ${widgetType}`
                );
            }

            // Type coercion based on widget type
            let newValue = fix.to;
            if (widgetType === 'number' || widgetType === 'slider') {
                newValue = parseFloat(fix.to);
                if (isNaN(newValue)) {
                    throw new Error(i18n?.fix_error_invalid_number || 'Invalid number value');
                }
            } else if (widgetType === 'toggle') {
                newValue = Boolean(fix.to);
            }

            // Store for undo
            this.appliedFixes.push({
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
            this.app.graph.setDirtyCanvas(false, true);

            // Success state
            button.className = 'doctor-fix-btn applied';
            button.textContent = i18n?.fix_applied || '✓ Applied';

            // Flash node highlight
            this.flashNodeHighlight(nodeId);

            // Log success
            console.log(`[FixHandler] Applied fix: Node ${nodeId}, ${fix.widget} = ${newValue}`);

        } catch (error) {
            console.error('[FixHandler] Apply failed:', error);
            button.className = 'doctor-fix-btn error';
            button.textContent = `✗ ${error.message}`;
        }
    }

    /**
     * Flash visual highlight on node
     *
     * @param {number} nodeId - Node ID to highlight
     */
    flashNodeHighlight(nodeId) {
        const node = this.app.graph.getNodeById(nodeId);
        if (!node) return;

        const originalColor = node.color;
        const originalBgColor = node.bgcolor;

        // Set highlight colors (blue theme)
        node.color = "#2563eb";
        node.bgcolor = "#dbeafe";
        this.app.graph.setDirtyCanvas(true, true);

        // Restore after animation
        setTimeout(() => {
            node.color = originalColor;
            node.bgcolor = originalBgColor;
            this.app.graph.setDirtyCanvas(true, true);
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
        const node = this.app.graph.getNodeById(last.node_id);
        const widget = node?.widgets?.find(w => w.name === last.widget);

        if (!widget) {
            console.error('[FixHandler] Cannot undo: widget not found');
            return false;
        }

        widget.value = last.oldValue;
        if (widget.callback) {
            widget.callback(last.oldValue);
        }

        this.app.graph.setDirtyCanvas(false, true);
        console.log(`[FixHandler] Undone: Node ${last.node_id}, ${last.widget} = ${last.oldValue}`);

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
