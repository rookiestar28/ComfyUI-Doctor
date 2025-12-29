
import { app } from "../../../scripts/app.js";

/**
 * Global State Management for Doctor Chat
 * Implements a Pub/Sub pattern to manage chat state, settings, and context.
 */
class DoctorContext {
    constructor() {
        this.listeners = new Map();

        // Initial State
        this.state = {
            messages: [],
            sessionId: this.generateUUID(),
            selectedNodes: [], // Currently selected nodes in canvas
            workflowContext: null, // Metadata about current workflow
            isProcessing: false,
            settings: {
                apiKey: "",
                baseUrl: "",
                model: "",
                provider: "openai",
                language: "en"
            }
        };

        this.initSettings();
    }

    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // --- Event Bus ---

    subscribe(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        // Return unsubscribe function
        return () => {
            const set = this.listeners.get(event);
            if (set) {
                set.delete(callback);
            }
        };
    }

    publish(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(cb => cb(data));
        }
    }

    // --- State Actions ---

    setState(updates) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };

        // Publish generic state change
        this.publish('stateChanged', { prev: oldState, current: this.state });

        // Publish specific changes
        Object.keys(updates).forEach(key => {
            if (oldState[key] !== this.state[key]) {
                this.publish(`change:${key}`, this.state[key]);
            }
        });
    }

    addMessage(role, content, metadata = {}) {
        const newMsg = {
            id: this.generateUUID(),
            role,
            content,
            timestamp: Date.now(),
            ...metadata
        };

        const messages = [...this.state.messages, newMsg];
        this.setState({ messages });
        this.publish('messageAdded', newMsg);

        return newMsg;
    }

    clearMessages() {
        this.setState({ messages: [] });
    }

    setProcessing(isProcessing) {
        this.setState({ isProcessing });
    }

    // --- Context Actions ---

    setSelectedNodes(nodes) {
        // checks if significantly changed
        const currentIds = this.state.selectedNodes.map(n => n.id).sort().join(',');
        const newIds = nodes.map(n => n.id).sort().join(',');

        if (currentIds !== newIds) {
            this.setState({ selectedNodes: nodes });
        }
    }

    // --- Settings Management ---

    initSettings() {
        // We defer this slightly to ensure app.ui.settings is ready if loaded early
        setTimeout(() => {
            this.refreshSettings();
        }, 100);
    }

    refreshSettings() {
        if (!app?.ui?.settings) return;

        const s = app.ui.settings;
        const newSettings = {
            apiKey: s.getSettingValue("Doctor.LLM.ApiKey", ""),
            baseUrl: s.getSettingValue("Doctor.LLM.BaseUrl", "https://api.openai.com/v1") || "",
            model: s.getSettingValue("Doctor.LLM.Model", "gpt-4o"),
            language: s.getSettingValue("Doctor.General.Language", "en"),
            provider: s.getSettingValue("Doctor.LLM.Provider", "openai")
        };

        this.setState({ settings: newSettings });
    }
}

// Singleton Instance
export const doctorContext = new DoctorContext();
