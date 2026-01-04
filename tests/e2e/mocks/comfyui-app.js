/**
 * Mock ComfyUI app object for isolated testing
 *
 * This provides the minimal interface that Doctor UI expects from ComfyUI,
 * allowing us to test the UI without running a full ComfyUI instance.
 */

export function createMockComfyUIApp() {
  const mockSettings = new Map();
  const mockExtensions = [];
  const mockSidebarTabs = [];

  const app = {
    ui: {
      settings: {
        addSetting(config) {
          console.log('[Mock] Adding setting:', config.id);
          mockSettings.set(config.id, config);
          // Set initial value
          if (config.defaultValue !== undefined) {
            mockSettings.get(config.id).value = config.defaultValue;
          }
          return config;
        },
        getSettingValue(id, defaultValue) {
          const setting = mockSettings.get(id);
          return setting?.value ?? setting?.defaultValue ?? defaultValue;
        },
        setSettingValue(id, value) {
          const setting = mockSettings.get(id);
          if (setting) {
            setting.value = value;
          } else {
            // Create setting if it doesn't exist
            mockSettings.set(id, { id, value, defaultValue: value });
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
    extensionManager: {
      // Mock extension manager
    },
    registerExtension(extension) {
      console.log('[Mock] Registering extension:', extension.name);
      mockExtensions.push(extension);
      // Call setup immediately for testing
      if (extension.setup) {
        setTimeout(() => extension.setup.call(extension), 0);
      }
    },
  };

  // Mock sidebar API (for left sidebar tabs)
  if (typeof window !== 'undefined') {
    window.comfyAPI = window.comfyAPI || {};
    window.comfyAPI.sidebarTab = window.comfyAPI.sidebarTab || {
      addTab(config) {
        console.log('[Mock] Adding sidebar tab:', config.id);
        mockSidebarTabs.push(config);

        // Create mock sidebar tab in DOM
        const tabContainer = document.getElementById('mock-sidebar-tabs');
        if (tabContainer && config.render) {
          const tabElement = document.createElement('div');
          tabElement.id = `sidebar-tab-${config.id}`;
          tabElement.className = 'mock-sidebar-tab';
          tabContainer.appendChild(tabElement);

          // Render the tab content
          config.render(tabElement);
        }

        return config;
      },
    };
  }

  return app;
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
