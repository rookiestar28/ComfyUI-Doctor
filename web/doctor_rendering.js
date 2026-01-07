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

const LOCAL_MARKED = "/extensions/ComfyUI-Doctor/lib/marked.min.js";
const LOCAL_HIGHLIGHT = "/extensions/ComfyUI-Doctor/lib/highlight.min.js";
const LOCAL_HIGHLIGHT_CSS = "/extensions/ComfyUI-Doctor/lib/github-dark.min.css";
const CDN_MARKED = "https://cdn.jsdelivr.net/npm/marked@15.0.4/marked.min.js";
const CDN_HIGHLIGHT = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js";
const CDN_HIGHLIGHT_CSS = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css";

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
 * Load all rendering assets (marked, highlight.js, CSS).
 * Uses local vendor files with CDN fallback.
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
            link.onerror = () => { link.href = CDN_HIGHLIGHT_CSS; };
            document.head.appendChild(link);
        }

        // Marked
        if (!window.marked) {
            try {
                await loadScript(LOCAL_MARKED);
                console.log('[DoctorRendering] ✅ marked loaded from local');
            } catch {
                await loadScript(CDN_MARKED);
                console.log('[DoctorRendering] ✅ marked loaded from CDN');
            }
        }

        // Highlight.js
        if (!window.hljs) {
            try {
                await loadScript(LOCAL_HIGHLIGHT);
                console.log('[DoctorRendering] ✅ hljs loaded from local');
            } catch {
                await loadScript(CDN_HIGHLIGHT);
                console.log('[DoctorRendering] ✅ hljs loaded from CDN');
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
