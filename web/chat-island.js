/**
 * Preact component for ComfyUI-Doctor Chat Interface.
 * Implements full chat functionality including streaming, markdown, code highlighting, and fix suggestions.
 * Replace doctor_chat.js functionality.
 */

import { app } from "../../../scripts/app.js";
import { loadPreact, isPreactEnabled } from './preact-loader.js';
import { DoctorAPI } from './doctor_api.js';
import { FixHandler } from './doctor_fix_handler.js';
// 5C.2: Use read-only selectors
import {
    getMessages, getWorkflowContext, getSettings, getIsProcessing, getSanitizationMetadata,
    onMessagesChanged, onStateChanged
} from './doctor_selectors.js';
// 5C.2: Use actions for state mutations (separate from selectors)
import {
    refreshSettings, addMessage, clearMessages, setProcessing, setState
} from './doctor_actions.js';
// 5C.3: Use shared rendering utilities
import {
    loadRenderingAssets, sanitizeHtml, highlightCodeBlocks, addCopyButtons
} from './doctor_rendering.js';

// Shared State
let preactModules = null;
let islandMounted = false;
let currentContainer = null;
let fixHandler = null;

// 5C.3: Local loadAssets, loadScript, sanitizeHtml removed - using shared doctor_rendering.js

// =========================================================
// COMPONENTS
// =========================================================

function summarizeError(lastError) {
    if (!lastError) return '';
    const lines = lastError.trim().split('\n');

    for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (/^[A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Interrupt):/.test(line)) {
            return line;
        }
    }

    for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (line && !line.startsWith('Prompt executed') && !line.startsWith('+-')) {
            return line;
        }
    }

    return lines[lines.length - 1]?.trim() || '';
}

function SanitizationStatus({ metadata, uiText }) {
    const { html } = preactModules;

    // Always render container for E2E compatibility
    const style = {
        flexShrink: 0,
        background: 'rgba(158, 158, 158, 0.1)',
        borderBottom: '1px solid var(--border-color, #444)',
        padding: '6px 10px',
        fontSize: '11px',
        color: '#888',
        display: metadata ? 'block' : 'none'
    };

    if (!metadata) {
        return html`<div id="doctor-sanitization-status" style=${style}></div>`;
    }

    const privacyMode = metadata.privacy_mode || 'basic';
    const piiFound = metadata.pii_found === true;

    // UI Text Fallbacks
    const privacyLabel = uiText?.sanitization_label || 'Privacy';
    const modeLabel = uiText?.[`sanitization_${privacyMode}`] || privacyMode;
    const piiLabel = piiFound
        ? (uiText?.sanitization_pii_found || 'PII removed')
        : (uiText?.sanitization_pii_not_found || 'No PII');

    const modeIcon = privacyMode === 'strict' ? '🔒' : (privacyMode === 'basic' ? '🔐' : '🔓');
    const piiIcon = piiFound ? '✓' : '';

    // Styling based on mode
    let bg = 'rgba(158, 158, 158, 0.1)';
    if (privacyMode === 'strict') bg = 'rgba(76, 175, 80, 0.15)';
    else if (privacyMode === 'basic') bg = 'rgba(255, 193, 7, 0.1)';

    return html`
        <div id="doctor-sanitization-status" class="sanitization-status" style=${{ ...style, background: bg }}>
            <span style="margin-right: 12px;">${modeIcon} ${privacyLabel}: <strong>${modeLabel}</strong></span>
            <span style="color: ${piiFound ? '#4caf50' : '#888'};">${piiIcon} ${piiLabel}</span>
        </div>
    `;
}

function ErrorContextCard({ workflowContext, onAnalyze }) {
    const { html } = preactModules;

    // Always render container for E2E compatibility
    const style = {
        padding: '10px',
        borderBottom: '1px solid #444',
        background: '#1e1e1e',
        display: (workflowContext && workflowContext.last_error) ? 'block' : 'none'
    };

    if (!workflowContext || !workflowContext.last_error) {
        return html`<div id="doctor-error-context" style=${style}></div>`;
    }

    const errorSummary = workflowContext.error_summary || summarizeError(workflowContext.last_error);

    return html`
        <div id="doctor-error-context" class="error-context-card" style=${style}>
            <div style="font-weight: bold; color: #f44; margin-bottom: 5px;">
                ${workflowContext.node_context?.node_name || 'Node Error'}
            </div>
            <div style="font-size: 12px; color: #ccc; max-height: 60px; overflow: hidden; text-overflow: ellipsis;">
                ${errorSummary}
            </div>
             <button onClick=${onAnalyze} style="
                width: 100%;
                margin-top: 8px;
                padding: 6px;
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            ">
                🤖 Analyze with AI
            </button>
        </div>
    `;
}

