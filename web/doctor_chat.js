
import { app } from "../../../scripts/app.js";
import { DoctorAPI } from "./doctor_api.js";
import { doctorContext } from "./doctor_state.js";

// S5: Local bundled assets with CDN fallback (pinned versions)
// Versions: marked@15.0.4, highlight.js@11.9.0
const LOCAL_MARKED = "/extensions/ComfyUI-Doctor/lib/marked.min.js";
const LOCAL_HIGHLIGHT = "/extensions/ComfyUI-Doctor/lib/highlight.min.js";
const LOCAL_HIGHLIGHT_CSS = "/extensions/ComfyUI-Doctor/lib/github-dark.min.css";
const CDN_MARKED = "https://cdn.jsdelivr.net/npm/marked@15.0.4/marked.min.js";
const CDN_HIGHLIGHT = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js";
const CDN_HIGHLIGHT_CSS = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css";

export class ChatPanel {
    constructor(options = {}) {
        console.log('[ChatPanel] Constructor called with options:', options);
        this.container = options.container || null;
        this.initialError = options.errorData || null;

        console.log('[ChatPanel] Container:', this.container);
        console.log('[ChatPanel] Initial error data:', this.initialError);

        // No local message state! Use context.
        this.unsubscribers = [];
        this.abortController = null; // For cancelling ongoing requests
        this.observers = null; // For ResizeObserver and MutationObserver
        this.lastContentHash = ''; // For content deduplication

        // Load dependencies
        this.loadAssets();

        // Create UI
        console.log('[ChatPanel] Creating interface...');
        this.element = this.createInterface();
        console.log('[ChatPanel] Interface created:', this.element);

        if (this.container) {
            console.log('[ChatPanel] Appending to container...');
            this.container.appendChild(this.element);
            console.log('[ChatPanel] Appended. Container innerHTML length:', this.container.innerHTML.length);

            // Verify the input box is in the DOM
            const inputBox = this.container.querySelector('.doctor-chat-input');
            if (inputBox) {
                console.log('[ChatPanel] ✅ Input box successfully added to DOM');
                console.log('[ChatPanel] Input box computed style:', window.getComputedStyle(inputBox).display);
            } else {
                console.error('[ChatPanel] ❌ ERROR: Input box NOT found in DOM after append!');
            }
        } else {
            console.warn('[ChatPanel] No container provided!');
        }

        // Initialize Context Listeners
        this.initListeners();

        // Initialize with error context if available
        if (this.initialError) {
            console.log('[ChatPanel] Initializing conversation with error context');
            this.initConversation(this.initialError);
        }

        // Setup Canvas listeners for "Context Awareness"
        this.setupCanvasListeners();

        console.log('[ChatPanel] Constructor complete. Element classes:', this.element.className);
    }

