/**
 * Doctor UI Factory - Creates the visual elements for the Doctor extension
 */
import { app } from "../../../scripts/app.js";
import { DoctorAPI } from "./doctor_api.js";

export class DoctorUI {
    constructor(options = {}) {
        // Configuration from ComfyUI settings
        this.language = options.language || 'zh_TW';
        this.pollInterval = options.pollInterval || 2000;
        this.autoOpenOnError = options.autoOpenOnError || false;
        this.enableNotifications = options.enableNotifications || true;
        this.api = options.api || null;  // ComfyUI API for event subscription

        this.isVisible = false;
        this.panel = null;
        this.pollTimerId = null;

        // Deduplication state
        this.lastErrorHash = null;
        this.lastErrorTimestamp = 0;
        this.ERROR_DEBOUNCE_MS = 1000;  // Ignore duplicate errors within 1 second

        this.createStyles();
        this.createSidebar();
        this.createMenuButton();

        // Subscribe to ComfyUI execution_error events (instant, more accurate)
        this.subscribeToExecutionErrors();

        // Start polling for errors (fallback for non-execution errors)
        this.startErrorMonitor();

        // Note: LLM settings are registered in doctor.js
    }

    /**
     * Subscribe to ComfyUI's native execution_error WebSocket events.
     * This provides instant error notifications with accurate node context.
     */
    subscribeToExecutionErrors() {
        if (!this.api) {
            console.warn("[ComfyUI-Doctor] API not available, relying on polling only");
            return;
        }

        this.api.addEventListener("execution_error", (event) => {
            console.log("[ComfyUI-Doctor] 🔴 Execution error received via WebSocket");

            const detail = event.detail || {};
            const { node_id, node_type, exception_message, exception_type } = detail;

            // Create error hash for deduplication
            const errorHash = this.getErrorHash(node_id, exception_type, exception_message);
            const now = Date.now();

            // Deduplicate: skip if same error within debounce window
            if (errorHash === this.lastErrorHash && (now - this.lastErrorTimestamp) < this.ERROR_DEBOUNCE_MS) {
                console.log("[ComfyUI-Doctor] Duplicate error ignored");
                return;
            }

            this.lastErrorHash = errorHash;
            this.lastErrorTimestamp = now;

            // Build data object compatible with existing updateLogCard
            const data = {
                last_error: `${exception_type}: ${exception_message}`,
                suggestion: null,  // Will be fetched from backend or analyzed by AI
                timestamp: new Date().toISOString(),
                node_context: {
                    node_id: node_id ? String(node_id) : null,
                    node_name: node_type || null,  // node_type is the class name
                    node_class: node_type || null,
                    custom_node_path: null,
                },
            };

            // Update UI
            this.handleNewError(data);
        });

        console.log("[ComfyUI-Doctor] 📡 Subscribed to execution_error events");
    }

    /**
     * Generate a hash for error deduplication.
     */
    getErrorHash(nodeId, exceptionType, exceptionMessage) {
        const msg = exceptionMessage ? exceptionMessage.slice(0, 100) : '';
        return `${nodeId || 'unknown'}-${exceptionType || 'Error'}-${msg}`;
    }

    /**
     * Handle a new error (from either event or polling).
     */
    handleNewError(data) {
        // Store for sidebar tab access
        this.lastErrorData = data;

        this.updateLogCard(data);

        // Update sidebar tab if available
        this.updateSidebarTab(data);

        // Update status dot (legacy sidebar)
        const statusDot = document.getElementById('doctor-status');
        if (statusDot) statusDot.classList.add('active');

        // Auto-open sidebar on error (if enabled)
        if (this.autoOpenOnError && !this.isVisible) {
            this.isVisible = true;
            this.panel.classList.add('visible');
        }

        // Show browser notification (if enabled)
        if (this.enableNotifications && Notification.permission === 'granted') {
            const body = data.suggestion
                ? data.suggestion.substring(0, 100)
                : (data.last_error ? data.last_error.substring(0, 100) : 'New error detected');
            new Notification('ComfyUI Doctor', { body, icon: '🏥' });
        }
    }

