/**
 * Preact component for ComfyUI-Doctor Chat Interface.
 * Implements full chat functionality including streaming, markdown, code highlighting, and fix suggestions.
 * Replace doctor_chat.js functionality.
 */

import { app } from "../../../scripts/app.js";
import { getDoctorSetting } from "./comfyui_frontend_compat.js";
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
import {
    applyProviderQuickSwitch,
    getProviderQuickSwitchState,
} from './llm_provider_quick_switch.js';
// R5: Error Boundaries
import { createErrorBoundaryAsync } from './ErrorBoundary.js';
import { isDoctorErrorBoundariesEnabled } from './comfyui_frontend_compat.js';
import { describeLlmError } from './utils/llm_error_text.js';
import { t } from './utils/i18n_fallback.js';

// Shared State
let preactModules = null;
let fixHandler = null;

const PENDING_REPLY = '...';

// IMPORTANT: the chat route forwards history roles verbatim to the provider. Island-only bubbles
// (error/system notices) and the pending placeholder must never be sent back as conversation history.
function buildChatHistory(messages, pendingId) {
    return messages
        .filter((m) => m.id !== pendingId && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
        .map((m) => ({ role: m.role, content: m.content }));
}

function updateMessage(id, patch) {
    const messages = getMessages();
    if (!messages.some((m) => m.id === id)) return;
    setState({ messages: messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) });
}

/**
 * Final notice for a finished chat request, or null when the streamed reply stands as is.
 * `DoctorAPI.streamChat` reports failures through its callback and never rethrows, so the outcome
 * is decided here from the abort signal, the reported failure and the streamed content.
 */
function describeChatOutcome({ aborted, stoppedByUser, failure, content }, uiText) {
    if (aborted) {
        return stoppedByUser
            ? { role: 'system', content: t(uiText, 'generation_stopped_user', 'Generation stopped by user.') }
            : null;
    }
    const streamError = t(uiText, 'stream_error', 'Stream Error');
    let detail = '';
    if (failure) {
        const message = typeof failure?.message === 'string' ? failure.message : String(failure);
        detail = describeLlmError(message, uiText) || streamError;
    } else if (!content) {
        detail = streamError;
    }
    return detail ? { role: 'error', content: `${t(uiText, 'chat_error', 'Chat error')}: ${detail}` } : null;
}

function finishPendingReply(id, content, outcome) {
    const messages = getMessages();
    if (!messages.some((m) => m.id === id)) return; // history was cleared meanwhile
    if (content) {
        if (outcome) addMessage(outcome.role, outcome.content);
        return;
    }
    setState({
        messages: outcome
            ? messages.map((m) => (m.id === id ? { ...m, role: outcome.role, content: outcome.content } : m))
            : messages.filter((m) => m.id !== id),
    });
}

// 5C.3: Local loadAssets, loadScript, sanitizeHtml removed - using shared doctor_rendering.js

// =========================================================
// R5: ERROR BOUNDARIES FEATURE FLAG
// =========================================================

/**
 * Check if Error Boundaries feature is enabled.
 * Must match the check in doctor.js.
 */
function isErrorBoundariesEnabled() {
    return isDoctorErrorBoundariesEnabled(window.app);
}

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