    sanitizeHtml(unsafeHtml) {
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(unsafeHtml, 'text/html');

            // Remove dangerous tags
            const blockedTags = ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta'];
            blockedTags.forEach(tag => {
                doc.querySelectorAll(tag).forEach(node => node.remove());
            });

            // Remove event handlers and javascript: URLs
            doc.querySelectorAll('*').forEach(node => {
                [...node.attributes].forEach(attr => {
                    const name = attr.name.toLowerCase();
                    const value = attr.value || '';
                    if (name.startsWith('on')) {
                        node.removeAttribute(attr.name);
                    }
                    if ((name === 'src' || name === 'href') && /^javascript:/i.test(value.trim())) {
                        node.removeAttribute(attr.name);
                    }
                });
            });

            return doc.body.innerHTML;
        } catch (e) {
            console.warn('[ChatPanel] sanitizeHtml failed, falling back to plain text:', e);
            const div = document.createElement('div');
            div.textContent = unsafeHtml;
            return div.innerHTML;
        }
    }

    destroy() {
        console.log('[ChatPanel] Destroying panel and cleaning up resources');

        // Abort ongoing streams
        if (this.abortController) {
            console.log('[ChatPanel] Aborting ongoing request');
            this.abortController.abort();
            this.abortController = null;
        }

        // Disconnect observers
        if (this.observers) {
            console.log('[ChatPanel] Disconnecting observers');
            if (this.observers.resizeObserver) {
                this.observers.resizeObserver.disconnect();
            }
            if (this.observers.mutationObserver) {
                this.observers.mutationObserver.disconnect();
            }
            this.observers = null;
        }

        // Unsubscribe from context
        this.unsubscribers.forEach(unsub => unsub());
        this.unsubscribers = [];

        console.log('[ChatPanel] Cleanup complete');
    }

    setupCanvasListeners() {
        // We poll for selection change or hook into app.canvas.onSelectionChange
        // Since LiteGraph doesn't have a standardized event dispatcher for this that is easily accessible without monkeypatching,
        // we will implement a lightweight poller or hook.

        // Hooking app.graph.onNodeAdded etc is possible but selection is Canvas level.
        // Let's monkeypatch app.canvas.selectNode/deselectNode if they exist, specific to ComfyUI's graph.

        // Safer approach: Periodic check when panel is open ?? No, resource intensive.
        // Better: Hook logic in a safe way.

        const originalSelect = app.canvas.selectNode;
        const originalDeselect = app.canvas.deselectNode;
        const self = this;

        // Note: this might conflict if multiple instances exist, but ChatPanel is likely singleton-ish in usage.
        // Ideally this should be in doctor_ui.js global init, but here is fine for now.

        // We won't monkeypatch here to avoid side effects. 
        // Instead, we trust doctor_ui.js to update the context or we rely on standard events if found.
        // For now, let's leave this placeholder or implement a simple check on mouseup which is common for selection.

        this.element.addEventListener('mouseenter', () => {
            // Refresh selection when checking panel?
            this.updateSelectedNodes();
        });

        // Or listen to global mouse up on window to check selection?
        // window.addEventListener('mouseup', () => this.updateSelectedNodes());
    }

    updateSelectedNodes() {
        if (app.canvas && app.canvas.selected_nodes) {
            const nodes = Object.values(app.canvas.selected_nodes).map(n => ({
                id: n.id,
                type: n.type,
                title: n.title,
                properties: n.properties
            }));
            doctorContext.setSelectedNodes(nodes);
        } else {
            doctorContext.setSelectedNodes([]);
        }
    }

    initListeners() {
        this.unsubscribers.push(
            doctorContext.subscribe('messageAdded', (msg) => this.renderMessage(msg)),
            doctorContext.subscribe('stateChanged', (state) => this.updateUIState(state)),
            doctorContext.subscribe('change:selectedNodes', (nodes) => this.updateContextInfo(nodes))
        );
    }

    async loadAssets() {
        // S5: Load CSS - try local first, fallback to CDN
        if (!document.getElementById('hljs-style')) {
            const link = document.createElement('link');
            link.id = 'hljs-style';
            link.rel = 'stylesheet';
            link.href = LOCAL_HIGHLIGHT_CSS;
            link.onerror = () => {
                console.warn('[ChatPanel] Local highlight.js CSS failed, using CDN fallback');
                link.href = CDN_HIGHLIGHT_CSS;
            };
            document.head.appendChild(link);
            console.log('[ChatPanel] Loading highlight.js CSS from:', link.href);
        }

        // Load custom chat CSS
        if (!document.getElementById('doctor-chat-css')) {
            const chatCss = document.createElement('link');
            chatCss.id = 'doctor-chat-css';
            chatCss.rel = 'stylesheet';
            chatCss.href = '/extensions/ComfyUI-Doctor/doctor_chat.css';
            document.head.appendChild(chatCss);
            console.log('[ChatPanel] Loading chat CSS from:', chatCss.href);
        }

        // S5: Load JS libraries - try local first, fallback to CDN
        if (!window.marked) {
            try {
                await this.loadScript(LOCAL_MARKED);
                console.log('[ChatPanel] ✅ Loaded marked.js from local bundle');
            } catch (e) {
                console.warn('[ChatPanel] Local marked.js failed, using CDN fallback');
                await this.loadScript(CDN_MARKED);
            }
        }

        if (!window.hljs) {
            try {
                await this.loadScript(LOCAL_HIGHLIGHT);
                console.log('[ChatPanel] ✅ Loaded highlight.js from local bundle');
            } catch (e) {
                console.warn('[ChatPanel] Local highlight.js failed, using CDN fallback');
                await this.loadScript(CDN_HIGHLIGHT);
            }
        }
    }

    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    createInterface() {
        console.log('[ChatPanel] Creating interface HTML structure...');
        const panel = document.createElement('div');
        panel.className = 'doctor-chat-panel';

        panel.innerHTML = `
            <div class="doctor-chat-header">
                <div class="header-main">
                    <span>🤖 Doctor AI</span>
                    <span class="doctor-context-badge" id="doctor-context-badge" style="display:none">0 nodes</span>
                </div>
                <div class="doctor-chat-controls">
                    <button id="doctor-chat-clear" title="Clear History">🗑️</button>
                    <button id="doctor-chat-expand" title="Expand">⤢</button>
                </div>
            </div>

            <div class="doctor-chat-messages" id="doctor-chat-messages">
                <!-- Messages go here -->
            </div>

            <div class="doctor-context-actions" id="doctor-context-actions">
                <!-- Quick buttons injected here -->
            </div>

            <div class="doctor-chat-input-area">
                <div class="doctor-input-wrapper">
                    <textarea class="doctor-chat-input" placeholder="Ask AI..." rows="1"></textarea>
                    <div class="doctor-input-actions">
                         <button class="doctor-chat-send-btn" title="Send">➤</button>
                    </div>
                </div>
                <div class="doctor-chat-toolbar">
                     <button class="tool-btn" data-intent="regenerate" title="Regenerate Last">🔄</button>
                     <button class="tool-btn dangerous" data-intent="stop" title="Stop Generating" style="display:none">⏹️</button>
                </div>
            </div>
        `;

        console.log('[ChatPanel] HTML structure created. Panel element:', panel);
        console.log('[ChatPanel] Input area found:', panel.querySelector('.doctor-chat-input-area'));
        console.log('[ChatPanel] Textarea found:', panel.querySelector('.doctor-chat-input'));

        // Event Listeners
        const input = panel.querySelector('.doctor-chat-input');
        const sendBtn = panel.querySelector('.doctor-chat-send-btn');
        const clearBtn = panel.querySelector('#doctor-chat-clear');
        const expandBtn = panel.querySelector('#doctor-chat-expand');
        const regenBtn = panel.querySelector('[data-intent="regenerate"]');
        const stopBtn = panel.querySelector('[data-intent="stop"]');

        // Bind Elements
        this.inputElement = input;
        this.messagesContainer = panel.querySelector('#doctor-chat-messages');
        this.sendButton = sendBtn;
        this.stopButton = stopBtn;
        this.contextBadge = panel.querySelector('#doctor-context-badge');
        this.contextActions = panel.querySelector('#doctor-context-actions');

        // Setup smart auto-scroll (ComfyUI-Copilot pattern)
        this.setupAutoScroll();

        // Auto-resize
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });

        // Send on Enter
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });

        sendBtn.addEventListener('click', () => this.handleSend());

        clearBtn.addEventListener('click', () => {
            // Logic to clear context
            if (confirm("Clear conversation?")) {
                doctorContext.clearMessages();
                this.messagesContainer.innerHTML = '';
                if (this.initialError) {
                    this.initConversation(this.initialError);
                }
            }
        });

        expandBtn.addEventListener('click', () => panel.classList.toggle('expanded'));

        // Toolbar Buttons
        regenBtn.addEventListener('click', () => this.handleRegenerate());
        stopBtn.addEventListener('click', () => this.handleStop());

        return panel;
    }

    updateUIState(state) {
        if (state.isProcessing) {
            this.sendButton.disabled = true;
            this.stopButton.style.display = 'inline-block';
            this.inputElement.disabled = true;
        } else {
            this.sendButton.disabled = false;
            this.stopButton.style.display = 'none';
            this.inputElement.disabled = false;
            this.inputElement.focus();
        }
    }

    updateContextInfo(nodes) {
        if (!nodes || nodes.length === 0) {
            this.contextBadge.style.display = 'none';
            this.contextActions.innerHTML = '';
            return;
        }

        this.contextBadge.textContent = `${nodes.length} Node${nodes.length > 1 ? 's' : ''}`;
        this.contextBadge.style.display = 'inline-block';

        // Add quick action if 1 node
        if (nodes.length === 1) {
            const node = nodes[0];
            this.contextActions.innerHTML = `
                <button class="context-pill" onclick="this.dispatchEvent(new CustomEvent('explain-node', {bubbles:true}))">
                    ✨ Explain ${node.type}
                </button>
            `;

            // Re-bind event manually or use delegation
            this.contextActions.querySelector('button').addEventListener('click', () => {
                this.handleSend(`Explain what the node "${node.title || node.type}" does and how to use it.`, 'explain_node');
            });
        }
    }

    renderMessage(msg) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `doctor-chat-message ${msg.role}`;

        // Metadata ID for later updates
        msgDiv.dataset.id = msg.id;

        const content = msg.content;

        if (msg.role === 'assistant' || msg.role === 'system') {
            if (window.marked) {
                const raw = window.marked.parse(content);
                msgDiv.innerHTML = this.sanitizeHtml(raw);
                if (window.hljs) {
                    msgDiv.querySelectorAll('pre code').forEach((block) => {
                        window.hljs.highlightElement(block);
                    });
                }
                this.addCopyButtons(msgDiv);
            } else {
                msgDiv.textContent = content;
            }
        } else {
            msgDiv.textContent = content;
        }

        this.messagesContainer.appendChild(msgDiv);
        this.scrollToBottom();
        return msgDiv;
    }

    // Legacy support for stream updates - now we just update the last assistant message in DOM
    // or we should update store?? 
    // For streaming, we usually append content to the LAST message in the store and re-render OR just update DOM.
    // Updating DOM is smoother. Updating store is correct.
    // Let's implement a "streamUpdate" method.

    setupAutoScroll() {
        // ComfyUI-Copilot pattern: Smart auto-scroll with ResizeObserver + MutationObserver
        // Only scrolls if user is already at bottom, preserves scroll position otherwise
        if (!this.messagesContainer) return;

        const updateScrollHeight = () => {
            requestAnimationFrame(() => {
                // Only auto-scroll if already at bottom
                const isAtBottom = this.messagesContainer.scrollHeight -
                    this.messagesContainer.scrollTop -
                    this.messagesContainer.clientHeight < 1;

                if (isAtBottom) {
                    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
                }
            });
        };

        const resizeObserver = new ResizeObserver(updateScrollHeight);
        const mutationObserver = new MutationObserver(updateScrollHeight);

        resizeObserver.observe(this.messagesContainer);
        mutationObserver.observe(this.messagesContainer, {
            childList: true,
            subtree: true
        });

        // Store for cleanup
        this.observers = { resizeObserver, mutationObserver };
    }

    updateLastMessage(content) {
        // Content hashing for deduplication (ComfyUI-Copilot pattern)
        const contentHash = content.slice(0, 100);
        if (this.lastContentHash === contentHash) {
            return; // Skip duplicate renders
        }
        this.lastContentHash = contentHash;

        // Find last message in DOM
        const lastMsg = this.messagesContainer.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('assistant')) {
            if (window.marked) {
                const raw = window.marked.parse(content);
                lastMsg.innerHTML = this.sanitizeHtml(raw);
                if (window.hljs) {
                    lastMsg.querySelectorAll('pre code').forEach((block) => {
                        window.hljs.highlightElement(block);
                    });
                }
                this.addCopyButtons(lastMsg);
            } else {
                lastMsg.textContent = content;
            }
            // Auto-scroll is handled by observers, no need to call scrollToBottom()
        }
    }

    initConversation(errorData) {
        console.log('[ChatPanel] Initializing conversation with error data:', errorData);

        const contextMsg = `Debugging: **${errorData.last_error}**\nNode: ${errorData.node_context?.node_name || 'Unknown'}`;
        doctorContext.addMessage('system', contextMsg);

        if (errorData.suggestion) {
            doctorContext.addMessage('assistant', errorData.suggestion);
        }

        // Sync context
        doctorContext.setState({ workflowContext: errorData });

        // Auto-trigger analysis when initialized with error context
        const autoAnalysisPrompt = `Analyze this error and provide debugging suggestions:\n\n**Error:** ${errorData.last_error}\n**Node:** ${errorData.node_context?.node_name || 'Unknown'} (${errorData.node_context?.node_class || 'Unknown'})`;

        console.log('[ChatPanel] Auto-triggering analysis...');
        this.handleSend(autoAnalysisPrompt, 'chat');
    }

    async handleSend(textOverride = null, intent = 'chat') {
        const text = textOverride || this.inputElement.value.trim();
        if (!text && intent === 'chat') return;

        if (!textOverride) {
            this.inputElement.value = '';
        }

        // Add user message to Store
        doctorContext.addMessage('user', text, { intent });

        // Start Processing
        doctorContext.setProcessing(true);

        // Create AbortController for this request
        this.abortController = new AbortController();
        // Add placeholder assistant message
        doctorContext.addMessage('assistant', '...'); // Placeholder

        // Remove '...' logic handled by renderer? 
        // Actually better to have a specialized "pending" state.
        // For now, let's treat the last message as the buffer.

        let fullContent = '';

        try {
            // Refresh LLM settings just-in-time to avoid stale API keys/base URLs
            if (typeof doctorContext.refreshSettings === 'function') {
                doctorContext.refreshSettings();
            }

            const state = doctorContext.state;
            const payload = {
                // OpenAI expects history. our store has all.
                // We should filter 'system' or keep it?
                messages: state.messages.filter(m => m.content !== '...'), // Filter placeholder

                error_context: state.workflowContext || {},
                intent: intent,
                selected_nodes: state.selectedNodes,

                api_key: state.settings.apiKey,
                base_url: state.settings.baseUrl,
                model: state.settings.model,
                language: state.settings.language
            };

            // Stream
            await DoctorAPI.streamChat(
                payload,
                (chunk) => {
                    if (chunk.delta) {
                        fullContent += chunk.delta;
                        this.updateLastMessage(fullContent);
                    }
                },
                (error) => {
                    console.error("Stream error:", error);
                    doctorContext.addMessage('system', `Stream Error: ${error.message}`);
                },
                this.abortController.signal
            );

            // Finalize State
            // Update the last message in store with full content
            const msgs = [...doctorContext.state.messages];
            msgs[msgs.length - 1].content = fullContent; // Replace placeholder
            doctorContext.setState({ messages: msgs });

        } catch (e) {
            console.error("Chat error:", e);
            doctorContext.addMessage('system', `Error: ${e.message}`);
        } finally {
            doctorContext.setProcessing(false);
        }
    }

    handleRegenerate() {
        // Find last user message
        const messages = doctorContext.state.messages;
        const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');

        if (!lastUserMsg) {
            console.warn('No user message to regenerate');
            return;
        }

        // Remove last assistant response if exists
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
            const newMessages = messages.slice(0, -1);
            doctorContext.setState({ messages: newMessages });
            // Also remove from DOM
            const lastMsgDiv = this.messagesContainer.lastElementChild;
            if (lastMsgDiv && lastMsgDiv.classList.contains('assistant')) {
                lastMsgDiv.remove();
            }
        }

        // Resend the last user message
        this.handleSend(lastUserMsg.content, lastUserMsg.intent || 'chat');
    }

    handleStop() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
            doctorContext.setProcessing(false);
            doctorContext.addMessage('system', 'Generation stopped by user.');
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    addCopyButtons(container) {
        container.querySelectorAll('pre').forEach((pre) => {
            if (pre.querySelector('.copy-btn')) return;
            if (!pre.querySelector('code')) return;

            const btn = document.createElement('button');
            btn.className = 'copy-btn';
            btn.textContent = '📋';
            btn.title = 'Copy code';

            btn.onclick = () => {
                const code = pre.querySelector('code').innerText;
                navigator.clipboard.writeText(code).then(() => {
                    btn.textContent = '✅';
                    setTimeout(() => btn.textContent = '📋', 2000);
                }).catch(err => {
                    console.error('Failed to copy', err);
                    btn.textContent = '❌';
                });
            };

            pre.style.position = 'relative';
            pre.appendChild(btn);
        });
    }
}
