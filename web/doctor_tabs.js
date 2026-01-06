/**
 * ComfyUI-Doctor Sidebar Tab Navigation System
 * Implements F13 Tab Infrastructure and prepares for A7 A7 Phase 5A
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
        // console.log(`[ComfyUI-Doctor] Registered tab: ${config.id}`);
    }

    getTab(id) {
        return this.tabs.get(id);
    }

    getAllTabs() {
        return Array.from(this.tabs.values()).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    }
}

// Global registry instance
export const tabRegistry = new TabRegistry();

export class TabManager {
    constructor(registry, containerId, tabBarId) {
        this.registry = registry;
        this.containerId = containerId; // ID of the content wrapper div
        this.tabBarId = tabBarId;       // ID of the tab bar div
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
            const currentEl = document.getElementById(`doctor-tab-${this.activeTabId}`);
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
        const mainContainer = document.getElementById(this.containerId);
        if (!mainContainer) return; // Should not happen if init correct

        let targetEl = document.getElementById(`doctor-tab-${tabId}`);
        if (!targetEl) {
            // Lazy Creation from render function
            targetEl = document.createElement('div');
            targetEl.id = `doctor-tab-${tabId}`;
            targetEl.className = 'doctor-tab-pane';
            // Initially hidden, will be shown below
            mainContainer.appendChild(targetEl);

            // First Render
            try {
                tab.render(targetEl);
            } catch (e) {
                console.error(`[ComfyUI-Doctor] Error rendering tab ${tabId}:`, e);
                targetEl.innerHTML = `<div class="error-state">Failed to render tab: ${e.message}</div>`;
            }
        }

        // 5. Show Target
        targetEl.style.display = 'block';

        // 6. Activate Hook
        if (tab.onActivate) {
            try { tab.onActivate(); } catch (e) { console.error(e); }
        }
    }

    /**
     * Render the Tab Bar buttons
     */
    renderTabBar() {
        const barContainer = document.getElementById(this.tabBarId);
        if (!barContainer) return;

        barContainer.innerHTML = '';
        const tabs = this.registry.getAllTabs();

        tabs.forEach(tab => {
            const btn = document.createElement('div');
            btn.className = 'doctor-tab-button';
            btn.dataset.tabId = tab.id;
            btn.title = tab.label;

            // Icon + Label (Label hidden on small sidebar?)
            // For now just Icon + Label
            btn.innerHTML = `<span class="tab-icon">${tab.icon}</span> <span class="tab-label">${tab.label}</span>`;

            btn.onclick = () => this.activateTab(tab.id);
            barContainer.appendChild(btn);
        });

        this.updateTabBarUI();
    }

    updateTabBarUI() {
        const barContainer = document.getElementById(this.tabBarId);
        if (!barContainer) return;

        // Reset all active classes
        const buttons = barContainer.querySelectorAll('.doctor-tab-button');
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