    /**
     * Update the modern sidebar tab content with error data.
     */
    updateSidebarTab(data) {
        const container = document.getElementById('doctor-tab-error-container');
        const statusDot = document.getElementById('doctor-tab-status');

        if (!container) return;

        // Update status indicator
        if (statusDot) {
            if (data && data.last_error) {
                statusDot.classList.add('error');
            } else {
                statusDot.classList.remove('error');
            }
        }

        if (!data || !data.last_error) {
            container.innerHTML = `
                <div class="no-errors">
                    <div class="icon">✅</div>
                    <div>No errors detected</div>
                    <div style="margin-top: 5px; font-size: 12px;">System running smoothly</div>
                </div>
            `;
            return;
        }

        const nodeContext = data.node_context || {};
        const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : 'Unknown';

        // Extract error type and message
        let errorType = 'Error';
        let errorMessage = data.last_error || 'Unknown error';
        if (errorMessage.includes(':')) {
            const colonIndex = errorMessage.indexOf(':');
            errorType = errorMessage.substring(0, colonIndex).trim();
            errorMessage = errorMessage.substring(colonIndex + 1).trim();
        }

        container.innerHTML = `
            <div class="error-card">
                <div class="error-type">⚠️ ${this.escapeHtml(errorType)}</div>
                <div class="error-message">${this.escapeHtml(errorMessage.substring(0, 300))}${errorMessage.length > 300 ? '...' : ''}</div>
                <div class="error-time">🕐 ${timestamp}</div>
                ${nodeContext.node_id ? `
                    <div class="node-context">
                        <span><strong>Node:</strong> ${this.escapeHtml(nodeContext.node_name || 'Unknown')} (#${nodeContext.node_id})</span>
                        ${nodeContext.node_class ? `<span><strong>Class:</strong> ${this.escapeHtml(nodeContext.node_class)}</span>` : ''}
                        ${nodeContext.custom_node_path ? `<span><strong>Source:</strong> ${this.escapeHtml(nodeContext.custom_node_path)}</span>` : ''}
                    </div>
                ` : ''}
                <button class="action-btn" id="doctor-tab-locate-btn">🔍 Locate Node on Canvas</button>
                <button class="action-btn primary" id="doctor-tab-ai-btn">✨ Analyze with AI</button>
            </div>
            <div id="doctor-tab-ai-response"></div>
            ${data.suggestion ? `
                <div class="ai-response">
                    <h4>💡 Suggestion</h4>
                    <div>${this.escapeHtml(data.suggestion)}</div>
                </div>
            ` : ''}
        `;

        // Attach event listeners
        const locateBtn = document.getElementById('doctor-tab-locate-btn');
        const aiBtn = document.getElementById('doctor-tab-ai-btn');

        if (locateBtn && nodeContext.node_id) {
            locateBtn.onclick = () => this.locateNodeOnCanvas(nodeContext.node_id);
        } else if (locateBtn) {
            locateBtn.disabled = true;
            locateBtn.style.opacity = '0.5';
        }

        if (aiBtn) {
            aiBtn.onclick = () => this.triggerAIAnalysis(data, 'doctor-tab-ai-response', aiBtn);
        }
    }

    /**
     * Escape HTML to prevent XSS.
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }


    // Note: LLM settings are now registered in doctor.js with Doctor.LLM.* IDs


    // Method to update poll interval dynamically
    updatePollInterval(newInterval) {
        this.pollInterval = newInterval;
        if (this.pollTimerId) {
            clearInterval(this.pollTimerId);
            this.startErrorMonitor();
        }
        console.log(`[ComfyUI-Doctor] Poll interval updated to ${newInterval}ms`);
    }

    createStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #doctor-sidebar {
                position: fixed;
                top: 0;
                right: -320px;
                width: 320px;
                height: 100vh;
                background: #222;
                border-left: 1px solid #444;
                transition: right 0.3s ease;
                z-index: 9000;
                display: flex;
                flex-direction: column;
                box-shadow: -4px 0 15px rgba(0,0,0,0.5);
                font-family: sans-serif;
            }
            #doctor-sidebar.visible {
                right: 0;
            }
            .doctor-header {
                padding: 15px;
                background: #333;
                border-bottom: 1px solid #444;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .doctor-title {
                font-weight: bold;
                color: #fff;
                font-size: 16px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .doctor-close {
                cursor: pointer;
                color: #aaa;
                background: none;
                border: none;
                font-size: 18px;
            }
            .doctor-close:hover { color: #fff; }
            
            .doctor-content {
                flex: 1;
                overflow-y: auto;
                padding: 15px;
            }
            
            .doctor-card {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 12px;
            }
            .doctor-card.error {
                border-left: 4px solid #ff4444;
            }
            .doctor-card-title {
                font-size: 12px;
                color: #888;
                margin-bottom: 5px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .doctor-card-body {
                color: #ddd;
                font-size: 14px;
                line-height: 1.4;
            }
            
            .doctor-action-btn {
                background: #333;
                color: #eee;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                margin-top: 8px;
                width: 100%;
                text-align: left;
                transition: background 0.2s;
            }
            .doctor-action-btn:hover { background: #444; }
            
            .doctor-status-dot {
                width: 8px;
                height: 8px;
                background: #4caf50; /* Green by default */
                border-radius: 50%;
                display: inline-block;
            }
            .doctor-status-dot.active { background: #ff4444; box-shadow: 0 0 5px #ff4444; }

            /* Settings section in sidebar */
            .doctor-settings-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
                color: #ccc;
                font-size: 13px;
            }
            .doctor-select {
                background: #111;
                color: #eee;
                border: 1px solid #444;
                padding: 4px;
                border-radius: 3px;
                width: 120px;
            }
        `;
        document.head.appendChild(style);
    }

    createSidebar() {
        this.panel = document.createElement('div');
        this.panel.id = 'doctor-sidebar';

        // Header
        const header = document.createElement('div');
        header.className = 'doctor-header';
        header.innerHTML = `
            <div class="doctor-title">
                <span class="doctor-status-dot" id="doctor-status"></span>
                ComfyUI Doctor
            </div>
            <button class="doctor-close">×</button>
        `;
        header.querySelector('.doctor-close').onclick = () => this.toggle();
        this.panel.appendChild(header);

        // Content Area
        const content = document.createElement('div');
        content.className = 'doctor-content';
        content.id = 'doctor-content-area';

        // Info Card - Settings are now in ComfyUI Settings Panel
        const infoCard = document.createElement('div');
        infoCard.className = 'doctor-card';
        infoCard.innerHTML = `
            <div class="doctor-card-title">INFO</div>
            <div class="doctor-card-body" style="font-size:12px;color:#888">
                ⚙️ Settings available in<br>
                <strong>ComfyUI Settings → Doctor</strong>
            </div>
        `;
        content.appendChild(infoCard);

        // Initial Loading State for Logs
        const logCard = document.createElement('div');
        logCard.className = 'doctor-card';
        logCard.innerHTML = `<div class="doctor-card-body" style="color:#777;text-align:center">No active errors detected.</div>`;
        logCard.id = 'doctor-latest-log';
        content.appendChild(logCard);

        this.panel.appendChild(content);
        document.body.appendChild(this.panel);
    }

    createMenuButton() {
        // Find ComfyUI menu strip
        const menuStrip = document.querySelector(".comfy-menu");

        const btn = document.createElement("button");
        btn.textContent = "🏥 Doctor";
        btn.style.cssText = `
            background: transparent;
            color: var(--fg-color, #ccc);
            border: none;
            cursor: pointer;
            font-size: 14px;
            padding: 5px 10px;
            margin-top: 10px;
            border-top: 1px solid var(--border-color, #444);
            width: 100%;
            text-align: left;
        `;
        // Try to insert after the last button for visibility, or append
        if (menuStrip) {
            menuStrip.appendChild(btn);
        } else {
            // Fallback: Fixed floating button if menu strip not found
            btn.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 50;
                background: #333;
                border: 1px solid #555;
                border-radius: 20px;
                padding: 8px 16px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            `;
            document.body.appendChild(btn);
        }

        btn.addEventListener('click', () => this.toggle());
    }

