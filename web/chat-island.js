/**
 * Preact Island Components for ComfyUI-Doctor
 * ============================================
 * Optional Preact-based UI components that enhance the Doctor UI.
 * These "islands" of interactivity are rendered into existing DOM containers.
 *
 * Usage:
 *   import { renderChatIsland, unmountChatIsland } from './components/chat-island.js';
 *   renderChatIsland(containerElement, { errorContext, onSendMessage });
 *
 * @module chat-island
 */

import { loadPreact, isPreactEnabled, getLoadError } from './preact-loader.js';

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let preactModules = null;
let islandMounted = false;
let currentContainer = null;

// ═══════════════════════════════════════════════════════════════════════════
// FALLBACK UI
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Render fallback UI when Preact fails to load.
 * This ensures the user always sees SOMETHING, even if Preact is broken.
 */
function renderFallbackUI(container, error) {
    console.warn('[ChatIsland] Rendering fallback UI due to Preact load failure:', error?.message);

    container.innerHTML = `
        <div style="padding: 20px; background: rgba(255, 68, 68, 0.1); border: 1px solid #f44; border-radius: 8px; color: #eee;">
            <h4 style="margin: 0 0 10px 0; color: #ff6b6b;">⚠️ Enhanced UI Unavailable</h4>
            <p style="margin: 0 0 10px 0; font-size: 13px; color: #aaa;">
                Preact components failed to load. The basic UI is still functional.
            </p>
            <details style="font-size: 12px; color: #888;">
                <summary style="cursor: pointer;">Technical Details</summary>
                <pre style="margin: 8px 0 0 0; padding: 8px; background: #222; border-radius: 4px; overflow-x: auto; white-space: pre-wrap;">${error?.message || 'Unknown error'}</pre>
                <p style="margin: 8px 0 0 0;">
                    To retry: Refresh the page or run <code style="background: #333; padding: 2px 4px; border-radius: 2px;">localStorage.removeItem('doctor_preact_disabled')</code>
                </p>
            </details>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════════════════
// CHAT ISLAND COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Chat Island Component (Preact)
 * Renders a chat interface for AI-assisted debugging.
 */
function ChatIsland({ errorContext, onSendMessage, onClear, uiText }) {
    const { html, useState, useCallback } = preactModules;
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSend = useCallback(() => {
        if (!inputValue.trim() || isLoading) return;

        const userMessage = { role: 'user', content: inputValue };
        setMessages(prev => [...prev, userMessage]);
        setInputValue('');
        setIsLoading(true);

        if (onSendMessage) {
            onSendMessage(inputValue, (response) => {
                setMessages(prev => [...prev, { role: 'assistant', content: response }]);
                setIsLoading(false);
            });
        }
    }, [inputValue, isLoading, onSendMessage]);

    const handleClear = useCallback(() => {
        setMessages([]);
        if (onClear) onClear();
    }, [onClear]);

    return html`
        <div class="chat-island">
            <div class="chat-messages" style="flex: 1; overflow-y: auto; padding: 10px;">
                ${messages.length === 0 && html`
                    <div style="text-align: center; padding: 40px 20px; color: #888;">
                        <div style="font-size: 48px; margin-bottom: 10px;">🤖</div>
                        <div>${uiText?.noMessages || 'Ask AI about this error...'}</div>
                    </div>
                `}
                ${messages.map((msg, idx) => html`
                    <div key=${idx} class="chat-message ${msg.role}" style="
                        background: ${msg.role === 'user' ? '#2b5c92' : '#333'};
                        color: ${msg.role === 'user' ? 'white' : '#eee'};
                        padding: 8px 12px;
                        border-radius: 8px;
                        margin-bottom: 10px;
                        max-width: ${msg.role === 'user' ? '80%' : '90%'};
                        align-self: ${msg.role === 'user' ? 'flex-end' : 'flex-start'};
                    ">
                        ${msg.content}
                    </div>
                `)}
                ${isLoading && html`
                    <div class="chat-loading" style="color: #888; font-style: italic; padding: 8px;">
                        ${uiText?.thinking || 'Thinking...'}
                    </div>
                `}
            </div>
            <div class="chat-input-area" style="border-top: 1px solid #444; padding: 10px; display: flex; gap: 8px;">
                <input 
                    type="text"
                    value=${inputValue}
                    onInput=${(e) => setInputValue(e.target.value)}
                    onKeyDown=${(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    placeholder=${uiText?.placeholder || 'Ask AI about this error...'}
                    style="flex: 1; padding: 8px; background: #111; border: 1px solid #444; border-radius: 4px; color: #eee;"
                    disabled=${isLoading}
                />
                <button 
                    onClick=${handleSend}
                    disabled=${isLoading || !inputValue.trim()}
                    style="padding: 8px 16px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer;"
                >
                    ${uiText?.send || 'Send'}
                </button>
                <button 
                    onClick=${handleClear}
                    style="padding: 8px 12px; background: #333; color: #eee; border: 1px solid #444; border-radius: 4px; cursor: pointer;"
                >
                    ${uiText?.clear || 'Clear'}
                </button>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Render the Chat Island into a container element.
 * @param {HTMLElement} container - The DOM element to render into
 * @param {Object} props - Component props (errorContext, onSendMessage, onClear, uiText)
 * @returns {Promise<boolean>} True if successfully rendered, false if fallback was used
 */
export async function renderChatIsland(container, props = {}) {
    if (!container) {
        console.error('[ChatIsland] No container provided');
        return false;
    }

    currentContainer = container;

    // Check if Preact is disabled
    if (!isPreactEnabled()) {
        renderFallbackUI(container, new Error('Preact islands are disabled'));
        return false;
    }

    try {
        // Load Preact modules
        preactModules = await loadPreact();
        const { render, html } = preactModules;

        // Render the Chat Island
        render(
            html`<${ChatIsland} ...${props} />`,
            container
        );

        islandMounted = true;
        console.log('[ChatIsland] ✅ Rendered successfully');
        return true;
    } catch (error) {
        console.error('[ChatIsland] ❌ Failed to render:', error);
        renderFallbackUI(container, error);
        return false;
    }
}

/**
 * Unmount the Chat Island from its container.
 */
export function unmountChatIsland() {
    if (!islandMounted || !currentContainer || !preactModules) {
        return;
    }

    try {
        preactModules.render(null, currentContainer);
        islandMounted = false;
        currentContainer = null;
        console.log('[ChatIsland] Unmounted');
    } catch (error) {
        console.warn('[ChatIsland] Unmount error:', error);
    }
}

/**
 * Check if the Chat Island is currently mounted.
 * @returns {boolean}
 */
export function isChatIslandMounted() {
    return islandMounted;
}
