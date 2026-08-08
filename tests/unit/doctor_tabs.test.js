import { beforeEach, afterEach, describe, expect, it } from 'vitest';
import { TabManager, TabRegistry } from '../../web/doctor_tabs.js';

function createClassList() {
  const values = new Set();
  return {
    add(value) {
      values.add(value);
    },
    remove(value) {
      values.delete(value);
    },
    has(value) {
      return values.has(value);
    },
  };
}

function createElement(tagName = 'div') {
  return {
    tagName,
    id: '',
    className: '',
    title: '',
    textContent: '',
    dataset: {},
    innerHTML: '',
    children: [],
    style: {},
    classList: createClassList(),
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    replaceChildren(...children) {
      this.children = children;
      this.innerHTML = '';
    },
    querySelector(selector) {
      if (!selector.startsWith('#')) return null;
      const id = selector.slice(1);
      return this.children.find((child) => child.id === id) || null;
    },
    querySelectorAll(selector) {
      if (selector !== '.doctor-tab-button') return [];
      return this.children.filter((child) => child.className === 'doctor-tab-button');
    },
  };
}

describe('TabManager cleanup', () => {
  let localStorageMock;
  let originalDocument;
  let originalLocalStorage;

  beforeEach(() => {
    originalDocument = global.document;
    originalLocalStorage = global.localStorage;

    global.document = {
      createElement: (tag) => createElement(tag),
    };

    const store = new Map();
    localStorageMock = {
      getItem(key) {
        return store.has(key) ? store.get(key) : null;
      },
      setItem(key, value) {
        store.set(key, String(value));
      },
    };
    global.localStorage = localStorageMock;
  });

  afterEach(() => {
    global.document = originalDocument;
    global.localStorage = originalLocalStorage;
  });

  it('runs async tab cleanup when manager is destroyed', async () => {
    const registry = new TabRegistry();
    const content = createElement('div');
    const tabBar = createElement('div');
    let cleaned = false;

    registry.register({
      id: 'chat',
      label: 'Chat',
      icon: 'C',
      order: 10,
      render: async () => () => {
        cleaned = true;
      },
    });

    const manager = new TabManager(registry, content, tabBar);
    manager.init();

    await Promise.resolve();
    await Promise.resolve();

    manager.destroy();

    expect(cleaned).toBe(true);
    expect(content.innerHTML).toBe('');
    expect(tabBar.innerHTML).toBe('');
  });

  it('passes the owned tab pane to the activation hook', () => {
    const registry = new TabRegistry();
    const content = createElement('div');
    const tabBar = createElement('div');
    let activatedPane;

    registry.register({
      id: 'chat',
      label: 'Chat',
      icon: 'C',
      order: 10,
      render: () => undefined,
      onActivate: (pane) => {
        activatedPane = pane;
      },
    });

    const manager = new TabManager(registry, content, tabBar);
    manager.init();

    expect(activatedPane).toBe(content.children[0]);
  });

  it('runs a late async cleanup immediately after manager destruction', async () => {
    const registry = new TabRegistry();
    const content = createElement('div');
    const tabBar = createElement('div');
    let resolveRender;
    let cleanupCount = 0;

    registry.register({
      id: 'chat',
      label: 'Chat',
      icon: 'C',
      order: 10,
      render: () => new Promise((resolve) => {
        resolveRender = () => resolve(() => {
          cleanupCount += 1;
        });
      }),
    });

    const manager = new TabManager(registry, content, tabBar);
    manager.init();
    manager.destroy();
    resolveRender();
    await Promise.resolve();
    await Promise.resolve();

    expect(cleanupCount).toBe(1);
    expect(manager.tabCleanups.size).toBe(0);
  });

  it('renders synchronous tab failures as literal text', () => {
    const payload = '<span id="dynamic-status-unit-sync-marker">sync marker</span>';
    const registry = new TabRegistry();
    const content = createElement('div');
    const tabBar = createElement('div');

    registry.register({
      id: 'sync-failure',
      label: 'Sync failure',
      icon: 'S',
      order: 10,
      render: () => {
        throw new Error(payload);
      },
    });

    const manager = new TabManager(registry, content, tabBar);
    manager.init();

    const pane = content.children[0];
    expect(pane.innerHTML).toBe('');
    expect(pane.children).toHaveLength(1);
    expect(pane.children[0].textContent).toContain(payload);
  });

  it('renders asynchronous tab failures as literal text', async () => {
    const payload = '<span id="dynamic-status-unit-async-marker">async marker</span>';
    const registry = new TabRegistry();
    const content = createElement('div');
    const tabBar = createElement('div');

    registry.register({
      id: 'async-failure',
      label: 'Async failure',
      icon: 'A',
      order: 10,
      render: async () => {
        throw new Error(payload);
      },
    });

    const manager = new TabManager(registry, content, tabBar);
    manager.init();
    await Promise.resolve();
    await Promise.resolve();

    const pane = content.children[0];
    expect(pane.innerHTML).toBe('');
    expect(pane.children).toHaveLength(1);
    expect(pane.children[0].textContent).toContain(payload);
  });
});