function buildAutoAnalysisPrompt(workflowContext, uiText) {
    const nodeName = workflowContext?.node_context?.node_name || 'Unknown';
    const nodeClass = workflowContext?.node_context?.node_class || 'Unknown';
    const nodeLabel = `${nodeName} (${nodeClass})`;
    const errorSummary = workflowContext?.error_summary || summarizeError(workflowContext?.last_error);

    const template = uiText?.analyze_prompt_label
        || 'Analyze this error and provide debugging suggestions:\n\n**Error:** {0}\n**Node:** {1}';

    // R14: Avoid sending the entire traceback as a user message.
    // The backend already receives full `error_context` and builds a system prompt (PromptComposer).
    return template
        .replace('{0}', errorSummary || 'Unknown Error')
        .replace('{1}', nodeLabel);
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

    const errorSummary = workflowContext.execution_context?.validation_display_summary
        || workflowContext.error_summary
        || summarizeError(workflowContext.last_error);

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

function ProviderQuickSwitch({ state, uiText, disabled, onSwitch }) {
    const { html } = preactModules;
    const providerLabel = uiText?.ai_provider_label || 'AI Provider';
    const baseUrlLabel = state?.baseUrl || '';

    return html`
        <div class="doctor-provider-quick-switch" style="
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 8px 10px;
            border-bottom: 1px solid var(--border-color, #444);
            background: rgba(255, 255, 255, 0.02);
        ">
            <label for="doctor-provider-quick-switch" style="font-size: 11px; color: #aaa;">
                ${providerLabel}
            </label>
            <select
                id="doctor-provider-quick-switch"
                aria-label="AI provider quick switch"
                value=${state?.provider || 'openai'}
                onChange=${(event) => onSwitch(event.currentTarget.value)}
                disabled=${disabled}
                style="
                    width: 100%;
                    padding: 6px 8px;
                    background: #111;
                    border: 1px solid #444;
                    border-radius: 4px;
                    color: #eee;
                    font-size: 12px;
                "
            >
                ${(state?.options || []).map((provider) => html`
                    <option value=${provider.value}>${provider.label}</option>
                `)}
            </select>
            <div id="doctor-provider-quick-status" style="font-size: 10px; color: #777; overflow-wrap: anywhere;">
                ${baseUrlLabel}
            </div>
        </div>
    `;
}

function MessageItem({ msg, uiText }) {
    const { html, useEffect, useRef } = preactModules;
    const contentRef = useRef(null);

    useEffect(() => {
        if (!contentRef.current) return;

        // CRITICAL: error/system bubbles carry server, provider or island status text. Render them as
        // text only (no markdown, no fix detection): failure strings must never become markup.
        if (msg.role === 'error' || msg.role === 'system') {
            contentRef.current.textContent = msg.content || '';
            return;
        }
        if (!window.marked) return;

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

        // IMPORTANT: only assistant replies may offer fix buttons; user/system/error text can carry
        // pasted or reflected fix blocks. Content was replaced above, so buttons never accumulate.
        if (fixHandler && msg.role === 'assistant') {
            const fixData = fixHandler.detectFixes(msg.content || '');
            if (fixData) {
                fixHandler.renderFixButtons(contentRef.current, fixData, uiText);
            }
        }

    }, [msg.content, msg.role]);

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

    // ⚠️ R5: E2E test injection point (production-safe double-guard)
    const isTestHarness = window.location.pathname.includes('test-harness.html') ||
        typeof window.__testMocks !== 'undefined';
    if (isTestHarness &&
        typeof window.__testErrorInjection !== 'undefined' &&
        window.__testErrorInjection.enabled &&
        window.__testErrorInjection.throwIn === 'chat') {

        // Support custom error message for PII sanitization testing
        const errorMsg = window.__testErrorInjection.customMessage ||
            (window.__testErrorInjection.mode === 'always'
                ? 'E2E Test: Permanent chat crash'
                : 'E2E Test: One-time chat crash');

        if (window.__testErrorInjection.mode === 'always') {
            throw new Error(errorMsg);
        } else if (window.__testErrorInjection.mode === 'once') {
            window.__testErrorInjection.mode = 'off'; // One-time
            throw new Error(errorMsg);
        }
    }

    // State
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [workflowContext, setWorkflowContext] = useState(null);
    const [sanitizationMetadata, setSanitizationMetadata] = useState(null);
    const [providerSwitchState, setProviderSwitchState] = useState(getProviderQuickSwitchState());

    const messagesEndRef = useRef(null);
    const abortControllerRef = useRef(null);
    const stopRequestedRef = useRef(false);
    const textareaRef = useRef(null);

    // 5C.2: Subscribe via selectors instead of direct doctorContext access
    useEffect(() => {
        // Initial load via selectors
        setMessages(getMessages());
        setWorkflowContext(getWorkflowContext());
        setSanitizationMetadata(getSanitizationMetadata());
        setProviderSwitchState(getProviderQuickSwitchState());

        // Listeners via selectors
        const msgUnsub = onMessagesChanged((msgs) => {
            setMessages([...msgs]);
        });

        const stateUnsub = onStateChanged((current) => {
            setIsProcessing(current.isProcessing || false);
            setMessages(current.messages || []);
            setProviderSwitchState(getProviderQuickSwitchState());
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
        const privacyMode = getDoctorSetting("Doctor.Privacy.Mode", "basic", app) || "basic";

        // 1. Add User Message via selector
        addMessage('user', text);
        setProcessing(true);

        // 2. Add the pending assistant reply (settled by id once the request finishes)
        const pending = addMessage('assistant', PENDING_REPLY);

        // 3. Prepare Payload via selectors
        const controller = new AbortController();
        abortControllerRef.current = controller;
        stopRequestedRef.current = false;

        const wfCtx = getWorkflowContext();
        const settings = getSettings();
        const payload = {
            messages: buildChatHistory(getMessages(), pending.id),
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
        let failure = null;

        try {
            await DoctorAPI.streamChat(
                payload,
                (chunk) => {
                    if (chunk.delta) {
                        fullContent += chunk.delta;
                        updateMessage(pending.id, { content: fullContent });
                    }
                },
                (err) => {
                    console.error("Stream error", err);
                    failure = err;
                },
                controller.signal
            );
        } catch (e) {
            failure = e;
        } finally {
            // IMPORTANT: every outcome must settle the pending reply here; streamChat never rethrows,
            // so a console-only error callback left a permanent '...' bubble.
            const outcome = describeChatOutcome({
                aborted: controller.signal.aborted,
                stoppedByUser: stopRequestedRef.current,
                failure,
                content: fullContent,
            }, uiText);
            finishPendingReply(pending.id, fullContent, outcome);
            setProcessing(false);
            if (abortControllerRef.current === controller) abortControllerRef.current = null;
        }
    }, [isProcessing, uiText]);

    const handleStop = useCallback(() => {
        if (!abortControllerRef.current) return;
        stopRequestedRef.current = true;
        abortControllerRef.current.abort();
    }, []);

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

    const handleProviderSwitch = useCallback((provider) => {
        applyProviderQuickSwitch(provider);
        setProviderSwitchState(getProviderQuickSwitchState());
    }, []);

    const handleAnalyze = useCallback(() => {
        if (!workflowContext?.last_error) return;
        const prompt = buildAutoAnalysisPrompt(workflowContext, uiText);
        runChat(prompt);
    }, [workflowContext, uiText, runChat]);

    const handleInput = (e) => {
        setInputValue(e.target.value);
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    };

    return html`
        <div class="chat-island" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
            
            <${ProviderQuickSwitch}
                state=${providerSwitchState}
                uiText=${uiText}
                disabled=${isProcessing}
                onSwitch=${handleProviderSwitch}
            />
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
                        ${isProcessing && html`
                            <button
                                id="doctor-stop-btn"
                                onClick=${handleStop}
                                style="
                                    flex: 1;
                                    padding: 8px;
                                    background: #b23b3b;
                                    color: white;
                                    border: none;
                                    border-radius: 4px;
                                    cursor: pointer;
                                "
                            >
                                ${uiText?.stop_btn || 'Stop'}
                            </button>
                        `}
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
                    islandId="chat"
                    uiText=${props.uiText || {}}
                >
                    <${ChatIsland} ...${props} />
                </${ErrorBoundary}>
            `, container);
        } else {
            // Render without ErrorBoundary (fallback to island_registry try-catch)
            render(html`<${ChatIsland} ...${props} />`, container);
        }

        return true;
    } catch (e) {
        console.error("ChatIsland render failed:", e);
        return false;
    }
}

export function activateChatIsland(container) {
    if (!container || container.isConnected === false) return false;

    const messages = container.querySelector('.chat-island .chat-messages');
    if (!messages) return false;

    messages.scrollTop = messages.scrollHeight;
    return true;
}

export function unmountChatIsland(container) {
    if (!container || !preactModules) return false;

    preactModules.render(null, container);
    return true;
}
