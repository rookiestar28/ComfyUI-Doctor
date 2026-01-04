/**
 * Doctor UI Factory - Creates the visual elements for the Doctor extension
 */
import { app } from "../../../scripts/app.js";
import { DoctorAPI } from "./doctor_api.js";
import { ChatPanel } from "./doctor_chat.js";

/**
 * CRITICAL INITIALIZATION WARNING (Added 2026-01-03)
 * ===================================================
 * This class uses ASYNC initialization via loadUIText().
 *
 * DO NOT call doctorUI.getUIText() BEFORE the DoctorUI instance is created!
 *
 * Problem Pattern (INCORRECT):
 * ```javascript
 * app.ui.settings.addSetting({
 *     name: doctorUI.getUIText('some_key'),  // ❌ ERROR: doctorUI doesn't exist yet!
 * });
 * const doctorUI = new DoctorUI({...});  // Created AFTER usage
 * ```
 *
 * Correct Pattern:
 * ```javascript
 * const doctorUI = new DoctorUI({...});  // Create FIRST
 * // Then use getUIText() in code that runs AFTER initialization
 * ```
 *
 * For code that runs BEFORE DoctorUI creation (e.g., ComfyUI settings registration),
 * use hardcoded fallback strings instead of getUIText().
 *
 * See: web/doctor.js lines 75, 119 for examples of correct hardcoded fallbacks.
 */
export class DoctorUI {
    constructor(options = {}) {
        // ═══════════════════════════════════════════════════════════════
        // CRITICAL: Language Fallback Configuration
        // ═══════════════════════════════════════════════════════════════
        // ⚠️ WARNING: Fallback must be 'en' (NOT 'zh_TW' or other languages)
        //
        // This fallback is used when options.language is undefined/null
        // MUST MATCH:
        //   - Backend: i18n.py (_current_language = "en")
        //   - Frontend: doctor.js (DEFAULTS.LANGUAGE = "en")
        //
        // Last Modified: 2026-01-03 (Fixed from 'zh_TW' to 'en')
        // ═══════════════════════════════════════════════════════════════
        this.language = options.language || 'en';  // ⚠️ DO NOT CHANGE fallback
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

        // ═══════════════════════════════════════════════════════════════
        // CRITICAL: UI Text Loading Order
        // ═══════════════════════════════════════════════════════════════
        // ⚠️ WARNING: this.uiText MUST be loaded BEFORE createSidebar()
        //
        // Common Bug Pattern (INCORRECT):
        //   this.uiText = {};
        //   this.loadUIText();        // ❌ Async, doesn't wait
        //   this.createSidebar();     // ❌ Creates UI before translations load
        //   Result: All UI text shows "[Missing: key_name]"
        //
        // Correct Pattern (CURRENT):
        //   this.uiText = {};
        //   this.loadUIText().then(() => {  // ✅ Wait for translations
        //       this.createSidebar();       // ✅ Create UI after load
        //   });
        //
        // Why This Matters:
        //   - Sidebar uses getUIText() extensively (save_settings_btn, etc.)
        //   - If uiText is empty {}, getUIText() returns "[Missing: ...]"
        //   - Users see broken UI with missing translations
        //
        // Last Modified: 2026-01-03 (Fixed race condition)
        // ═══════════════════════════════════════════════════════════════
        this.uiText = {};

        this.createStyles();
        this.createMenuButton();

        // ⚠️ CRITICAL: Load UI text FIRST, then create sidebar
        // DO NOT move createSidebar() before loadUIText() completes!
        this.loadUIText().then(() => {
            this.createSidebar();
        });

        // Subscribe to ComfyUI execution_error events (instant, more accurate)
        this.subscribeToExecutionErrors();

        // Start polling for errors (fallback for non-execution errors)
        this.startErrorMonitor();

        // Note: LLM settings are registered in doctor.js
    }

    /**
     * Load UI text translations from backend
     *
     * ⚠️ ASYNC WARNING (Added 2026-01-03):
     * This method is asynchronous and does NOT block the constructor.
     * this.uiText will be empty {} until this promise resolves.
     *
     * This means:
     * - getUIText() will return "[Missing: key]" if called before this completes
     * - UI elements created in constructor may initially show fallback text
     * - Language updates happen via updateUILanguage() after loading
     */
    async loadUIText() {
        try {
            const response = await fetch(`/doctor/ui_text?lang=${this.language}`);
            const data = await response.json();
            this.uiText = data.text || {};
            console.log(`[ComfyUI-Doctor] Loaded UI text for language: ${data.language}, Keys: ${Object.keys(this.uiText).length}`);
            if (this.uiText.statistics_title) console.log(`[ComfyUI-Doctor] statistics_title: ${this.uiText.statistics_title}`);
            else console.log(`[ComfyUI-Doctor] statistics_title MISSING`);

            // Update UI if already created
            if (this.panel) {
                this.updateUILanguage();
            }
        } catch (error) {
            console.error("[ComfyUI-Doctor] Failed to load UI text:", error);
            // Fallback to English defaults
            this.uiText = {
                "info_title": "INFO",
                "info_message": "Click 🏥 Doctor button (left sidebar) to analyze errors with AI",
                "settings_hint": "Settings available in",
                "settings_path": "ComfyUI Settings → Doctor",
                "sidebar_hint": "Open the Doctor sidebar (left panel) to analyze with AI",
                "locate_node_btn": "Locate Node on Canvas",
                "no_errors": "No active errors detected.",
                "analyze_with_ai": "✨ Analyze with AI",
                "ai_analysis_title": "AI Analysis:",
                "thinking": "Thinking...",
                "missing_api_key_title": "Missing API Key",
                "connecting_to_ai": "Connecting to AI...",
                "connecting_to_local_llm": "Connecting to local LLM...",
                "system_running_smoothly": "System running smoothly",
                "no_errors_detected": "No errors detected",
                "node_label": "Node",
                "ask_ai_placeholder": "Ask AI about this error...",
                "send_btn": "Send",
                "clear_btn": "Clear",
                "doctor_ai_title": "🤖 Doctor AI",
                "expand_btn": "Expand",
                "regenerate_btn": "Regenerate Last",
                "stop_btn": "Stop Generating",
                "confirm_clear": "Clear conversation?",
                "clear_history": "Clear History",
                "statistics_title": "Error Statistics",
                "stats_total_errors": "Total (30d)",
                "stats_last_24h": "Last 24h",
                "stats_last_7d": "Last 7d",
                "stats_last_30d": "Last 30d",
                "stats_top_patterns": "Top Error Patterns",
                "stats_resolution_rate": "Resolution Rate",
                "stats_error": "Failed to load statistics",
                "stats_categories": "Categories",
                "stats_loading": "Loading...",
                "stats_no_data": "No data yet",
                "stats_resolved": "Resolved",
                "stats_unresolved": "Unresolved",
                "stats_ignored": "Ignored",
                "category_memory": "Memory",
                "category_workflow": "Workflow",
                "category_model_loading": "Model Loading",
                "category_framework": "Framework",
                "category_generic": "Generic",
            };
        }
    }

