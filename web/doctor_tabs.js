/**
 * ComfyUI-Doctor Sidebar Tab Navigation System
 * Implements F13 Tab Infrastructure and prepares for A7 A7 Phase 5A
 * 
 * ═══════════════════════════════════════════════════════════════
 * CRITICAL FIX (2026-01-06): Direct DOM Reference Usage
 * ═══════════════════════════════════════════════════════════════
 * Previous issue: document.getElementById() returned null because
 * ComfyUI uses Vue.js and the sidebar container might be in a
 * different context (Shadow DOM or Vue component isolation).
 *
 * Solution: TabManager now accepts direct DOM element references
 * instead of relying on global ID lookup.
 * ═══════════════════════════════════════════════════════════════
 */

export class TabRegistry {
    constructor() {
        this.tabs = new Map();
    }

    /**
     * Register a new tab
     * @param {Object} config Tab configuration
     * @param {string} config.id Unique tab ID
     * @param {string} config.icon Icon character or HTML
     * @param {string} config.label Tab label text
     * @param {number} config.order Sort order (lower = first)
     * @param {Function} config.render Render function (container) => void
     * @param {Function} [config.onActivate] Lifecycle hook when tab becomes active
     * @param {Function} [config.onDeactivate] Lifecycle hook when tab becomes inactive
     */
    register(config) {
        if (!config.id || !config.render) {
            console.error('[ComfyUI-Doctor] Invalid tab config:', config);
            return;
        }
        this.tabs.set(config.id, config);
    }

    getTab(id) {
        return this.tabs.get(id);
    }

    getAllTabs() {
        return Array.from(this.tabs.values()).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    }

    clear() {
        this.tabs.clear();
    }
}

// Global registry instance
export const tabRegistry = new TabRegistry();

export class TabManager {
    /**
     * Create TabManager with direct DOM element references
     * 
     * ⚠️ IMPORTANT: Use DOM elements, NOT ID strings!
     * document.getElementById() fails in ComfyUI's Vue context.
     * 
     * @param {TabRegistry} registry Tab registry instance
     * @param {HTMLElement} contentContainer DOM element for tab content
     * @param {HTMLElement} tabBarContainer DOM element for tab bar
     */
    constructor(registry, contentContainer, tabBarContainer) {
        this.registry = registry;
        this.contentContainer = contentContainer;
        this.tabBarContainer = tabBarContainer;
        this.activeTabId = null;
    }

    /**
     * Switch to specific tab
     * @param {string} tabId Target tab ID
     */
    activateTab(tabId) {
        const tab = this.registry.getTab(tabId);
        if (!tab) {
            console.error(`[ComfyUI-Doctor] Tab not found: ${tabId}`);
            return;
        }

        // 1. Deactivate current tab
        if (this.activeTabId) {
            const currentTab = this.registry.getTab(this.activeTabId);
            const currentEl = this.contentContainer.querySelector(`#doctor-tab-${this.activeTabId}`);
            if (currentEl) {
                currentEl.style.display = 'none';
            }
            // Hook
            if (currentTab?.onDeactivate) {
                try { currentTab.onDeactivate(); } catch (e) { console.error(e); }
            }
        }

        // 2. Update Active ID
        this.activeTabId = tabId;
        localStorage.setItem('doctor_active_tab', tabId);

        // 3. Update Tab Bar UI (Highlight active button)
        this.updateTabBarUI();

        // 4. Get or Create Content Container for Target Tab
        if (!this.contentContainer) {
            console.error('[ComfyUI-Doctor] Content container not set');
            return;
        }

        let targetEl = this.contentContainer.querySelector(`#doctor-tab-${tabId}`);
        if (!targetEl) {
            // Lazy Creation from render function
            targetEl = document.createElement('div');
            targetEl.id = `doctor-tab-${tabId}`;
            targetEl.className = 'doctor-tab-pane';
            // Initially hidden, will be shown below
            this.contentContainer.appendChild(targetEl);

            // First Render
            try {
                console.log(`[ComfyUI-Doctor] Rendering tab: ${tabId}`);
                tab.render(targetEl);
            } catch (e) {
                console.error(`[ComfyUI-Doctor] Error rendering tab ${tabId}:`, e);
                targetEl.innerHTML = `<div class="error-state" style="padding: 20px; color: #ff5555;">Failed to render tab: ${e.message}</div>`;
            }
        }

        // ═══════════════════════════════════════════════════════════════
        // 5. Show Target - MUST USE display: flex, NOT display: block!
        // ═══════════════════════════════════════════════════════════════
        // ⚠️ CRITICAL FIX (2026-01-06): Chat scrolling broken if block
        // 
        // Previous bug: Using display: 'block' broke the flex layout chain,
        // causing child elements (messages area) to not scroll properly
        // because min-height: 0 only works in flex containers.
        //
        // DO NOT CHANGE THIS TO 'block'!
        // ═══════════════════════════════════════════════════════════════
        targetEl.style.display = 'flex';
        targetEl.style.flexDirection = 'column';

        // 6. Activate Hook
        if (tab.onActivate) {
            try { tab.onActivate(); } catch (e) { console.error(e); }
        }
    }

    /**
     * Render the Tab Bar buttons
     */
    renderTabBar() {
        if (!this.tabBarContainer) {
            console.error('[ComfyUI-Doctor] ❌ Tab bar container not set');
            return;
        }

        this.tabBarContainer.innerHTML = '';
        const tabs = this.registry.getAllTabs();
        console.log(`[ComfyUI-Doctor] renderTabBar: rendering ${tabs.length} tabs`);

        tabs.forEach(tab => {
            const btn = document.createElement('div');
            btn.className = 'doctor-tab-button';
            btn.dataset.tabId = tab.id;
            btn.title = tab.label;

            // Icon + Label
            btn.innerHTML = `<span class="tab-icon">${tab.icon}</span> <span class="tab-label">${tab.label}</span>`;

            btn.onclick = () => this.activateTab(tab.id);
            this.tabBarContainer.appendChild(btn);
        });

        this.updateTabBarUI();
    }

    updateTabBarUI() {
        if (!this.tabBarContainer) return;

        // Reset all active classes
        const buttons = this.tabBarContainer.querySelectorAll('.doctor-tab-button');
        buttons.forEach(btn => {
            if (btn.dataset.tabId === this.activeTabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    /**
     * Initialize tab system
     * @returns {string} Initial tab ID
     */
    init() {
        this.renderTabBar();

        // Restore active tab or default to first
        const saved = localStorage.getItem('doctor_active_tab');
        const first = this.registry.getAllTabs()[0]?.id;
        const initial = (saved && this.registry.getTab(saved)) ? saved : first;

        if (initial) {
            this.activateTab(initial);
        }
        return initial;
    }
}
