/**
 * Mock ComfyUI app.js for testing
 *
 * This file mocks the ComfyUI app module that doctor_ui.js tries to import.
 * It re-exports the mock app object that was set up by the test harness.
 */

// The test harness creates window.app before loading doctor_ui.js
// We simply re-export it here so the ES module import works
export const app = window.app;