    /**
     * Get translated UI text by key
     *
     * ⚠️ TIMING WARNING (Added 2026-01-03):
     * This method can only be called AFTER the DoctorUI instance is created.
     * If this.uiText hasn't loaded yet, it returns "[Missing: key]".
     *
     * DO NOT use this in code that runs before DoctorUI instantiation!
     * Use hardcoded fallback strings instead for early initialization code.
     */
    getUIText(key) {
        return this.uiText[key] || `[Missing: ${key}]`;
    }

    /**
     * Update UI language when language changes
     */
    updateUILanguage() {
        // This will be called when language changes
        // For now, we'll implement the specific UI updates in the relevant methods
        this.updateInfoCard();
        this.updateLogCard();
        this.updateStatisticsPanel();
    }

    /**
     * Update INFO card with current language
     */
    updateInfoCard() {
        const infoCard = document.querySelector('#doctor-content-area .doctor-card:first-child');
        if (infoCard) {
            infoCard.innerHTML = `
                <div class="doctor-card-title">${this.getUIText('info_title')}</div>
                <div class="doctor-card-body" style="font-size:12px;color:#888;line-height:1.6;">
                    ${this.getUIText('info_message')}
                </div>
            `;
        }
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

        // F4: Auto-refresh statistics
        this.renderStatistics();
    }

