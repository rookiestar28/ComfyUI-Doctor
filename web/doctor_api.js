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
    }
};