    toggle() {
        this.isVisible = !this.isVisible;
        this.panel.classList.toggle('visible', this.isVisible);
    }

    startErrorMonitor() {
        this.lastTimestamp = null;
        this.pollTimerId = setInterval(async () => {
            const data = await DoctorAPI.getLastAnalysis();
            if (!data) return;

            // Update status dot
            const statusDot = document.getElementById('doctor-status');

            if (data.last_error && data.timestamp) {
                // Check if this is a new error (by timestamp)
                if (this.lastTimestamp !== data.timestamp) {
                    this.lastTimestamp = data.timestamp;

                    // Apply deduplication (same logic as event handler)
                    const errorHash = this.getErrorHash(
                        data.node_context?.node_id,
                        null,  // exception_type not available from polling
                        data.last_error
                    );
                    const now = Date.now();

                    if (errorHash === this.lastErrorHash && (now - this.lastErrorTimestamp) < this.ERROR_DEBOUNCE_MS) {
                        console.log("[ComfyUI-Doctor] Duplicate error from polling ignored");
                        return;
                    }

                    this.lastErrorHash = errorHash;
                    this.lastErrorTimestamp = now;

                    // Use shared handler
                    this.handleNewError(data);
                }
            } else {
                if (statusDot) statusDot.classList.remove('active');
            }
        }, this.pollInterval);
    }

