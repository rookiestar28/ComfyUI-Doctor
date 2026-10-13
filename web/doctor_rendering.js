/**
 * Doctor Rendering Utilities
 * ==========================
 * Shared rendering pipeline for sanitization, markdown, and code highlighting.
 * Used by Preact islands and vanilla fallback components.
 *
 * @module doctor_rendering
 */

// ═══════════════════════════════════════════════════════════════════════════
// ASSET PATHS
// ═══════════════════════════════════════════════════════════════════════════

// IMPORTANT: ComfyUI serves this extension at /extensions/<install folder>/ and the folder name
// varies (renamed clones, archive extractions), so resolve vendored assets relative to this module.
// An absolute /extensions/ComfyUI-Doctor/ path 404s elsewhere. Do not add a CDN fallback: it loaded
// unpinned third-party script into the ComfyUI origin; missing assets degrade to plain text instead.
const LIB_BASE = new URL('./lib/', import.meta.url);
const LOCAL_MARKED = new URL('marked.min.js', LIB_BASE).href;
const LOCAL_HIGHLIGHT = new URL('highlight.min.js', LIB_BASE).href;
const LOCAL_HIGHLIGHT_CSS = new URL('github-dark.min.css', LIB_BASE).href;

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let assetsLoaded = false;
let loadPromise = null;

// ═══════════════════════════════════════════════════════════════════════════
// ASSET LOADING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load a script dynamically.
 * @param {string} src - Script URL
 * @returns {Promise<void>}
 */
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * Load all rendering assets (marked, highlight.js, CSS) from the extension's own lib/ directory.
 * Never rejects: a missing asset is reported once and rendering falls back to plain text.
 * @returns {Promise<void>}
 */
export async function loadRenderingAssets() {
    if (assetsLoaded) return;
    if (loadPromise) return loadPromise;

    loadPromise = (async () => {
        // CSS
        if (!document.getElementById('hljs-style')) {
            const link = document.createElement('link');
            link.id = 'hljs-style';
            link.rel = 'stylesheet';
            link.href = LOCAL_HIGHLIGHT_CSS;
            link.onerror = () => {
                console.warn('[DoctorRendering] highlight theme unavailable; code blocks stay unstyled');
            };
            document.head.appendChild(link);
        }

        // Marked
        if (!window.marked) {
            try {
                await loadScript(LOCAL_MARKED);
                console.log('[DoctorRendering] ✅ marked loaded from local');
            } catch {
                console.warn('[DoctorRendering] marked unavailable; chat replies render as plain text');
            }
        }

        // Highlight.js
        if (!window.hljs) {
            try {
                await loadScript(LOCAL_HIGHLIGHT);
                console.log('[DoctorRendering] ✅ hljs loaded from local');
            } catch {
                console.warn('[DoctorRendering] highlight.js unavailable; code blocks stay unhighlighted');
            }
        }

        assetsLoaded = true;
    })();

    return loadPromise;
}

// ═══════════════════════════════════════════════════════════════════════════
// SANITIZATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Sanitize HTML to prevent XSS attacks.
 * Removes dangerous tags and event handlers.
 *
 * @param {string} unsafeHtml - HTML content to sanitize
 * @returns {string} Sanitized HTML
 */
export function sanitizeHtml(unsafeHtml) {
    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(unsafeHtml, 'text/html');

        // Remove dangerous tags
        const blockedTags = ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta'];
        blockedTags.forEach(tag => {
            doc.querySelectorAll(tag).forEach(node => node.remove());
        });

        // Remove event handlers and javascript: links
        doc.querySelectorAll('*').forEach(node => {
            [...node.attributes].forEach(attr => {
                const name = attr.name.toLowerCase();
                const value = attr.value || '';
                if (name.startsWith('on')) {
                    node.removeAttribute(attr.name);
                }
                if ((name === 'src' || name === 'href') && /^javascript:/i.test(value.trim())) {
                    node.removeAttribute(attr.name);
                }
            });
        });

        return doc.body.innerHTML;
    } catch (e) {
        // Fallback: escape all HTML
        const div = document.createElement('div');
        div.textContent = unsafeHtml;
        return div.innerHTML;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MARKDOWN RENDERING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Render markdown content to sanitized HTML.
 * Requires assets to be loaded first.
 *
 * @param {string} content - Markdown content
 * @returns {string} Sanitized HTML
 */
export function renderMarkdown(content) {
    if (!window.marked) {
        console.warn('[DoctorRendering] marked not loaded, returning raw content');
        return sanitizeHtml(content);
    }

    const rawHtml = window.marked.parse(content || '');
    return sanitizeHtml(rawHtml);
}

// ═══════════════════════════════════════════════════════════════════════════
// CODE HIGHLIGHTING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Apply syntax highlighting to code blocks in a container.
 *
 * @param {HTMLElement} container - DOM container with code blocks
 */
export function highlightCodeBlocks(container) {
    if (!window.hljs || !container) return;

    container.querySelectorAll('pre code').forEach(block => {
        window.hljs.highlightElement(block);
    });
}

/**
 * Add copy buttons to pre blocks in a container.
 *
 * @param {HTMLElement} container - DOM container with pre blocks
 */
export function addCopyButtons(container) {
    if (!container) return;

    container.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-btn')) return;
        if (!pre.querySelector('code')) return;

        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = '📋';
        btn.title = 'Copy code';
        btn.onclick = () => {
            const code = pre.querySelector('code').innerText;
            navigator.clipboard.writeText(code)
                .then(() => { btn.textContent = '✅'; })
                .catch(() => { btn.textContent = '❌'; });
            setTimeout(() => { btn.textContent = '📋'; }, 2000);
        };
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// FULL PIPELINE
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Full rendering pipeline: markdown → sanitize → highlight → copy buttons.
 *
 * @param {string} content - Markdown content to render
 * @param {HTMLElement} container - Target container element
 * @returns {Promise<void>}
 */
export async function renderContentPipeline(content, container) {
    await loadRenderingAssets();

    const html = renderMarkdown(content);
    container.innerHTML = html;

    highlightCodeBlocks(container);
    addCopyButtons(container);
}

/**
 * Escape HTML to prevent XSS (for text-only content).
 *
 * @param {string} text - Plain text
 * @returns {string} Escaped HTML
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS FOR TESTING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Reset the assets loaded state (for testing only).
 */
export function _resetAssets() {
    assetsLoaded = false;
    loadPromise = null;
}
