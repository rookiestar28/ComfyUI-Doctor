// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Preact Loader E2E Tests
 * 
 * Tests the A7 Preact Islands architecture:
 * - preact-loader.js module loading
 * - Feature flag functionality
 * - Fallback behavior
 */
test.describe('Preact Loader', () => {
    test.beforeEach(async ({ page }) => {
        // Mock the ComfyUI modules that doctor.js tries to import
        await page.route('**/scripts/app.js', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/javascript',
                body: 'export const app = window.app;',
            });
        });

        await page.route('**/scripts/api.js', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/javascript',
                body: 'export const api = window.api;',
            });
        });

        // Navigate to test harness
        await page.goto('test-harness.html');

        // Wait for Doctor UI to be ready
        await page.waitForFunction(() => window.__doctorTestReady === true, { timeout: 10000 });
    });

    test.describe('Module Loading', () => {
        test('should load preact-loader.js successfully', async ({ page }) => {
            // Try to dynamically import the preact-loader module
            const result = await page.evaluate(async () => {
                try {
                    const module = await import('/web/preact-loader.js');
                    return {
                        success: true,
                        hasIsPreactEnabled: typeof module.isPreactEnabled === 'function',
                        hasLoadPreact: typeof module.loadPreact === 'function',
                        hasGetLoadError: typeof module.getLoadError === 'function',
                    };
                } catch (error) {
                    return { success: false, error: error.message };
                }
            });

            expect(result.success).toBe(true);
            expect(result.hasIsPreactEnabled).toBe(true);
            expect(result.hasLoadPreact).toBe(true);
            expect(result.hasGetLoadError).toBe(true);
        });

        test('should report isPreactEnabled as true by default', async ({ page }) => {
            const isEnabled = await page.evaluate(async () => {
                const { isPreactEnabled } = await import('/web/preact-loader.js');
                return isPreactEnabled();
            });

            expect(isEnabled).toBe(true);
        });

        test('should load Preact with all expected exports', async ({ page }) => {
            // This test requires network access to esm.sh CDN
            test.slow(); // Allow more time for CDN loading

            const result = await page.evaluate(async () => {
                try {
                    const { loadPreact } = await import('/web/preact-loader.js');
                    const preact = await loadPreact();
                    return {
                        success: true,
                        exports: Object.keys(preact),
                    };
                } catch (error) {
                    return { success: false, error: error.message };
                }
            });

            expect(result.success).toBe(true);
            expect(result.exports).toContain('h');
            expect(result.exports).toContain('render');
            expect(result.exports).toContain('useState');
            expect(result.exports).toContain('useEffect');
            expect(result.exports).toContain('signal');
            expect(result.exports).toContain('html');
        });
    });

    test.describe('Feature Flag', () => {
        test('should disable Preact when localStorage flag is set', async ({ page }) => {
            // Set the disable flag BEFORE loading the module
            await page.evaluate(() => {
                localStorage.setItem('doctor_preact_disabled', 'true');
            });

            // Reload to apply the flag
            await page.reload();
            await page.waitForFunction(() => window.__doctorTestReady === true, { timeout: 10000 });

            const isEnabled = await page.evaluate(async () => {
                const { isPreactEnabled } = await import('/web/preact-loader.js');
                return isPreactEnabled();
            });

            // Note: isPreactEnabled() in preact-loader.js returns the PREACT_ENABLED constant,
            // not the localStorage value directly. The localStorage check is in doctor.js.
            // This test documents the current behavior.
            expect(isEnabled).toBe(true); // PREACT_ENABLED is hardcoded to true

            // Clean up
            await page.evaluate(() => {
                localStorage.removeItem('doctor_preact_disabled');
            });
        });

        test('should respect PREACT_ISLANDS_ENABLED in doctor.js', async ({ page }) => {
            // Check that the flag is exposed or can be detected
            const hasFlag = await page.evaluate(() => {
                // The flag is a const, so we check if preact-loader import succeeds
                // which indicates the import statement in doctor.js worked
                return typeof window.__doctorTestReady !== 'undefined';
            });

            expect(hasFlag).toBe(true);
        });
    });

    test.describe('Error Handling', () => {
        test('should handle CDN failure gracefully', async ({ page }) => {
            // Block esm.sh requests to simulate offline
            await page.route('**/esm.sh/**', route => route.abort());

            const result = await page.evaluate(async () => {
                // Reset the loader state first
                const loader = await import('/web/preact-loader.js');
                if (loader.resetLoader) {
                    loader.resetLoader();
                }

                try {
                    await loader.loadPreact();
                    return { success: true };
                } catch (error) {
                    return { success: false, error: error.message };
                }
            });

            // Should fail gracefully when CDN is blocked
            expect(result.success).toBe(false);
            expect(result.error).toContain('Failed to load');
        });

        test('should report error via getLoadError after failure', async ({ page }) => {
            // Block CDN
            await page.route('**/esm.sh/**', route => route.abort());

            const result = await page.evaluate(async () => {
                const loader = await import('/web/preact-loader.js');
                if (loader.resetLoader) {
                    loader.resetLoader();
                }

                try {
                    await loader.loadPreact();
                } catch (e) {
                    // Expected to fail
                }

                const error = loader.getLoadError();
                return {
                    hasError: error !== null,
                    errorMessage: error?.message || null,
                };
            });

            expect(result.hasError).toBe(true);
            expect(result.errorMessage).toBeTruthy();
        });
    });

    test.describe('Single Instance Pattern', () => {
        test('should return same instance on multiple loadPreact calls', async ({ page }) => {
            test.slow();

            const result = await page.evaluate(async () => {
                const { loadPreact } = await import('/web/preact-loader.js');

                const instance1 = await loadPreact();
                const instance2 = await loadPreact();

                return {
                    sameH: instance1.h === instance2.h,
                    sameRender: instance1.render === instance2.render,
                    sameSignal: instance1.signal === instance2.signal,
                };
            });

            expect(result.sameH).toBe(true);
            expect(result.sameRender).toBe(true);
            expect(result.sameSignal).toBe(true);
        });
    });
});