    /**
     * ═══════════════════════════════════════════════════════════════
     * Update LEFT SIDEBAR Tab - Doctor Sidebar Error Context
     * ═══════════════════════════════════════════════════════════════
     *
     * LOCATION: Left sidebar panel (web/doctor.js)
     * DO NOT CONFUSE WITH: Right error panel (updateLogCard method)
     *
     * PURPOSE: Updates the error context card in the left sidebar
     *
     * DISPLAY STRATEGY:
     * - Shows CONCISE SUGGESTION ONLY (actionable advice)
     * - Extracts last sentence from full suggestion
     * - Example: "Check input connections and ensure node requirements are met."
     *
     * BACKEND DATA:
     * - Full error context is sent to LLM (unchanged)
     * - Only frontend display is simplified
     *
     * EXTRACTION LOGIC:
     * - Split suggestion by period ('. ')
     * - Take last sentence as actionable advice
     * - See Lines 240-258 for implementation
     *
     * RELATED:
     * - Left sidebar structure: web/doctor.js Lines 540-559
     * - Right panel display: updateLogCard() method
     * - Documentation: .planning/ERROR_PANEL_UI_FIXES.md Issue 5
     * ═══════════════════════════════════════════════════════════════
     */
    updateSidebarTab(data) {
        const errorContext = this.sidebarErrorContext;
        const messages = this.sidebarMessages;
        const statusDot = document.getElementById('doctor-tab-status');

        if (!errorContext || !messages) return;

        // Update status indicator
        if (statusDot) {
            if (data && data.last_error) {
                statusDot.style.background = '#ff4444';
            } else {
                statusDot.style.background = '#4caf50';
            }
        }

        if (!data || !data.last_error) {
            errorContext.style.display = 'none';
            messages.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: #888;">
                    <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
                    <div>${this.getUIText('no_errors_detected')}</div>
                    <div style="margin-top: 5px; font-size: 12px;">${this.getUIText('system_running_smoothly')}</div>
                </div>
            `;
            return;
        }

        // Store error data for chat
        this.currentErrorData = data;

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

        // ═══════════════════════════════════════════════════════════════
        // SUGGESTION EXTRACTION - Display CONCISE advice only
        // ═══════════════════════════════════════════════════════════════
        // DO NOT REMOVE OR MODIFY without consulting .planning/ERROR_PANEL_UI_FIXES.md Issue 5
        //
        // BACKEND SENDS: "Validation Error in KSampler: Return type mismatch... Check input connections and ensure node requirements are met."
        // WE DISPLAY: "Check input connections and ensure node requirements are met."
        //
        // REASON: User needs actionable advice, not verbose error description
        // IMPORTANT: Full context still sent to LLM for analysis
        // ═══════════════════════════════════════════════════════════════

        // Show error context - ONLY display suggestion if available
        errorContext.style.display = 'block';

        // Extract suggestion (remove prefix if present)
        let suggestion = data.suggestion
            ? data.suggestion.replace("💡 SUGGESTION: ", "").trim()
            : null;

        // Extract only the actionable part (last sentence after final period)
        if (suggestion) {
            const sentences = suggestion.split('. ');
            if (sentences.length > 1) {
                // Take the last sentence (the actionable advice)
                suggestion = sentences[sentences.length - 1].trim();
                // Ensure it ends with a period
                if (!suggestion.endsWith('.')) {
                    suggestion += '.';
                }
            }
        }

        errorContext.innerHTML = `
            <div style="padding: 12px; background: rgba(74, 170, 74, 0.1); border-bottom: 1px solid #4a4;">
                <div style="font-weight: bold; color: #4a4; margin-bottom: 8px;">${this.getUIText('suggestion_label')}</div>
                ${suggestion
                ? `<div style="font-size: 13px; color: #ddd; word-break: break-word; margin-bottom: 8px; line-height: 1.5;">${this.escapeHtml(suggestion)}</div>`
                : `<div style="font-size: 13px; color: #888; font-style: italic; margin-bottom: 8px;">${this.getUIText('no_suggestion_available')}</div>`
            }
                <div style="font-size: 11px; color: #888;">🕐 ${timestamp}</div>
                ${nodeContext.node_id ? `
                    <div style="background: rgba(0,0,0,0.2); border-radius: 4px; padding: 8px; margin-top: 8px; font-size: 12px;">
                        <div><strong>${this.getUIText('node_label')}:</strong> ${this.escapeHtml(nodeContext.node_name || 'Unknown')} (#${nodeContext.node_id})</div>
                    </div>
                ` : ''}
                <button id="doctor-analyze-btn" style="width: 100%; background: #2563eb; color: white; border: none; border-radius: 4px; padding: 8px; margin-top: 8px; cursor: pointer; font-weight: bold;">${this.getUIText('analyze_with_ai')}</button>
            </div>
        `;

        // Clear messages and show welcome
        messages.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #888;">
                <div style="font-size: 32px; margin-bottom: 10px;">🤖</div>
                <div>${this.getUIText('click_to_start_debugging')}</div>
            </div>
        `;

        // Attach analyze button listener - use querySelector on errorContext to ensure we find the newly created button
        console.log('[Doctor] Looking for analyze button in errorContext...');
        const analyzeBtn = errorContext.querySelector('#doctor-analyze-btn');
        console.log('[Doctor] Found button:', analyzeBtn);
        if (analyzeBtn) {
            console.log('[Doctor] Attaching click listener to Analyze button');
            analyzeBtn.onclick = () => {
                console.log('[Doctor] Analyze button clicked!');
                this.startAIChat(data);
            };
            console.log('[Doctor] Click listener attached successfully');
        } else {
            console.error('[Doctor] Analyze button NOT found in errorContext!');
            console.error('[Doctor] errorContext innerHTML:', errorContext.innerHTML);
        }

        // Wire up send button
        if (this.sidebarSendBtn && !this.sidebarSendBtn._hasListener) {
            this.sidebarSendBtn.addEventListener('click', () => this.handleSendMessage());
            this.sidebarSendBtn._hasListener = true;
        }

        // Wire up clear button
        if (this.sidebarClearBtn && !this.sidebarClearBtn._hasListener) {
            this.sidebarClearBtn.addEventListener('click', () => this.handleClearChat());
            this.sidebarClearBtn._hasListener = true;
        }

        // Wire up Enter key for input
        if (this.sidebarInput && !this.sidebarInput._hasListener) {
            this.sidebarInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.handleSendMessage();
                }
            });
            this.sidebarInput._hasListener = true;
        }
    }

    async startAIChat(data) {
        try {
            console.log('[Doctor] Starting AI chat with error data:', data);
            console.log('[Doctor] this.currentErrorData:', this.currentErrorData);
            console.log('[Doctor] this.sidebarMessages:', this.sidebarMessages);

            // Add system message
            console.log('[Doctor] Adding system message...');
            this.addChatMessage('system', `Analyzing error: ${data.last_error}`);
            console.log('[Doctor] System message added');

            // Auto-trigger analysis
            console.log('[Doctor] Calling sendToAI...');
            await this.sendToAI(`Analyze this error and provide debugging suggestions:\n\n**Error:** ${data.last_error}\n**Node:** ${data.node_context?.node_name || 'Unknown'}`);
            console.log('[Doctor] sendToAI completed');
        } catch (error) {
            console.error('[Doctor] startAIChat failed:', error);
            console.error('[Doctor] Error stack:', error.stack);
        }
    }

    addChatMessage(role, content) {
        if (!this.sidebarMessages) return;

        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = role === 'user'
            ? 'background: #2b5c92; color: white; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; align-self: flex-end; max-width: 80%;'
            : role === 'assistant'
                ? 'background: #333; color: #eee; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; align-self: flex-start; max-width: 90%; border: 1px solid #444;'
                : 'background: transparent; color: #888; font-size: 11px; font-style: italic; padding: 4px; text-align: center; margin-bottom: 10px;';

        msgDiv.textContent = content;
        msgDiv.dataset.role = role;

        // Clear welcome message if exists
        const welcome = this.sidebarMessages.querySelector('div[style*="text-align: center"]');
        if (welcome) this.sidebarMessages.innerHTML = '';

        // Set flex layout for proper alignment
        if (!this.sidebarMessages.style.display.includes('flex')) {
            this.sidebarMessages.style.display = 'flex';
            this.sidebarMessages.style.flexDirection = 'column';
        }

        this.sidebarMessages.appendChild(msgDiv);
        this.sidebarMessages.scrollTop = this.sidebarMessages.scrollHeight;

        return msgDiv;
    }

    async handleSendMessage() {
        if (!this.sidebarInput || !this.currentErrorData) return;

        const text = this.sidebarInput.value.trim();
        if (!text) return;

        // Add user message
        this.addChatMessage('user', text);
        this.sidebarInput.value = '';

        // Send to AI
        await this.sendToAI(text);
    }

    async sendToAI(text) {
        try {
            console.log('[Doctor] sendToAI called with text:', text.substring(0, 100));

            // Get LLM settings
            const apiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
            const baseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1");
            const model = app.ui.settings.getSettingValue("Doctor.LLM.Model", "gpt-4o");
            const language = app.ui.settings.getSettingValue("Doctor.General.Language", this.language);

            console.log('[Doctor] LLM Settings:', { baseUrl, model, language, hasApiKey: !!apiKey });

            // S6: Get privacy mode from settings
            const privacyMode = app.ui.settings.getSettingValue("Doctor.Privacy.Mode", "basic");

            const payload = {
                messages: [{ role: 'user', content: text }],
                error_context: this.currentErrorData || {},
                intent: 'chat',
                selected_nodes: [],
                api_key: apiKey,
                base_url: baseUrl,
                model: model,
                language: language,
                privacy_mode: privacyMode
            };

            console.log('[Doctor] Payload prepared:', payload);

            // Add placeholder assistant message
            const placeholderMsg = this.addChatMessage('assistant', 'Thinking...');
            console.log('[Doctor] Placeholder message added');

            try {
                let fullContent = '';
                const controller = new AbortController();

                console.log('[Doctor] Calling DoctorAPI.streamChat...');
                await DoctorAPI.streamChat(
                    payload,
                    (chunk) => {
                        console.log('[Doctor] Received chunk:', chunk);
                        if (chunk.delta) {
                            fullContent += chunk.delta;
                            placeholderMsg.textContent = fullContent;
                        }
                    },
                    (error) => {
                        console.error("[Doctor] Stream error:", error);
                        placeholderMsg.textContent = `Error: ${error.message}`;
                    },
                    controller.signal
                );
                console.log('[Doctor] DoctorAPI.streamChat completed');
            } catch (e) {
                console.error('[Doctor] AI request failed:', e);
                console.error('[Doctor] Error stack:', e.stack);
                placeholderMsg.textContent = `Error: ${e.message}`;
            }
        } catch (outerError) {
            console.error('[Doctor] sendToAI outer catch:', outerError);
            console.error('[Doctor] Outer error stack:', outerError.stack);
        }
    }

    handleClearChat() {
        if (!this.sidebarMessages) return;
        this.sidebarMessages.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #888;">
                <div style="font-size: 32px; margin-bottom: 10px;">🤖</div>
                <div>${this.getUIText('chat_cleared')}</div>
            </div>
        `;
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

    /**
     * Capture current workflow context for AI analysis.
     * Returns a simplified workflow structure to avoid token overflow.
     */
    getWorkflowContext() {
        try {
            if (!app || !app.graph) return null;

            // Get full workflow
            const workflow = app.graph.serialize();
            if (!workflow) return null;

            // Simplify to essential info (nodes and links)
            const simplified = {
                nodes: (workflow.nodes || []).map(n => ({
                    id: n.id,
                    type: n.type,
                    title: n.title || n.type,
                    widgets_values: n.widgets_values ? n.widgets_values.slice(0, 5) : undefined, // Limit widget values
                })).slice(0, 50), // Limit to 50 nodes
                links: (workflow.links || []).slice(0, 100), // Limit links
            };

            return JSON.stringify(simplified);
        } catch (e) {
            console.warn('[ComfyUI-Doctor] Failed to capture workflow:', e);
            return null;
        }
    }

    /**
     * Locate and highlight a node on the canvas.
     * Uses ComfyUI's centralized approach similar to NodesMap.
     * @param {string|number} nodeId - The node ID to locate
     */
    locateNodeOnCanvas(nodeId) {
        console.log('[ComfyUI-Doctor] locateNodeOnCanvas called with:', nodeId);
        try {
            const numericId = typeof nodeId === 'string' ? parseInt(nodeId, 10) : nodeId;
            if (isNaN(numericId)) {
                console.warn('[ComfyUI-Doctor] Invalid node ID:', nodeId);
                return;
            }

            if (!app || !app.graph || !app.canvas) {
                console.error('[ComfyUI-Doctor] ComfyUI app, graph or canvas not available');
                return;
            }

            const node = app.graph.getNodeById(numericId);
            if (!node) {
                console.warn('[ComfyUI-Doctor] Node not found in graph:', numericId);
                return;
            }

            console.log('[ComfyUI-Doctor] Found node:', node.title || node.type, 'at pos:', node.pos);

            // Method 1: Use selectNodes (ComfyUI's NodesMap approach) - jumps and selects
            if (typeof app.canvas.selectNodes === 'function') {
                app.canvas.selectNodes([node]);
                console.log('[ComfyUI-Doctor] Used selectNodes method');
            }

            // Method 2: Center on node using offset calculation
            const canvas = app.canvas;
            const nodeX = node.pos[0] + (node.size[0] || 100) / 2;
            const nodeY = node.pos[1] + (node.size[1] || 50) / 2;

            // Get canvas dimensions
            const canvasWidth = canvas.canvas?.width || canvas.bgcanvas?.width || 1920;
            const canvasHeight = canvas.canvas?.height || canvas.bgcanvas?.height || 1080;
            const scale = canvas.ds?.scale || 1;

            // Calculate offset to center the node
            const offsetX = canvasWidth / 2 / scale - nodeX;
            const offsetY = canvasHeight / 2 / scale - nodeY;

            if (canvas.ds) {
                canvas.ds.offset[0] = offsetX;
                canvas.ds.offset[1] = offsetY;
            } else if (canvas.offset) {
                canvas.offset[0] = offsetX;
                canvas.offset[1] = offsetY;
            }

            // Ensure the node is selected (fallback)
            if (!canvas.selected_nodes || !canvas.selected_nodes[node.id]) {
                canvas.selected_nodes = {};
                canvas.selected_nodes[node.id] = node;
            }

            // Redraw canvas
            if (typeof canvas.setDirty === 'function') {
                canvas.setDirty(true, true);
            }
            if (typeof canvas.draw === 'function') {
                canvas.draw(true);
            }

            console.log('[ComfyUI-Doctor] Successfully located node:', numericId);
        } catch (e) {
            console.error('[ComfyUI-Doctor] Failed to locate node:', e);
        }
    }

    /**
     * Trigger AI analysis for an error.
     * @param {object} data - Error data
     * @param {string} resultContainerId - ID of the container to show results
     * @param {HTMLElement} button - The button element to update state
     */
    async triggerAIAnalysis(data, resultContainerId, button) {
        const resultContainer = document.getElementById(resultContainerId);

        // Get LLM settings
        const apiKey = app.ui.settings.getSettingValue("Doctor.LLM.ApiKey", "");
        const baseUrl = app.ui.settings.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1") || "";
        const model = app.ui.settings.getSettingValue("Doctor.LLM.Model", "gpt-4o");
        const language = app.ui.settings.getSettingValue("Doctor.General.Language", this.language);
        const provider = app.ui.settings.getSettingValue("Doctor.LLM.Provider", "openai");

        console.log('[ComfyUI-Doctor] AI Analysis settings:', { apiKey: apiKey ? '***' : 'empty', baseUrl, model, provider, language });

        // Check if this is a local LLM (Ollama/LMStudio) - doesn't need API key
        // Check both provider setting AND URL pattern
        const isLocalProvider = provider === "ollama" || provider === "lmstudio";
        const isLocalUrl = baseUrl.includes("localhost") || baseUrl.includes("127.0.0.1");
        const isLocal = isLocalProvider || isLocalUrl;
        console.log('[ComfyUI-Doctor] Is local LLM:', isLocal, '(provider:', isLocalProvider, ', url:', isLocalUrl, ')');

        // Only require API key for non-local LLMs
        if (!apiKey && !isLocal) {
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div class="ai-response" style="border-color: #ff6b6b;">
                        <h4 style="color: #ff6b6b;">⚠️ Missing API Key</h4>
                        <div>Please configure your API Key in:</div>
                        <div style="margin-top: 8px; font-weight: bold;">ComfyUI Settings → Doctor → AI API Key</div>
                    </div>
                `;
            }
            return;
        }

        // Update button state
        if (button) {
            button.disabled = true;
            button.textContent = "⏳ Analyzing...";
        }

        // Show loading state
        if (resultContainer) {
            resultContainer.innerHTML = `
                <div class="ai-response">
                    <h4>⏳ ${isLocal ? 'Connecting to local LLM...' : 'Connecting to AI...'}</h4>
                    <div>Please wait, this may take a few seconds...</div>
                </div>
            `;
        }

        try {
            // F3: Capture workflow context
            const workflowContext = this.getWorkflowContext();

            // S6: Get privacy mode from settings
            const privacyMode = app.ui.settings.getSettingValue("Doctor.Privacy.Mode", "basic");

            const payload = {
                error: data.last_error || "Unknown Error",
                node_context: data.node_context,
                workflow: workflowContext,
                api_key: apiKey,
                base_url: baseUrl,
                model: model,
                language: language,
                privacy_mode: privacyMode
            };

            const result = await DoctorAPI.analyzeError(payload);

            if (resultContainer) {
                if (result.analysis) {
                    // Use textContent for security (prevent XSS)
                    const analysisDiv = document.createElement('div');
                    analysisDiv.className = 'ai-response';
                    analysisDiv.innerHTML = '<h4>🤖 AI Analysis</h4>';
                    const contentDiv = document.createElement('div');
                    contentDiv.style.whiteSpace = 'pre-wrap';
                    contentDiv.textContent = result.analysis;
                    analysisDiv.appendChild(contentDiv);
                    resultContainer.innerHTML = '';
                    resultContainer.appendChild(analysisDiv);
                } else if (result.error) {
                    resultContainer.innerHTML = `
                        <div class="ai-response" style="border-color: #ff6b6b;">
                            <h4 style="color: #ff6b6b;">⚠️ Error</h4>
                            <div>${this.escapeHtml(result.error)}</div>
                        </div>
                    `;
                } else {
                    resultContainer.innerHTML = `
                        <div class="ai-response">
                            <h4>No analysis returned</h4>
                        </div>
                    `;
                }
            }
        } catch (e) {
            console.error('[ComfyUI-Doctor] AI analysis failed:', e);
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div class="ai-response" style="border-color: #ff6b6b;">
                        <h4 style="color: #ff6b6b;">⚠️ Analysis Failed</h4>
                        <div>${this.escapeHtml(e.message)}</div>
                    </div>
                `;
            }
        } finally {
            // Reset button state
            if (button) {
                button.disabled = false;
                button.textContent = "✨ Analyze with AI";
            }
        }
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

    /**
     * F4: Update statistics panel UI text (i18n)
     * Updates static text labels in the statistics panel
     */
    updateStatisticsPanel() {
        // Update panel summary title
        const statsSummary = document.querySelector('#doctor-statistics-panel > summary');
        if (statsSummary) {
            statsSummary.textContent = `📊 ${this.getUIText('statistics_title')}`;
        }

        // Update stat card labels
        const statsGrid = document.querySelector('#doctor-stats-content .stats-grid');
        if (statsGrid) {
            const totalLabel = statsGrid.querySelector('.stat-card:nth-child(1) .stat-label');
            if (totalLabel) {
                totalLabel.textContent = this.getUIText('stats_total_errors');
            }

            const last24hLabel = statsGrid.querySelector('.stat-card:nth-child(2) .stat-label');
            if (last24hLabel) {
                last24hLabel.textContent = this.getUIText('stats_last_24h');
            }
        }

        // Note: Don't call renderStatistics() here to avoid unnecessary API calls
        // renderStatistics() will be called separately when needed
    }

    /**
     * F4: Render statistics dashboard panel
     * Fetches statistics from /doctor/statistics API and updates the panel
     */
    async renderStatistics() {
        try {
            // Fetch statistics from API
            const result = await DoctorAPI.getStatistics(30);

            if (!result.success) {
                console.warn('[ComfyUI-Doctor] Failed to load statistics:', result.error);
                const container = document.getElementById('doctor-stats-content');
                if (container) {
                    container.innerHTML = `
                        <div class="stats-empty" style="text-align:center;padding:20px;color:#ff6b6b;">
                            ⚠️ ${this.getUIText('stats_error')}
                        </div>
                     `;
                }
                return;
            }

            const stats = result.statistics;

            // Update stat cards
            const totalEl = document.getElementById('stats-total');
            const last24hEl = document.getElementById('stats-24h');

            if (totalEl) totalEl.textContent = stats.total_errors || 0;
            if (last24hEl) last24hEl.textContent = stats.trend?.last_24h || 0;

            // Update resolution rate (inject if missing)
            let resolvedEl = document.getElementById('stats-resolved-count');

            if (!resolvedEl) {
                const topPatternsEl = document.getElementById('doctor-top-patterns');
                if (topPatternsEl) {
                    const resolutionDiv = document.createElement('div');
                    resolutionDiv.style.cssText = "margin-bottom:15px;padding:8px;background:#222;border-radius:4px;";
                    resolutionDiv.innerHTML = `
                        <h5 style="margin:0 0 8px 0;font-size:11px;color:#aaa;">${this.getUIText('stats_resolution_rate')}</h5>
                        <div style="display:flex;justify-content:space-between;font-size:11px;">
                            <span style="color:#4caf50;">✔ ${this.getUIText('stats_resolved')}: <strong id="stats-resolved-count">0</strong></span>
                            <span style="color:#ff9800;">⚠ ${this.getUIText('stats_unresolved')}: <strong id="stats-unresolved-count">0</strong></span>
                            <span style="color:#888;">⚪ ${this.getUIText('stats_ignored')}: <strong id="stats-ignored-count">0</strong></span>
                        </div>
                    `;
                    topPatternsEl.parentNode.insertBefore(resolutionDiv, topPatternsEl);

                    // Re-fetch element
                    resolvedEl = document.getElementById('stats-resolved-count');
                }
            }

            const unresolvedEl = document.getElementById('stats-unresolved-count');
            const ignoredEl = document.getElementById('stats-ignored-count');

            if (resolvedEl) resolvedEl.textContent = stats.resolution_rate?.resolved || 0;
            if (unresolvedEl) unresolvedEl.textContent = stats.resolution_rate?.unresolved || 0;
            if (ignoredEl) ignoredEl.textContent = stats.resolution_rate?.ignored || 0;

            // Render top patterns
            const topPatternsEl = document.getElementById('doctor-top-patterns');
            if (topPatternsEl) {
                if (stats.top_patterns && stats.top_patterns.length > 0) {
                    let html = `<h5>🔥 ${this.getUIText('stats_top_patterns') || 'Top Error Patterns'}</h5>`;
                    stats.top_patterns.forEach(p => {
                        const displayName = this.formatPatternName(p.pattern_id);
                        html += `
                            <div class="pattern-item">
                                <span class="pattern-name">${this.escapeHtml(displayName)}</span>
                                <span class="pattern-count">${p.count}</span>
                            </div>
                        `;
                    });
                    topPatternsEl.innerHTML = html;
                } else {
                    topPatternsEl.innerHTML = `
                        <h5>🔥 ${this.getUIText('stats_top_patterns') || 'Top Error Patterns'}</h5>
                        <div class="stats-empty">${this.getUIText('stats_no_data') || 'No data yet'}</div>
                    `;
                }
            }

            // Render category breakdown
            const categoriesEl = document.getElementById('doctor-category-breakdown');
            if (categoriesEl && stats.category_breakdown) {
                const total = stats.total_errors || 1;
                const colors = {
                    'memory': '#f44',
                    'model_loading': '#ff9800',
                    'workflow': '#2196f3',
                    'framework': '#9c27b0',
                    'generic': '#607d8b'
                };

                let html = `<h5>📁 ${this.getUIText('stats_categories') || 'Categories'}</h5>`;

                Object.entries(stats.category_breakdown).forEach(([category, count]) => {
                    const percent = Math.round((count / total) * 100);
                    const color = colors[category] || '#888';
                    const labelKey = `category_${category}`;
                    const label = this.getUIText(labelKey) || category.replace('_', ' ');

                    html += `
                        <div class="category-bar">
                            <div class="bar-label">
                                <span>${this.escapeHtml(label)}</span>
                                <span>${count} (${percent}%)</span>
                            </div>
                            <div class="bar-track">
                                <div class="bar-fill" style="width: ${percent}%; background: ${color};"></div>
                            </div>
                        </div>
                    `;
                });

                categoriesEl.innerHTML = html;
            }

            console.log('[ComfyUI-Doctor] Statistics rendered:', stats);
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to render statistics:', error);
        }
    }

    /**
     * F4: Format pattern ID to human-readable name
     * "cuda_oom_classic" -> "CUDA OOM"
     */
    formatPatternName(patternId) {
        if (!patternId) return 'Unknown';

        // Convert snake_case to Title Case
        return patternId
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .replace(/Oom/g, 'OOM')
            .replace(/Cuda/g, 'CUDA')
            .replace(/Vae/g, 'VAE')
            .replace(/Llm/g, 'LLM');
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

    /**
     * Creates the Doctor sidebar panel with INFO card and LATEST DIAGNOSIS card
     *
     * UI STRUCTURE (DO NOT MODIFY):
     * ┌─────────────────────────────────────┐
     * │ ComfyUI Doctor            [×]       │ <- Header
     * ├─────────────────────────────────────┤
     * │ INFO                                │ <- Info Card (guides user to use AI)
     * │ Click 🏥 Doctor button...           │    - Title: i18n 'info_title'
     * │                                     │    - Message: i18n 'info_message'
     * ├─────────────────────────────────────┤
     * │ LATEST DIAGNOSIS                    │ <- Log Card (updated by updateLogCard)
     * │ [Error/Suggestion/Node/Button]      │    - ID: 'doctor-latest-log'
     * └─────────────────────────────────────┘
     *
     * IMPORTANT NOTES:
     * - INFO card content uses i18n keys: 'info_title', 'info_message'
     * - INFO card is updated by updateInfoCard() on language change
     * - LATEST DIAGNOSIS card is updated by updateLogCard(data)
     * - DO NOT remove #doctor-latest-log ID (required by updateLogCard)
     */
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

        // ═══════════════════════════════════════════════════════════════
        // INFO CARD - Guide users to use left sidebar for AI debugging
        // ═══════════════════════════════════════════════════════════════
        // STRUCTURE:
        //   <div class="doctor-card">
        //     <div class="doctor-card-title">INFO</div>
        //     <div class="doctor-card-body">Click 🏥 Doctor button...</div>
        //   </div>
        //
        // I18N KEYS USED:
        //   - info_title: "INFO" (or localized equivalent)
        //   - info_message: "Click 🏥 Doctor button (left sidebar)..."
        //
        // UPDATED BY: updateInfoCard() when language changes
        // ═══════════════════════════════════════════════════════════════
        const infoCard = document.createElement('div');
        infoCard.className = 'doctor-card';
        infoCard.innerHTML = `
            <div class="doctor-card-title">${this.getUIText('info_title')}</div>
            <div class="doctor-card-body" style="font-size:12px;color:#888;line-height:1.6;">
                ${this.getUIText('info_message')}
            </div>
        `;
        content.appendChild(infoCard);

        // ═══════════════════════════════════════════════════════════════
        // LATEST DIAGNOSIS CARD - Shows error analysis results
        // ═══════════════════════════════════════════════════════════════
        // INITIAL STATE: Shows "no errors" message
        // UPDATED BY: updateLogCard(data) when new error detected
        //
        // ID REQUIRED: 'doctor-latest-log' (DO NOT CHANGE)
        //
        // FINAL STRUCTURE (after updateLogCard):
        //   <div class="doctor-card error" id="doctor-latest-log">
        //     <div class="doctor-card-title">LATEST DIAGNOSIS</div>
        //     <div class="doctor-card-body">
        //       <!-- Error Summary Section -->
        //       <!-- Collapsible Full Error Details -->
        //       <!-- Suggestion Section (green theme) -->
        //       <!-- Timestamp -->
        //       <!-- Node Context -->
        //       <!-- Locate Node on Canvas Button -->
        //     </div>
        //   </div>
        // ═══════════════════════════════════════════════════════════════
        const logCard = document.createElement('div');
        logCard.className = 'doctor-card';
        logCard.innerHTML = `<div class="doctor-card-body" style="color:#777;text-align:center">${this.getUIText('no_errors')}</div>`;
        logCard.id = 'doctor-latest-log';  // REQUIRED ID - DO NOT REMOVE
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

    /**
     * Extract error summary and suggestion from raw error data
     *
     * SEPARATES ERROR AND SUGGESTION (CRITICAL - DO NOT MERGE THEM AGAIN)
     *
     * PURPOSE:
     *   Prevents information overload by separating concerns:
     *   - errorSummary: Brief 1-2 line summary for quick scanning
     *   - fullError: Complete error traceback (may be truncated)
     *   - suggestion: AI-generated fix recommendation (already cleaned by backend)
     *
     * RETURNS: {
     *   errorSummary: string,   // Brief error summary (red theme in UI)
     *   fullError: string,       // Full error text (collapsible in UI)
     *   suggestion: string,      // AI suggestion (green theme in UI)
     *   hasLongError: boolean    // Whether to show collapse UI
     * }
     *
     * ERROR SUMMARY LOGIC:
     *   - Validation errors: Extract first "* NodeName" + "- ErrorDetail"
     *   - Other errors: Use last line (usually "Exception: Message")
     *   - Fallback: "Unknown Error"
     *
     * SUGGESTION HANDLING:
     *   - Backend already cleaned via regex fix (analyzer.py:112)
     *   - Only removes "💡 SUGGESTION: " prefix here
     *   - NO error log pollution (fixed 2025-12-31)
     *
     * RELATED FIXES:
     *   - Issue 1: Error panel information overload (2025-12-31)
     *   - Issue 4: Suggestion message contains error logs (2025-12-31)
     *   - See: .planning/ERROR_PANEL_UI_FIXES.md
     */
    extractErrorInfo(data) {
        const result = {
            errorSummary: null,
            fullError: null,
            suggestion: null,
            hasLongError: false
        };

        // ═══════════════════════════════════════════════════════════════
        // EXTRACT SUGGESTION (ONLY ACTIONABLE ADVICE) - RIGHT ERROR PANEL
        // ═══════════════════════════════════════════════════════════════
        // DO NOT REMOVE OR MODIFY without consulting .planning/ERROR_PANEL_UI_FIXES.md Issue 5
        //
        // USED BY: Right error panel (updateLogCard method)
        // SAME LOGIC AS: Left sidebar (updateSidebarTab method, Lines 264-295)
        //
        // Backend provides full suggestion (e.g., "Validation Error in KSampler: ... Check input connections...")
        // Frontend extracts ONLY the last sentence (actionable advice)
        // Example: "Check input connections and ensure node requirements are met."
        //
        // REASON: Consistent UX - both panels show concise suggestions
        // IMPORTANT: Full context still sent to LLM for analysis
        // ═══════════════════════════════════════════════════════════════
        if (data.suggestion) {
            let suggestion = data.suggestion.replace("💡 SUGGESTION: ", "").trim();

            // Extract only the actionable part (last sentence after final period)
            const sentences = suggestion.split('. ');
            if (sentences.length > 1) {
                // Take the last sentence (the actionable advice)
                suggestion = sentences[sentences.length - 1].trim();
                // Ensure it ends with a period
                if (!suggestion.endsWith('.')) {
                    suggestion += '.';
                }
            }

            result.suggestion = suggestion;
        }

        // ═══════════════════════════════════════════════════════════════
        // EXTRACT ERROR SUMMARY (BRIEF 1-2 LINE VERSION)
        // ═══════════════════════════════════════════════════════════════
        if (data.last_error) {
            const fullError = data.last_error.trim();
            result.fullError = fullError;
            const lines = fullError.split('\n');

            // --- Validation Errors ---
            // Extract first node error (not all 12+ repeated errors)
            if (fullError.includes('Failed to validate prompt')) {
                // Look for lines starting with "* " (node error details)
                const nodeErrorLine = lines.find(line => line.trim().startsWith('* '));
                const detailLine = lines.find(line => line.trim().startsWith('- '));

                if (nodeErrorLine && detailLine) {
                    result.errorSummary = `${nodeErrorLine.trim()}\n${detailLine.trim()}`;
                } else if (nodeErrorLine) {
                    result.errorSummary = nodeErrorLine.trim();
                } else {
                    // Count validation errors
                    const errorCount = (fullError.match(/Failed to validate prompt for output/g) || []).length;
                    result.errorSummary = `Validation failed for ${errorCount} output(s)`;
                }

                // Check if error is too long (more than 500 characters)
                result.hasLongError = fullError.length > 500;
            } else if (lines.length > 0) {
                // --- Other Errors ---
                // Use last line (usually Exception: Message)
                result.errorSummary = lines[lines.length - 1];
                result.hasLongError = fullError.length > 500;
            }
        }

        if (!result.errorSummary) result.errorSummary = this.getUIText('unknown_error');

        return result;
    }

    /**
     * Truncate long error text for display (show first and last parts)
     *
     * PREVENTS INFORMATION OVERLOAD (Issue 1: Fixed 2025-12-31)
     *
     * STRATEGY:
     *   - Short text (≤500 chars): Show in full, no truncation
     *   - Few lines but long (≤10 lines): Character-based truncation
     *   - Many lines (>10 lines): Show first 3 + last 3, omit middle
     *
     * RETURNS: {
     *   truncated: string,   // Truncated text for display
     *   isTruncated: boolean // Whether truncation was applied
     * }
     *
     * EXAMPLE OUTPUT (many lines):
     *   Line 1
     *   Line 2
     *   Line 3
     *
     *   ... (47 lines omitted) ...
     *
     *   Line 48
     *   Line 49
     *   Line 50
     *
     * USED BY: updateLogCard() when hasLongError === true
     * DISPLAY: Inside <details> element (collapsible)
     *
     * DO NOT MODIFY: Carefully tuned thresholds (500 chars, 10 lines, 3+3)
     */
    truncateError(text, maxLength = 500) {
        if (text.length <= maxLength) {
            return { truncated: text, isTruncated: false };
        }

        const lines = text.split('\n');

        // ═══════════════════════════════════════════════════════════════
        // CASE 1: Few lines but long (≤10 lines, >500 chars)
        // ═══════════════════════════════════════════════════════════════
        // Example: Single-line error with 1000+ character message
        // Strategy: Character-based split (first half + last half)
        // ═══════════════════════════════════════════════════════════════
        if (lines.length <= 10) {
            const halfLength = Math.floor(maxLength / 2);
            return {
                truncated: text.substring(0, halfLength) + `\n\n${this.getUIText('truncated')}\n\n` + text.substring(text.length - halfLength),
                isTruncated: true
            };
        }

        // ═══════════════════════════════════════════════════════════════
        // CASE 2: Many lines (>10 lines)
        // ═══════════════════════════════════════════════════════════════
        // Example: 50-line validation error with 12 repeated errors
        // Strategy: Show first 3 + last 3, omit middle
        // Result: User sees start/end context, avoids scroll fatigue
        // ═══════════════════════════════════════════════════════════════
        const firstLines = lines.slice(0, 3).join('\n');
        const lastLines = lines.slice(-3).join('\n');
        const omittedCount = lines.length - 6;

        return {
            truncated: `${firstLines}\n\n... (${this.getUIText('lines_omitted').replace('{0}', omittedCount)}) ...\n\n${lastLines}`,
            isTruncated: true
        };
    }

    /**
     * Update LATEST DIAGNOSIS card with error analysis results
     *
     * ═══════════════════════════════════════════════════════════════════════════
     * CRITICAL UI COMPONENT - STRUCTURE DOCUMENTATION
     * ═══════════════════════════════════════════════════════════════════════════
     *
     * VISUAL LAYOUT (DO NOT MODIFY STRUCTURE):
     *
     * ┌─────────────────────────────────────────────────────────────────────┐
     * │ LATEST DIAGNOSIS                                     <- Title       │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ Error                                                <- Section 1    │
     * │ KSampler 25: Return type mismatch...  (RED #ff8888)                 │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ ▶ Show full error details                           <- Section 2    │
     * │   (Collapsible <details> with full traceback)                       │
     * │   - Only shown if hasLongError === true                             │
     * │   - Truncated using truncateError() (first 3 + last 3 lines)        │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ 💡 Suggestion                                        <- Section 3    │
     * │ Validation Error in KSampler: Return type...  (GREEN #afa)          │
     * │   - Background: #1a3a1a (dark green)                                │
     * │   - Border-left: 3px solid #4a4                                     │
     * │   - SEPARATED from error (Issue 2: Fixed 2025-12-31)                │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ 2:30:45 PM                                           <- Timestamp   │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ Node #25: KSampler                                   <- Node Context│
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ [🔍 Locate Node on Canvas]                           <- Action Btn  │
     * │   - ID: doctor-locate-btn                                           │
     * │   - data-node attribute: node_id                                    │
     * │   - onClick: locateNodeOnCanvas(nodeId)                             │
     * │   - i18n: 'locate_node_btn'                                         │
     * ├─────────────────────────────────────────────────────────────────────┤
     * │ 💡 Open the Doctor sidebar (left panel) to analyze... <- Hint       │
     * │   - i18n: 'sidebar_hint'                                            │
     * └─────────────────────────────────────────────────────────────────────┘
     *
     * ═══════════════════════════════════════════════════════════════════════════
     * COLOR SCHEME (DO NOT CHANGE):
     * ═══════════════════════════════════════════════════════════════════════════
     * - Error Summary: #ff8888 (light red) - Bold, prominent
     * - Full Error Details: #ccc on #1a1a1a - Monospace, scrollable
     * - Suggestion Box: #afa on #1a3a1a - Green theme, distinct
     * - Suggestion Border: 3px solid #4a4 - Left accent
     * - Timestamp: #666 - Subtle
     * - Node Context: #222 background - Monospace
     * - Hint Text: #888 - Italic, centered
     *
     * ═══════════════════════════════════════════════════════════════════════════
     * I18N KEYS USED:
     * ═══════════════════════════════════════════════════════════════════════════
     * - locate_node_btn: "Locate Node on Canvas" (button text)
     * - sidebar_hint: "Open the Doctor sidebar..." (bottom hint)
     *
     * ═══════════════════════════════════════════════════════════════════════════
     * IMPORTANT FIXES APPLIED (DO NOT REVERT):
     * ═══════════════════════════════════════════════════════════════════════════
     * 1. Error and suggestion SEPARATED (Issue 2: 2025-12-31)
     *    - Before: Mixed in one block, hard to distinguish
     *    - After: Separate sections with color coding
     *
     * 2. Long errors TRUNCATED (Issue 1: 2025-12-31)
     *    - Before: 12+ repeated validation errors shown in full
     *    - After: Collapsible <details> with smart truncation
     *
     * 3. Suggestion NO LONGER contains error logs (Issue 4: 2025-12-31)
     *    - Before: Massive error block polluted suggestion
     *    - After: Backend regex fix ensures only minimal info
     *
     * SEE: .planning/ERROR_PANEL_UI_FIXES.md for full documentation
     * ═══════════════════════════════════════════════════════════════════════════
     */
    updateLogCard(data) {
        const container = document.getElementById('doctor-latest-log');
        if (!container) return;

        const { errorSummary, fullError, suggestion, hasLongError } = this.extractErrorInfo(data);

        let html = `
            <div class="doctor-card-title">${this.getUIText('latest_diagnosis_title')}</div>
            <div class="doctor-card-body">
        `;

        // ═══════════════════════════════════════════════════════════════
        // SECTION 1: ERROR SUMMARY (Brief, bold, red theme)
        // ═══════════════════════════════════════════════════════════════
        // Purpose: Quick scanning - user sees key error in 1-2 lines
        // Color: #ff8888 (light red) for error indication
        // Font: Bold, 12px for prominence
        // DO NOT merge with suggestion section (Issue 2 fix)
        // ═══════════════════════════════════════════════════════════════
        html += `
            <div style="margin-bottom:12px;">
                <div style="font-size:10px;color:#999;text-transform:uppercase;margin-bottom:4px;">${this.getUIText('error_label')}</div>
                <div style="font-weight:bold;color:#ff8888;font-size:12px;line-height:1.4;">${this.escapeHtml(errorSummary)}</div>
            </div>
        `;

        // ═══════════════════════════════════════════════════════════════
        // SECTION 2: FULL ERROR DETAILS (Collapsible if long)
        // ═══════════════════════════════════════════════════════════════
        // Shown only if: hasLongError === true (>500 chars)
        // Display: HTML <details> element (native collapse/expand)
        // Truncation: First 3 + last 3 lines via truncateError()
        // Style: Monospace <pre>, dark background #1a1a1a
        // Purpose: Avoid information overload (Issue 1 fix)
        // ═══════════════════════════════════════════════════════════════
        if (hasLongError && fullError) {
            const { truncated, isTruncated } = this.truncateError(fullError);
            html += `
                <details style="margin-bottom:12px;">
                    <summary style="cursor:pointer;color:#aaa;font-size:11px;user-select:none;">
                        ${isTruncated ? this.getUIText('show_full_error') : this.getUIText('show_error_details')}
                    </summary>
                    <pre style="background:#1a1a1a;padding:8px;border-radius:4px;font-size:10px;color:#ccc;overflow-x:auto;margin-top:6px;white-space:pre-wrap;word-wrap:break-word;">${this.escapeHtml(fullError)}</pre>
                </details>
            `;
        }

        // ═══════════════════════════════════════════════════════════════
        // SECTION 3: SUGGESTION (Green theme, SEPARATED from error)
        // ═══════════════════════════════════════════════════════════════
        // CRITICAL: DO NOT merge with error section (Issue 2 fix)
        // Background: #1a3a1a (dark green) - distinct from error
        // Border: 3px solid #4a4 on left - visual accent
        // Text: #afa (light green) - easy to read
        // Content: Already cleaned by backend regex (analyzer.py:112)
        //          - validation_error: Only node name + error detail
        //          - Other errors: Use i18n template
        // NO error log pollution (Issue 4 fix - 2025-12-31)
        // ═══════════════════════════════════════════════════════════════
        if (suggestion) {
            html += `
                <div style="margin-bottom:12px;padding:8px;background:#1a3a1a;border-left:3px solid #4a4;border-radius:4px;">
                    <div style="font-size:10px;color:#8f8;text-transform:uppercase;margin-bottom:4px;">${this.getUIText('suggestion_label')}</div>
                    <div style="color:#afa;font-size:11px;line-height:1.5;">${this.escapeHtml(suggestion)}</div>
                </div>
            `;
        }

        // ═══════════════════════════════════════════════════════════════
        // SECTION 4: TIMESTAMP
        // ═══════════════════════════════════════════════════════════════
        // Format: Local time (e.g., "2:30:45 PM")
        // Color: #666 (subtle, non-intrusive)
        // ═══════════════════════════════════════════════════════════════
        html += `<div style="font-size:11px;color:#666;margin-bottom:8px;">${new Date(data.timestamp).toLocaleTimeString()}</div>`;

        // ═══════════════════════════════════════════════════════════════
        // SECTION 5: NODE CONTEXT + LOCATE BUTTON
        // ═══════════════════════════════════════════════════════════════
        // Node Info: "Node #25: KSampler" (monospace, dark bg)
        // Button: "🔍 Locate Node on Canvas"
        //   - ID: doctor-locate-btn (required for event binding)
        //   - data-node: node_id (used by locateNodeOnCanvas)
        //   - i18n: 'locate_node_btn'
        // Event: Re-bound after innerHTML update (see below)
        // ═══════════════════════════════════════════════════════════════
        if (data.node_context && data.node_context.node_id) {
            const safeNodeId = this.escapeHtml(String(data.node_context.node_id));
            const safeNodeName = this.escapeHtml(data.node_context.node_name || 'Unknown');
            html += `
                <div style="background:#222;padding:6px;border-radius:4px;margin-bottom:8px;font-family:monospace;font-size:11px;">
                    ${this.getUIText('node_label')} #${safeNodeId}: ${safeNodeName}
                </div>
                <button class="doctor-action-btn" id="doctor-locate-btn" data-node="${safeNodeId}">
                    🔍 ${this.getUIText('locate_node_btn')}
                </button>
            `;
        }

        // ═══════════════════════════════════════════════════════════════
        // SECTION 6: SIDEBAR HINT (Bottom guidance text)
        // ═══════════════════════════════════════════════════════════════
        // Purpose: Guide users to open left sidebar for AI analysis
        // i18n: 'sidebar_hint'
        // Style: Italic, centered, subtle gray
        // ═══════════════════════════════════════════════════════════════
        html += `
            <div style="margin-top:10px;font-size:11px;color:#888;text-align:center;font-style:italic;">
                💡 ${this.getUIText('sidebar_hint')}
            </div>
        `;

        html += `</div>`;

        container.innerHTML = html;
        container.classList.add('error');

        // ═══════════════════════════════════════════════════════════════
        // RE-BIND LOCATE BUTTON EVENT (Required after innerHTML update)
        // ═══════════════════════════════════════════════════════════════
        // Why: innerHTML wipes event listeners, must re-attach
        // Button ID: doctor-locate-btn
        // Event: Click → locateNodeOnCanvas(nodeId)
        // ═══════════════════════════════════════════════════════════════
        const btn = container.querySelector('#doctor-locate-btn');
        if (btn) {
            btn.onclick = () => {
                const nodeId = btn.getAttribute('data-node');
                this.locateNodeOnCanvas(nodeId);
            };
        }
    }
}