function MessageItem({ msg, uiText }) {
    const { html, useEffect, useRef } = preactModules;
    const contentRef = useRef(null);

    useEffect(() => {
        if (!contentRef.current || !window.marked) return;

        // Match vanilla behavior: allow fix buttons to appear in chat content.
        if (!fixHandler && app) {
            fixHandler = new FixHandler(app);
        }

        // Markdown Render
        const rawHtml = window.marked.parse(msg.content || '');
        // Avoid raw HTML injection from markdown.
        contentRef.current.innerHTML = sanitizeHtml(rawHtml);

        // 5C.3: Use shared highlight/copy utilities
        highlightCodeBlocks(contentRef.current);
        addCopyButtons(contentRef.current);

        if (fixHandler) {
            const fixData = fixHandler.detectFixes(msg.content || '');
            if (fixData) {
                fixHandler.renderFixButtons(contentRef.current, fixData, uiText);
            }
        }

    }, [msg.content]);

    return html`
        <div class="doctor-chat-message ${msg.role}" ref=${contentRef} style="
            padding: 8px 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            max-width: 90%;
            align-self: ${msg.role === 'user' ? 'flex-end' : 'flex-start'};
            background: ${msg.role === 'user' ? '#2b5c92' : '#333'};
            color: ${msg.role === 'user' ? 'white' : '#eee'};
            word-wrap: break-word;
        ">
            <!-- Content injected via ref -->
        </div>
    `;
}

