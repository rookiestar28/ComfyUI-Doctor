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
    dataset: {},
    innerHTML: '',
    children: [],
    style: {},
    classList: createClassList(),
    appendChild(child) {
      this.children.push(child);
      return child;
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
});
