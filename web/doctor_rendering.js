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

// IMPORTANT (S32): the assistant reply is untrusted (prompt-injectable through error text and
// workflow content) and is assigned with innerHTML inside the ComfyUI origin. The previous denylist
// matched `/^javascript:/i` on the raw attribute string, but the HTML parser decodes entities and the
// URL parser then drops tab/newline/CR anywhere in the value and strips leading control characters, so
// `java&#9;script:` and `&#1;javascript:` ran script on click. This sanitizer therefore:
//   1. allowlists elements and attributes (unknown elements are unwrapped, dangerous containers removed
//      with their content, anything outside the XHTML namespace such as svg/math removed);
//   2. judges every URL by the PARSED scheme and writes back only the parser's canonical `href`, never
//      the original string, so the browser cannot re-read the value differently from this check;
//   3. builds a NEW tree inside the inert DOMParser document and serializes only that tree, so nothing
//      the parser mutated (noscript/template/foreign content) is re-parsed by the later innerHTML
//      assignment, and creating an <img> cannot start a network request here.
// Tempting but wrong: re-adding a regex scheme check, allowing `style`/`form`/`svg`, or returning the
// parsed document's own markup after removing nodes in place.
const XHTML_NS = 'http://www.w3.org/1999/xhtml';
const MAX_SANITIZED_URL_LENGTH = 2048;
const MAX_SANITIZED_TEXT_ATTR_LENGTH = 1000;
const LINK_SCHEMES = new Set(['http:', 'https:', 'mailto:']);
const IMAGE_SCHEMES = new Set(['http:', 'https:']);
const FRAGMENT_LINK = /^#[A-Za-z0-9_.:-]{0,128}$/;
const CODE_LANGUAGE_CLASS = /^language-[A-Za-z0-9_+-]{1,32}$/;
const SAFE_TAGS = new Set([
    'a', 'b', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
    'input', 'li', 'ol', 'p', 'pre', 's', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'u', 'ul',
]);
// Removed together with their content; every other unknown element is unwrapped (its children are kept).
const DROPPED_TAGS = new Set([
    'applet', 'audio', 'base', 'button', 'canvas', 'dialog', 'embed', 'form', 'frame', 'frameset', 'head', 'iframe',
    'link', 'math', 'meta', 'noembed', 'noframes', 'noscript', 'object', 'script', 'select', 'style', 'svg',
    'template', 'textarea', 'title', 'track', 'video', 'xmp',
]);

/**
 * Judge a URL attribute value by its parsed scheme and return the parser's canonical form, or null.
 * Only absolute http(s) (plus mailto for links) and bare fragment links survive; relative, protocol-relative,
 * credential-bearing, oversized and unparsable values are rejected.
 *
 * @param {unknown} value - Raw attribute value as decoded by the HTML parser
 * @param {'a'|'img'} kind - Which element the value belongs to
 * @returns {string|null} Canonical URL to write back, or null to drop the attribute
 */
export function judgeSanitizerUrl(value, kind) {
    if (typeof value !== 'string' || value.length > MAX_SANITIZED_URL_LENGTH) return null;
    // The URL parser strips these itself; trimming first only lets the fragment test see the same text.
    const candidate = value.replace(/^[\u0000- ]+|[\u0000- ]+$/g, '');
    if (kind === 'a' && FRAGMENT_LINK.test(candidate)) return candidate;
    let parsed;
    try {
        parsed = new URL(candidate);
    } catch (error) {
        return null;
    }
    const schemes = kind === 'a' ? LINK_SCHEMES : IMAGE_SCHEMES;
    if (!schemes.has(parsed.protocol)) return null;
    if (parsed.protocol !== 'mailto:' && !parsed.hostname) return null;
    if (parsed.username || parsed.password) return null;
    return parsed.href.length > MAX_SANITIZED_URL_LENGTH ? null : parsed.href;
}

