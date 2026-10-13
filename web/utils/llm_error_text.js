/**
 * User-facing text for LLM route error codes.
 *
 * The backend returns stable error codes (for example `destination_not_allowed` when the requested
 * base URL is not an operator-approved destination). Known codes are shown as localized guidance;
 * any other value is shown unchanged.
 */

import { t } from "./i18n_fallback.js";

export const DESTINATION_NOT_ALLOWED = "destination_not_allowed";

const DESTINATION_NOT_ALLOWED_FALLBACK =
    "This LLM endpoint is not approved on this server. Ask the server operator to add it to DOCTOR_LLM_ALLOWED_BASE_URLS.";

/**
 * @param {string} codeOrMessage - Error code or message from an LLM route.
 * @param {Object} uiText - Loaded UI text dictionary (may be empty).
 * @returns {string}
 */
export function describeLlmError(codeOrMessage, uiText) {
    if (codeOrMessage === DESTINATION_NOT_ALLOWED) {
        return t(uiText, "llm_destination_not_allowed", DESTINATION_NOT_ALLOWED_FALLBACK);
    }
    return codeOrMessage;
}
