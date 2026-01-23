/**
 * Pure functions for i18n fallback logic.
 */

/**
 * Get translated text or fallback.
 * @param {Object} uiText - The dictionary of keys
 * @param {String} key - The key to look up
 * @param {String} fallback - The fallback text if key missing
 * @returns {String}
 */
export function t(uiText, key, fallback) {
    if (!uiText || typeof uiText[key] === 'undefined') {
        return fallback;
    }
    return uiText[key];
}