function limitedAttribute(node, name) {
    const value = node.getAttribute(name);
    return value === null ? null : value.slice(0, MAX_SANITIZED_TEXT_ATTR_LENGTH);
}

/**
 * Create the sanitized counterpart of one allowlisted element, or null when it must be unwrapped/dropped.
 * Attributes are copied one by one from an explicit per-tag allowlist; nothing else is ever carried over.
 */
function createSafeElement(source, doc) {
    const tag = source.localName;
    const target = doc.createElement(tag);
    const setText = (name) => {
        const value = limitedAttribute(source, name);
        if (value !== null) target.setAttribute(name, value);
    };
    switch (tag) {
        case 'a': {
            const href = judgeSanitizerUrl(source.getAttribute('href'), 'a');
            if (href === null) return null;
            target.setAttribute('href', href);
            setText('title');
            target.setAttribute('rel', 'noopener noreferrer');
            target.setAttribute('target', '_blank');
            break;
        }
        case 'img': {
            const src = judgeSanitizerUrl(source.getAttribute('src'), 'img');
            if (src === null) return null;
            target.setAttribute('src', src);
            setText('alt');
            setText('title');
            target.setAttribute('referrerpolicy', 'no-referrer');
            break;
        }
        case 'input':
            // Only the disabled task-list checkbox that markdown emits; any other input is dropped.
            if ((source.getAttribute('type') || '').toLowerCase() !== 'checkbox') return null;
            target.setAttribute('type', 'checkbox');
            target.setAttribute('disabled', '');
            if (source.hasAttribute('checked')) target.setAttribute('checked', '');
            break;
        case 'code': {
            const className = source.getAttribute('class');
            if (className !== null && CODE_LANGUAGE_CLASS.test(className)) target.setAttribute('class', className);
            break;
        }
        case 'ol': {
            const start = source.getAttribute('start');
            if (start !== null && /^\d{1,6}$/.test(start)) target.setAttribute('start', start);
            break;
        }
        case 'td':
        case 'th': {
            const align = (source.getAttribute('align') || '').toLowerCase();
            if (align === 'left' || align === 'center' || align === 'right') target.setAttribute('align', align);
            break;
        }
        default:
            break;
    }
    return target;
}

function copySafeChildren(sourceParent, targetParent, doc) {
    for (const node of sourceParent.childNodes) {
        if (node.nodeType === 3) {
            targetParent.appendChild(doc.createTextNode(node.data));
            continue;
        }
        // Comments, processing instructions and anything else are dropped.
        if (node.nodeType !== 1) continue;
        const tag = node.localName;
        if (node.namespaceURI !== XHTML_NS || DROPPED_TAGS.has(tag)) continue;
        if (!SAFE_TAGS.has(tag)) {
            copySafeChildren(node, targetParent, doc);
            continue;
        }
        const safe = createSafeElement(node, doc);
        if (safe === null) {
            copySafeChildren(node, targetParent, doc);
            continue;
        }
        targetParent.appendChild(safe);
        copySafeChildren(node, safe, doc);
    }
}

/**
 * Sanitize untrusted HTML (rendered markdown from an LLM reply) with an allowlist.
 * Fails closed: any error returns the input escaped as text, never the unsanitized markup.
 *
 * @param {string} unsafeHtml - HTML content to sanitize
 * @returns {string} Sanitized HTML
 */
export function sanitizeHtml(unsafeHtml) {
    const input = typeof unsafeHtml === 'string' ? unsafeHtml : String(unsafeHtml ?? '');
    try {
        const doc = new DOMParser().parseFromString(input, 'text/html');
        const root = doc.createElement('div');
        copySafeChildren(doc.body, root, doc);
        return root.innerHTML;
    } catch (e) {
        // Fallback: escape all HTML
        const div = document.createElement('div');
        div.textContent = input;
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
// TEXT ESCAPING
// ═══════════════════════════════════════════════════════════════════════════

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