function ChatIsland({ uiText }) {
    const { html, useState, useEffect, useRef, useCallback } = preactModules;

    // State
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [workflowContext, setWorkflowContext] = useState(null);
    const [sanitizationMetadata, setSanitizationMetadata] = useState(null);

    const messagesEndRef = useRef(null);
    const abortControllerRef = useRef(null);
    const textareaRef = useRef(null);

    // 5C.2: Subscribe via selectors instead of direct doctorContext access
    useEffect(() => {
        // Initial load via selectors
        setMessages(getMessages());
        setWorkflowContext(getWorkflowContext());
        setSanitizationMetadata(getSanitizationMetadata());

        // Listeners via selectors
        const msgUnsub = onMessagesChanged((msgs) => {
            setMessages([...msgs]);
        });

        const stateUnsub = onStateChanged((current) => {
            setIsProcessing(current.isProcessing || false);
            setMessages(current.messages || []);
            if (current.workflowContext !== workflowContext) {
                setWorkflowContext(current.workflowContext);
                setSanitizationMetadata(current.workflowContext?.analysis_metadata?.sanitization);
            }
        });

        return () => {
            msgUnsub();
            stateUnsub();
        };
    }, []);

    // Auto-scroll
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, messages.length]);

    // 5C.3: Load rendering assets via shared module
    useEffect(() => {
        loadRenderingAssets();
    }, []);

    // 5B.3: Cleanup on unmount - abort active streams
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
                abortControllerRef.current = null;
            }
        };
    }, []);

    const scrollToBottom = () => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    };

    const runChat = useCallback(async (text) => {
        if (!text || isProcessing) return;

        // 5C.2: Refresh settings via selector
        refreshSettings();
        const privacyMode = app?.ui?.settings?.getSettingValue?.("Doctor.Privacy.Mode", "basic") || "basic";

        // 1. Add User Message via selector
        addMessage('user', text);
        setProcessing(true);

        // 2. Add System Placeholder for Assistant
        addMessage('assistant', '...');

        // 3. Prepare Payload via selectors
        abortControllerRef.current = new AbortController();

        const msgs = getMessages();
        const wfCtx = getWorkflowContext();
        const settings = getSettings();
        const payload = {
            messages: msgs.filter(m => m.content !== '...'),
            error_context: wfCtx || {},
            intent: 'chat',
            selected_nodes: [],
            api_key: settings.apiKey,
            base_url: settings.baseUrl,
            model: settings.model,
            language: settings.language,
            privacy_mode: privacyMode
        };

        let fullContent = '';

        try {
            await DoctorAPI.streamChat(
                payload,
                (chunk) => {
                    if (chunk.delta) {
                        fullContent += chunk.delta;
                        const currentMsgs = [...getMessages()];
                        if (currentMsgs.length > 0) {
                            currentMsgs[currentMsgs.length - 1].content = fullContent;
                            setState({ messages: currentMsgs });
                        }
                    }
                },
                (err) => console.error("Stream error", err),
                abortControllerRef.current.signal
            );
        } catch (e) {
            if (e.name !== 'AbortError') {
                addMessage('system', `Error: ${e.message}`);
            }
        } finally {
            setProcessing(false);
            abortControllerRef.current = null;
        }
    }, [isProcessing]);

    const handleSend = useCallback(async () => {
        if (!inputValue.trim() || isProcessing) return;

        const text = inputValue.trim();
        setInputValue('');

        if (textareaRef.current) textareaRef.current.style.height = 'auto';

        await runChat(text);
    }, [inputValue, isProcessing, runChat]);

    const handleClear = useCallback(() => {
        if (confirm(uiText?.confirm_clear || 'Clear history?')) {
            // 5C.2: Use selector action
            clearMessages();
        }
    }, [uiText]);

    const handleAnalyze = useCallback(() => {
        if (!workflowContext?.last_error) return;
        const nodeName = workflowContext.node_context?.node_name || 'Unknown';
        const nodeClass = workflowContext.node_context?.node_class || 'Unknown';
        const prompt = `Analyze this error and provide debugging suggestions:\n\n**Error:** ${workflowContext.last_error}\n**Node:** ${nodeName} (${nodeClass})`;
        runChat(prompt);
    }, [workflowContext, runChat]);

    const handleInput = (e) => {
        setInputValue(e.target.value);
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    };

    return html`
        <div class="chat-island" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
            
            <${SanitizationStatus} metadata=${sanitizationMetadata} uiText=${uiText} />
            <${ErrorContextCard} workflowContext=${workflowContext} onAnalyze=${handleAnalyze} />

            <div id="doctor-messages" class="chat-messages" style="
                flex: 1 1 0; 
                overflow-y: auto; 
                padding: 10px; 
                min-height: 0;
            ">
                ${messages.length === 0 && html`
                    <div style="text-align: center; padding: 40px 20px; color: #888;">
                        <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
                        <div>${uiText?.no_errors_detected || 'System Healthy'}</div>
                    </div>
                `}
                
                ${messages.map((msg, i) => html`
                    <${MessageItem} key=${i} msg=${msg} uiText=${uiText} />
                `)}
                <div ref=${messagesEndRef}></div>
            </div>

            <div class="chat-input-area" style="
                border-top: 1px solid #444; 
                padding: 10px; 
                background: var(--bg-color, #252525);
                flex-shrink: 0;
            ">
                <div style="display: flex; gap: 8px; flex-direction: column;">
                    <textarea 
                        id="doctor-input"
                        ref=${textareaRef}
                        value=${inputValue}
                        onInput=${handleInput}
                        onKeyDown=${(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
                        placeholder=${uiText?.ask_ai_placeholder || 'Ask AI...'}
                        rows="1"
                        style="
                            width: 100%; 
                            min-height: 40px; 
                            max-height: 120px;
                            background: #111; 
                            border: 1px solid #444; 
                            border-radius: 4px; 
                            color: #eee; 
                            padding: 8px; 
                            resize: none;
                        "
                        disabled=${isProcessing}
                    ></textarea>
                    
                    <div style="display: flex; gap: 8px;">
                        <button 
                            id="doctor-send-btn"
                            onClick=${handleSend} 
                            disabled=${isProcessing || !inputValue.trim()}
                            style="
                                flex: 2; 
                                padding: 8px; 
                                background: ${isProcessing ? '#666' : '#4caf50'}; 
                                color: white; 
                                border: none; 
                                border-radius: 4px; 
                                cursor: pointer;
                                font-weight: bold;
                            "
                        >
                            ${isProcessing ? 'Thinking...' : (uiText?.send_btn || 'Send')}
                        </button>
                        <button 
                            id="doctor-clear-btn"
                            onClick=${handleClear}
                            style="
                                flex: 1; 
                                padding: 8px; 
                                background: #666; 
                                color: white; 
                                border: none; 
                                border-radius: 4px; 
                                cursor: pointer;
                            "
                        >
                            ${uiText?.clear_btn || 'Clear'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// =========================================================
// EXPORTS
// =========================================================

export async function renderChatIsland(container, props = {}, options = {}) {
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
        render(html`<${ChatIsland} ...${props} />`, container);
        islandMounted = true;
        return true;
    } catch (e) {
        console.error("ChatIsland render failed:", e);
        return false;
    }
}

export function unmountChatIsland() {
    if (islandMounted && currentContainer && preactModules) {
        preactModules.render(null, currentContainer);
        islandMounted = false;
        currentContainer = null;
    }
}
