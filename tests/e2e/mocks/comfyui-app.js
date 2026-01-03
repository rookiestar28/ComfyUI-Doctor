/**
 * Mock ComfyUI app object for isolated testing
 *
 * This provides the minimal interface that Doctor UI expects from ComfyUI,
 * allowing us to test the UI without running a full ComfyUI instance.
 */

export function createMockComfyUIApp() {
  const mockSettings = new Map();

  return {
    ui: {
      settings: {
        addSetting(config) {
          console.log('[Mock] Adding setting:', config.id);
          mockSettings.set(config.id, config);
          return config;
        },
        getSettingValue(id, defaultValue) {
          return mockSettings.get(id)?.defaultValue ?? defaultValue;
        },
        setSettingValue(id, value) {
          const setting = mockSettings.get(id);
          if (setting) {
            setting.defaultValue = value;
          }
        },
      },
    },
    graph: {
      _nodes: [],
      clear() {
        this._nodes = [];
      },
    },
    canvas: {
      ds: { scale: 1, offset: [0, 0] },
    },
  };
}

export function createMockComfyUIAPI() {
  const eventListeners = new Map();

  return {
    addEventListener(event, callback) {
      if (!eventListeners.has(event)) {
        eventListeners.set(event, []);
      }
      eventListeners.get(event).push(callback);
      console.log(`[Mock API] Registered listener for: ${event}`);
    },

    removeEventListener(event, callback) {
      const listeners = eventListeners.get(event);
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
    },

    async fetchApi(endpoint, options = {}) {
      console.log(`[Mock API] Fetching: ${endpoint}`);

      // Mock UI text endpoint
      if (endpoint === '/doctor/ui_text') {
        const uiText = await fetch('/mocks/ui-text.json').then(r => r.json());
        return {
          ok: true,
          status: 200,
          json: async () => uiText,
        };
      }

      // Mock settings endpoint
      if (endpoint === '/doctor/settings') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            language: 'en',
            provider: 'openai',
            model: 'gpt-4',
          }),
        };
      }

      // Default mock response
      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      };
    },

    // Trigger mock events for testing
    _triggerEvent(event, data) {
      const listeners = eventListeners.get(event);
      if (listeners) {
        listeners.forEach(callback => callback(data));
      }
    },
  };
}
