/**
 * Privacy Utilities
 * =================
 * Frontend PII sanitization for error data.
 * Mirrors backend sanitizer.py patterns.
 *
 * R5: Frontend Error Boundaries
 * @module privacy_utils
 */

// ═══════════════════════════════════════════════════════════════════════════
// PATTERNS
// ═══════════════════════════════════════════════════════════════════════════

const PATTERNS = {
    // Windows user paths: C:\Users\username -> <USER_PATH>
    windowsUserPath: /C:\\Users\\[^\\]+/gi,
    // Unix home paths: /home/username -> <USER_HOME>
    unixHomePath: /\/home\/[^\/]+/gi,
    // macOS home paths: /Users/username -> <USER_HOME>
    macHomePath: /\/Users\/[^\/]+/gi,
    // API keys: sk-xxx, pk-xxx, api_xxx -> <API_KEY>
    apiKey: /\b(sk|pk|api)[-_]?[a-zA-Z0-9]{20,}\b/gi,
    // Emails: user@example.com -> <EMAIL>
    email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi,
    // Private IPs: 192.168.x.x, 10.x.x.x, 172.16-31.x.x -> <PRIVATE_IP>
    privateIp: /\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b/g
};

// ═══════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get privacy mode from ComfyUI settings.
 * @returns {'none'|'basic'|'strict'} Current privacy mode
 */
function getPrivacyMode() {
    try {
        const mode = window.app?.ui?.settings?.getSettingValue?.(
            'Doctor.Privacy.Mode',
            'basic'
        );
        return mode || 'basic';
    } catch (err) {
        return 'basic'; // Default to basic
    }
}

/**
 * Apply sanitization patterns to a string.
 */
function sanitizeString(str) {
    if (!str) return str;

    let result = str;
    result = result.replace(PATTERNS.windowsUserPath, '<USER_PATH>');
    result = result.replace(PATTERNS.unixHomePath, '<USER_HOME>');
    result = result.replace(PATTERNS.macHomePath, '<USER_HOME>');
    result = result.replace(PATTERNS.apiKey, '<API_KEY>');
    result = result.replace(PATTERNS.email, '<EMAIL>');
    result = result.replace(PATTERNS.privateIp, '<PRIVATE_IP>');

    return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Sanitize error data based on current privacy mode.
 *
 * Privacy Mode Matrix:
 * | Mode   | Stack Trace | File Paths       | IPs    |
 * |--------|-------------|------------------|--------|
 * | none   | Full        | Full             | Full   |
 * | basic  | Sanitized   | Username removed | Hidden |
 * | strict | Removed     | Filename only    | Hidden |
 *
 * @param {Object} data - Error data to sanitize
 * @param {string} [data.message] - Error message
 * @param {string} [data.source] - Source file path
 * @param {string} [data.stack] - Stack trace
 * @param {number} [data.lineno] - Line number
 * @param {number} [data.colno] - Column number
 * @returns {Object} Sanitized error data
 */
export function sanitizeErrorData(data) {
    const mode = getPrivacyMode();
    const { message, source, stack, lineno, colno } = data;

    if (mode === 'none') {
        return data; // No sanitization
    }

    let sanitizedMessage = message || '';
    let sanitizedSource = source || '';
    let sanitizedStack = stack || '';

    if (mode === 'basic' || mode === 'strict') {
        // Sanitize all fields
        sanitizedMessage = sanitizeString(sanitizedMessage);
        sanitizedSource = sanitizeString(sanitizedSource);
        sanitizedStack = sanitizeString(sanitizedStack);
    }

    if (mode === 'strict') {
        // Remove file paths entirely (keep only filename)
        if (sanitizedSource) {
            const parts = sanitizedSource.split(/[\/\\]/);
            sanitizedSource = parts[parts.length - 1] || '<PATH>';
        }
        // Remove stack trace in strict mode
        sanitizedStack = '';
    }

    return {
        message: sanitizedMessage,
        source: sanitizedSource,
        stack: sanitizedStack,
        lineno: mode === 'strict' ? null : lineno,
        colno: mode === 'strict' ? null : colno
    };
}
