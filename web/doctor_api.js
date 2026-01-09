/**
 * API Wrapper for ComfyUI-Doctor
 */
export const DoctorAPI = {
    /**
     * Get the last analysis result
     */
    async getLastAnalysis() {
        try {
            const response = await fetch('/debugger/last_analysis');
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to fetch analysis:', error);
            return null;
        }
    },

    /**
     * Get error history
     */
    async getHistory() {
        try {
            const response = await fetch('/debugger/history');
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to fetch history:', error);
            return null;
        }
    },

    /**
     * Set display language
     * @param {string} language - 'en', 'zh_TW', 'zh_CN', 'ja'
     */
    async setLanguage(language) {
        try {
            const response = await fetch('/debugger/set_language', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language })
            });
            // The original code had a check for response.ok, but the provided snippet removed it.
            // Keeping the behavior from the provided snippet.
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to set language:', error);
            // The original code returned null, but the provided snippet returns { success: false }.
            // Keeping the behavior from the provided snippet.
            return { success: false };
        }
    },

    async analyzeError(payload) {
        try {
            const response = await fetch('/doctor/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Analysis failed:', error);
            throw error;
        }
    },

    /**
     * Verify API key validity
     * @param {string} baseUrl - LLM API base URL
     * @param {string} apiKey - API key to verify
     * @returns {Promise<{success: boolean, message: string, is_local: boolean}>}
     */
    async verifyApiKey(baseUrl, apiKey) {
        try {
            const response = await fetch('/doctor/verify_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ base_url: baseUrl, api_key: apiKey })
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Key verification failed:', error);
            return { success: false, message: error.message, is_local: false };
        }
    },

    /**
     * List available LLM models
     * @param {string} baseUrl - LLM API base URL
     * @param {string} apiKey - API key
     * @returns {Promise<{success: boolean, models: Array<{id: string, name: string}>, message: string}>}
     */
    async listModels(baseUrl, apiKey) {
        try {
            const response = await fetch('/doctor/list_models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ base_url: baseUrl, api_key: apiKey })
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to list models:', error);
            return { success: false, models: [], message: error.message };
        }
    },

    /**
     * Stream chat with LLM (SSE)
     * @param {Object} payload - Chat payload
     * @param {Array<{role: string, content: string}>} payload.messages - Conversation history
     * @param {Object} payload.error_context - Error context {error, node_context, workflow}
     * @param {string} payload.api_key - LLM API key
     * @param {string} payload.base_url - LLM API base URL
     * @param {string} payload.model - Model name
     * @param {string} payload.language - Response language
     * @param {Function} onChunk - Callback for each chunk {delta: string, done: boolean}
     * @param {Function} onError - Callback for errors
     * @param {AbortSignal} signal - Optional AbortSignal for cancellation
     * @returns {Promise<void>}
     */
    async streamChat(payload, onChunk, onError, signal = null) {
        try {
            const response = await fetch('/doctor/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, stream: true }),
                signal
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
                throw new Error(err.error || `HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || !trimmed.startsWith('data:')) continue;

                    const jsonStr = trimmed.slice(5).trim();
                    if (!jsonStr) continue;

                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.error) {
                            onError?.(new Error(data.error));
                            return;
                        }
                        onChunk?.(data);
                        if (data.done) return;
                    } catch (parseErr) {
                        console.warn('[ComfyUI-Doctor] Failed to parse SSE chunk:', jsonStr);
                    }
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[ComfyUI-Doctor] Chat stream aborted');
                return;
            }
            console.error('[ComfyUI-Doctor] Stream chat failed:', error);
            onError?.(error);
        }
    },

    /**
     * Non-streaming chat with LLM (fallback)
     * @param {Object} payload - Same as streamChat
     * @returns {Promise<{content: string, done: boolean}>}
     */
    async chat(payload) {
        try {
            const response = await fetch('/doctor/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, stream: false })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
                throw new Error(err.error || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Chat failed:', error);
            throw error;
        }
    },

    /**
     * F4: Get error statistics for dashboard
     * @param {number} timeRangeDays - Number of days to include (default: 30)
     * @returns {Promise<{success: boolean, statistics: Object}>}
     */
    async getStatistics(timeRangeDays = 30) {
        try {
            const response = await fetch(`/doctor/statistics?time_range_days=${timeRangeDays}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
                throw new Error(err.error || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to fetch statistics:', error);
            return {
                success: false,
                error: error.message,
                statistics: {
                    total_errors: 0,
                    pattern_frequency: {},
                    category_breakdown: {},
                    top_patterns: [],
                    resolution_rate: { resolved: 0, unresolved: 0, ignored: 0 },
                    trend: { last_24h: 0, last_7d: 0, last_30d: 0 }
                }
            };
        }
    },

    /**
     * Get internal health metrics
     * @returns {Promise<{success: boolean, health?: any, error?: string}>}
     */
    async getHealth() {
        try {
            const response = await fetch('/doctor/health');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to fetch health:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * Get plugin trust report (scan-only)
     * @returns {Promise<{success: boolean, plugins?: any, error?: string}>}
     */
    async getPluginsReport() {
        try {
            const response = await fetch('/doctor/plugins');
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to fetch plugin report:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * F4: Mark an error as resolved/unresolved/ignored
     * @param {string} timestamp - Error timestamp
     * @param {string} status - Status: 'resolved', 'unresolved', or 'ignored'
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async markResolved(timestamp, status = 'resolved') {
        try {
            const response = await fetch('/doctor/mark_resolved', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timestamp, status })
            });
            return await response.json();
        } catch (error) {
            console.error('[ComfyUI-Doctor] Failed to mark error:', error);
            return { success: false, message: error.message };
        }
    }
};
