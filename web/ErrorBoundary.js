/**
 * ErrorBoundary.js
 * =================
 * Preact Error Boundary Component for ComfyUI-Doctor.
 * Uses async factory pattern because preact-loader.js doesn't export named exports.
 *
 * R5: Frontend Error Boundaries
 * @module ErrorBoundary
 */

import { loadPreact } from './preact-loader.js';
import { recordError } from './island_registry.js';
import { sanitizeErrorData } from './privacy_utils.js';

/**
 * Create ErrorBoundary class using loaded Preact modules.
 * MUST be called AFTER loadPreact() completes.
 *
 * @param {Object} preactModules - Result from loadPreact()
 * @returns {Class} ErrorBoundary component class
 */
export function createErrorBoundary(preactModules) {
    const { Component, html } = preactModules;

    return class ErrorBoundary extends Component {
        constructor(props) {
            super(props);
            this.state = {
                hasError: false,
                error: null,
                errorId: null,
                attemptCount: 0,
                copied: false,
                copyFailed: false
            };
        }

        componentDidCatch(error, errorInfo) {
            const errorId = this.generateErrorId();
            const attemptCount = this.state.attemptCount + 1;

            // 1. Record to island registry
            if (this.props.islandId) {
                recordError(this.props.islandId, error);
            }

            // 2. Sanitize error data before logging (respect privacy_mode)
            const sanitized = sanitizeErrorData({
                message: error.message,
                stack: error.stack
            });

            // 3. Console logging (NO telemetry in Phase 1)
            console.error(`[ErrorBoundary] Component error (${errorId}):`, {
                islandId: this.props.islandId,
                error: sanitized.message,
                stack: sanitized.stack,
                attemptCount,
                componentStack: errorInfo?.componentStack
            });

            // 4. Update UI state
            this.setState({
                hasError: true,
                error,
                errorId,
                attemptCount
            });
        }

        generateErrorId() {
            const timestamp = Date.now();
            const random = Math.random().toString(36).substring(2, 11);
            return `err-${timestamp}-${random}`;
        }

        handleReload = () => {
            if (this.state.attemptCount < 3) {
                this.setState({ hasError: false }); // Remount children
            }
        }

        handleCopyId = async () => {
            try {
                await navigator.clipboard.writeText(this.state.errorId);
                this.setState({ copied: true, copyFailed: false });
                setTimeout(() => this.setState({ copied: false }), 2000);
            } catch (err) {
                console.error('[ErrorBoundary] Failed to copy error ID:', err);
                // Fallback for non-secure context (http://, permissions denied)
                this.fallbackCopyToClipboard(this.state.errorId);
            }
        }

        /**
         * Fallback copy method for non-secure contexts.
         * Uses temporary textarea + execCommand('copy').
         */
        fallbackCopyToClipboard(text) {
            try {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                const success = document.execCommand('copy');
                document.body.removeChild(textarea);

                if (success) {
                    this.setState({ copied: true, copyFailed: false });
                    setTimeout(() => this.setState({ copied: false }), 2000);
                } else {
                    console.error('[ErrorBoundary] Fallback copy failed');
                    this.setState({ copyFailed: true });
                    setTimeout(() => this.setState({ copyFailed: false }), 2000);
                }
            } catch (err) {
                console.error('[ErrorBoundary] Fallback copy exception:', err);
                this.setState({ copyFailed: true });
                setTimeout(() => this.setState({ copyFailed: false }), 2000);
            }
        }

        render() {
            if (this.state.hasError) {
                const isPermanent = this.state.attemptCount >= 3;
                const uiText = this.props.uiText || {};

                return html`
                    <div class="error-boundary-container ${isPermanent ? 'permanent' : ''}">
                        <div class="error-boundary-icon">⚠️</div>
                        <h3 class="error-boundary-title">
                            ${isPermanent
                        ? (uiText.error_boundary_permanent_title || 'Component Failed to Load')
                        : (uiText.error_boundary_title || 'Component Error')
                    }
                        </h3>
                        <p class="error-boundary-message">
                            ${isPermanent
                        ? (uiText.error_boundary_permanent_msg || 'This component failed after 3 reload attempts.')
                        : (uiText.error_boundary_msg || 'This component encountered an error.')
                    }
                        </p>
                        <div class="error-boundary-actions">
                            ${!isPermanent ? html`
                                <button
                                    class="error-boundary-btn reload-btn"
                                    onClick=${this.handleReload}
                                >
                                    ${uiText.error_boundary_reload_btn || 'Reload Component'}
                                </button>
                            ` : null}
                            <button
                                class="error-boundary-btn copy-btn ${this.state.copied ? 'copied' : (this.state.copyFailed ? 'failed' : '')}"
                                onClick=${this.handleCopyId}
                            >
                                ${this.state.copied
                        ? (uiText.error_boundary_copied || 'Copied!')
                        : this.state.copyFailed
                            ? (uiText.error_boundary_copy_failed || 'Copy Failed')
                            : (uiText.error_boundary_copy_id_btn || 'Copy Error ID')
                    }
                            </button>
                        </div>
                        <p class="error-boundary-error-id">
                            ${uiText.error_boundary_error_id_label || 'Error ID:'} <code>${this.state.errorId}</code>
                        </p>
                    </div>
                `;
            }

            return this.props.children;
        }
    }; // End of ErrorBoundary class
}

/**
 * Convenience async wrapper to load Preact and create ErrorBoundary.
 * Usage in islands:
 *   const ErrorBoundary = await createErrorBoundaryAsync();
 *
 * @returns {Promise<Class>} ErrorBoundary component class
 */
export async function createErrorBoundaryAsync() {
    const preactModules = await loadPreact();
    return createErrorBoundary(preactModules);
}