    updateLogCard(data) {
        const container = document.getElementById('doctor-latest-log');
        if (!container) return;

        let errorText = data.suggestion ? data.suggestion.replace("💡 SUGGESTION: ", "") : null;

        // Fallback: If no suggestion, try to extract the exception message from raw error
        if (!errorText && data.last_error) {
            const lines = data.last_error.trim().split('\n');
            if (lines.length > 0) {
                errorText = lines[lines.length - 1]; // Use last line (usually Exception: Message)
            }
        }

        if (!errorText) errorText = "Unknown Error";

        let html = `
            <div class="doctor-card-title">LATEST DIAGNOSIS</div>
            <div class="doctor-card-body">
                <div style="font-weight:bold;color:#ff8888;margin-bottom:8px">${errorText}</div>
                <div style="font-size:11px;color:#888;margin-bottom:8px">${new Date(data.timestamp).toLocaleTimeString()}</div>
        `;

        if (data.node_context && data.node_context.node_id) {
            html += `
                <div style="background:#222;padding:6px;border-radius:4px;margin-bottom:8px;font-family:monospace;font-size:11px;">
                    Node #${data.node_context.node_id}: ${data.node_context.node_name || 'Unknown'}
                </div>
                <button class="doctor-action-btn" id="doctor-locate-btn" data-node="${data.node_context.node_id}">
                    🔍 Locate Node on Canvas
                </button>
             `;
        }

        // Add AI Analysis Button
        html += `
            <button class="doctor-action-btn" id="doctor-ai-btn" style="border-color:#6699ff;color:#6699ff;">
                ✨ Analyze with AI
            </button>
            <div id="doctor-ai-result" style="margin-top:10px;font-size:13px;line-height:1.5;color:#eee;white-space:pre-wrap;display:none;background:#223;padding:10px;border-radius:4px;"></div>
        `;

        html += `</div>`;

        container.innerHTML = html;
        container.classList.add('error');

        // Re-bind locate button
        const btn = container.querySelector('#doctor-locate-btn');
        if (btn) {
            btn.onclick = () => {
                try {
                    const nodeId = btn.getAttribute('data-node');
                    const numericId = parseInt(nodeId, 10);
                    if (isNaN(numericId)) {
                        console.warn('[ComfyUI-Doctor] Invalid node ID:', nodeId);
                        return;
                    }
                    app.canvas.centerOnNode(numericId);
                    // Optional: visual flash logic
                    const node = app.graph.getNodeById(numericId);
                    if (node) {
                        app.canvas.selectNode(node);
                    }
                } catch (e) {
                    console.error('[ComfyUI-Doctor] Failed to locate node:', e);
                }
            };
        }

        // Bind AI button
        const aiBtn = container.querySelector('#doctor-ai-btn');
        const aiResult = container.querySelector('#doctor-ai-result');
        if (aiBtn) {
            aiBtn.onclick = async () => {
                const apiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
                const baseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
                const model = app.ui.settings.getSettingValue("Doctor.LLM.Model", "gpt-4o");

                // Check if this is a local LLM (Ollama/LMStudio)
                const isLocal = baseUrl.includes("localhost") || baseUrl.includes("127.0.0.1");

                // Only require API key for non-local LLMs
                if (!apiKey && !isLocal) {
                    alert("Please configure API Key in ComfyUI Settings -> Doctor first.");
                    return;
                }

                aiBtn.disabled = true;
                aiBtn.textContent = "⏳ Analyzing...";
                aiResult.style.display = 'block';
                aiResult.textContent = isLocal ? "Connecting to local LLM..." : "Connecting to LLM...";

                try {
                    const payload = {
                        error: data.last_error || "Unknown Error",
                        node_context: data.node_context,
                        api_key: apiKey,
                        base_url: baseUrl,
                        model: model,
                        language: this.language
                    };

                    const result = await DoctorAPI.analyzeError(payload);

                    if (result.analysis) {
                        // Security: Use textContent to prevent XSS
                        aiResult.textContent = "🤖 AI Analysis:\n\n" + result.analysis;
                    } else {
                        aiResult.textContent = "No analysis returned.";
                    }
                } catch (e) {
                    aiResult.textContent = `Error: ${e.message}`;
                } finally {
                    aiBtn.disabled = false;
                    aiBtn.textContent = "✨ Analyze with AI";
                }
            };
        }
    }
}
