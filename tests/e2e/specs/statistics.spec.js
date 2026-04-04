/**
 * Statistics Dashboard Tests (F4)
 *
 * Tests the Doctor statistics panel functionality:
 * - Statistics panel visibility and toggle
 * - Statistics data loading and display
 * - Top patterns rendering
 * - Category breakdown visualization
 * - Resolution rate display
 * - Empty state handling
 * - API error handling
 * - i18n support
 */

import { test, expect } from '@playwright/test';
import { waitForDoctorReady, waitForI18nLoaded, clearStorage } from '../utils/helpers.js';

// Mock statistics data
const MOCK_STATISTICS = {
  success: true,
  statistics: {
    total_errors: 42,
    pattern_frequency: {
      'cuda_oom_classic': 15,
      'missing_module': 10,
      'type_mismatch': 8,
      'model_not_found': 6,
      'invalid_workflow': 3
    },
    category_breakdown: {
      'memory': 20,
      'workflow': 12,
      'model_loading': 8,
      'framework': 2
    },
    top_patterns: [
      { pattern_id: 'cuda_oom_classic', count: 15, category: 'memory' },
      { pattern_id: 'missing_module', count: 10, category: 'framework' },
      { pattern_id: 'type_mismatch', count: 8, category: 'workflow' },
      { pattern_id: 'model_not_found', count: 6, category: 'model_loading' },
      { pattern_id: 'invalid_workflow', count: 3, category: 'workflow' }
    ],
    resolution_rate: {
      resolved: 20,
      unresolved: 18,
      ignored: 4
    },
    trend: {
      last_24h: 3,
      last_7d: 12,
      last_30d: 42
    }
  }
};

const EMPTY_STATISTICS = {
  success: true,
  statistics: {
    total_errors: 0,
    pattern_frequency: {},
    category_breakdown: {},
    top_patterns: [],
    resolution_rate: { resolved: 0, unresolved: 0, ignored: 0 },
    trend: { last_24h: 0, last_7d: 0, last_30d: 0 }
  }
};

// Complete UI text mock (English)
const MOCK_UI_TEXT_EN = {
  // Base UI keys
  sidebar_doctor_title: 'Doctor',
  sidebar_doctor_tooltip: 'ComfyUI Doctor - Error Diagnostics',
  info_title: 'INFO',
  info_message: 'Click 🏥 Doctor button to analyze errors',
  no_errors: 'No active errors detected.',
  system_running_smoothly: 'System running smoothly',
  no_errors_detected: 'No errors detected',
  settings_title: 'Settings',
  language_label: 'Language',
  ai_provider_label: 'AI Provider',
  base_url_label: 'Base URL',
  api_key_label: 'API Key',
  model_name_label: 'Model Name',
  save_settings_btn: 'Save Settings',
  analyze_with_ai: '✨ Analyze with AI',
  ask_ai_placeholder: 'Ask AI about this error...',
  send_btn: 'Send',
  clear_btn: 'Clear',
  // F4 Statistics keys
  statistics_title: 'Error Statistics',
  stats_total_errors: 'Total (30d)',
  stats_last_24h: 'Last 24h',
  stats_last_7d: 'Last 7d',
  stats_last_30d: 'Last 30d',
  stats_top_patterns: 'Top Error Patterns',
  stats_resolution_rate: 'Resolution Rate',
  stats_error: 'Failed to load statistics',
  stats_categories: 'Categories',
  stats_loading: 'Loading...',
  stats_no_data: 'No data yet',
  stats_resolved: 'Resolved',
  stats_unresolved: 'Unresolved',
  stats_ignored: 'Ignored',
  category_memory: 'Memory',
  category_workflow: 'Workflow',
  category_model_loading: 'Model Loading',
  category_framework: 'Framework',
  category_generic: 'Generic',
};

// Japanese UI text for i18n test
const MOCK_UI_TEXT_JA = {
  sidebar_doctor_title: 'Doctor',
  sidebar_doctor_tooltip: 'ComfyUI Doctor - エラー診断',
  info_title: '情報',
  info_message: '🏥 Doctor ボタンをクリックしてエラーを分析',
  no_errors: 'アクティブなエラーは検出されていません。',
  system_running_smoothly: 'システムは正常に動作しています',
  no_errors_detected: 'エラーは検出されませんでした',
  settings_title: '設定',
  analyze_with_ai: '✨ AIで分析',
  ask_ai_placeholder: 'AIに質問...',
  send_btn: '送信',
  clear_btn: 'クリア',
  statistics_title: 'エラー統計',
  stats_total_errors: '合計 (30日)',
  stats_last_24h: '過去24時間',
  stats_last_7d: '過去7日間',
  stats_last_30d: '過去30日間',
  stats_top_patterns: 'よくあるエラーパターン',
  stats_resolution_rate: '解決率',
  stats_error: '統計の読み込みに失敗しました',
  stats_categories: 'カテゴリ',
  stats_loading: '読み込み中...',
  stats_no_data: 'データなし',
  stats_resolved: '解決済',
  stats_unresolved: '未解決',
  stats_ignored: '無視',
  category_memory: 'メモリ',
  category_workflow: 'ワークフロー',
  category_model_loading: 'モデル読込',
  category_framework: 'フレームワーク',
  category_generic: '一般',
};

/**
 * Setup all required mocks for Doctor statistics
 * IMPORTANT: Call this BEFORE page.goto() to ensure routes intercept requests
 * When re-calling within a test (before reload), old routes are cleared first.
 */
async function setupMocks(page, options = {}) {
  // Clear any previously registered routes to avoid stacking conflicts
  await page.unrouteAll({ behavior: 'ignoreErrors' });

  const uiText = options.uiText || MOCK_UI_TEXT_EN;
  const statistics = options.statistics || MOCK_STATISTICS;

  await page.route('**/scripts/app.js', route => {
    route.fulfill({ status: 200, contentType: 'application/javascript', body: 'export const app = window.app;' });
  });

  await page.route('**/scripts/api.js', route => {
    route.fulfill({ status: 200, contentType: 'application/javascript', body: 'export const api = window.api;' });
  });

  await page.route('**/doctor/provider_defaults', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ openai: 'https://api.openai.com/v1', deepseek: 'https://api.deepseek.com/v1' }),
    });
  });

  await page.route('**/debugger/set_language', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    });
  });

  await page.route('**/doctor/ui_text*', route => {
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ language: options.language || 'en', text: uiText }) });
  });

  await page.route('**/doctor/statistics*', route => {
    if (options.statisticsError) {
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, error: 'Internal server error' }) });
    } else {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(statistics) });
    }
  });

  await page.route('**/doctor/mark_resolved', route => {
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, message: 'Status updated' }) });
  });

  // Trust & Health mocks (moved from settings.spec.js)
  await page.route('**/doctor/health', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        health: {
          logger: { dropped_messages: 2 },
          ssrf: { blocked_total: 1 },
          last_analysis: { timestamp: '2026-01-10T00:00:00Z', pipeline_status: 'ok' }
        }
      })
    });
  });

  await page.route('**/doctor/plugins', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        plugins: {
          config: { enabled: false, allowlist_count: 0, signature_required: false },
          trust_counts: { untrusted: 1 },
          plugins: [
            { file: 'example.py', plugin_id: 'example.plugin', trust: 'untrusted', reason: 'not_allowlisted' }
          ]
        }
      })
    });
  });

  // Telemetry mocks
  await page.route('**/doctor/telemetry/status', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, enabled: false, stats: { count: 5 } })
    });
  });

  await page.route('**/doctor/telemetry/toggle', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, enabled: true })
    });
  });

  await page.route('**/doctor/telemetry/buffer', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, events: [{ type: 'test', ts: '2026-01-10T00:00:00Z' }] })
    });
  });

  await page.route('**/doctor/telemetry/clear', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true })
    });
  });

  await page.route('**/doctor/telemetry/export', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ events: [] })
    });
  });
}

test.describe('Statistics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Setup all mocks using shared helper
    await setupMocks(page);

    await page.goto('test-harness.html');
    await clearStorage(page);
    // Force DoctorUI to use native fetch for UI text loading (bypassing potentially unmocked api.fetchApi)
    await page.evaluate(() => {
      if (window.api) window.api.fetchApi = undefined;
    });
    await waitForDoctorReady(page);
    await waitForI18nLoaded(page); // Wait for UI text to load
  });

  test('should display statistics tab button', async ({ page }) => {
    const tabBtn = page.locator('.doctor-tab-button[data-tab-id="stats"]');
    await expect(tabBtn).toBeVisible();
  });

  test('should show statistics content when tab clicked', async ({ page }) => {
    const tabBtn = page.locator('.doctor-tab-button[data-tab-id="stats"]');
    const statsContent = page.locator('#doctor-stats-content');

    // Initially hidden (since chat is default)
    await expect(statsContent).toBeHidden();

    // Click tab
    await tabBtn.click();
    await expect(statsContent).toBeVisible();
  });

  test('should display total errors stat card', async ({ page }) => {
    // Open panel by clicking tab
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const total = page.locator('#stats-total');
    await expect(total).toHaveText('42'); // From MOCK_STATISTICS
  });

  test('should display last 24h stat card', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const last24h = page.locator('#stats-24h');
    await expect(last24h).toHaveText('3'); // From MOCK_STATISTICS.trend.last_24h
  });

  test('should display top 5 error patterns', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const patternItems = page.locator('.pattern-item');
    await expect(patternItems).toHaveCount(5);

    const patterns = page.locator('#doctor-top-patterns');
    await expect(patterns).toContainText(/Top.*Patterns/i);
    await expect(patterns).toContainText(/CUDA OOM/i);
    await expect(patterns).toContainText(/Missing Module/i);
  });

  test('should limit top patterns to 5 items', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const patternItems = page.locator('.pattern-item');
    await expect(patternItems).toHaveCount(5); // Our mock has exactly 5
  });

  test('should display pattern counts', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const patternItems = page.locator('.pattern-item');
    await expect(patternItems).toHaveCount(5);

    const counts = page.locator('.pattern-count');
    await expect(counts.nth(0)).toHaveText('15'); // cuda_oom_classic count
    await expect(counts.nth(1)).toHaveText('10'); // missing_module count
  });

  test('should display category breakdown section', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const categoryBars = page.locator('.category-bar');
    await expect(categoryBars).toHaveCount(4);

    const categories = page.locator('#doctor-category-breakdown');
    await expect(categories).toContainText('Categories');
    await expect(categories).toContainText(/Memory/i);
    await expect(categories).toContainText('Workflow');
  });

  test('should display category progress bars', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const categoryBars = page.locator('.category-bar');
    await expect(categoryBars).toHaveCount(4);
  });

  test('should handle empty statistics gracefully', async ({ page }) => {
    // Setup mocks with empty statistics before reload
    await setupMocks(page, { statistics: EMPTY_STATISTICS });

    // Reload to apply new mocks
    await page.reload();
    await waitForDoctorReady(page);

    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    const statsContent = page.locator('#doctor-stats-content');
    // Should show "No data yet" message after async load completes
    await expect(statsContent).toContainText('No data yet');
  });

  test('should handle API error gracefully', async ({ page }) => {
    // Setup mocks with statistics error before reload
    await setupMocks(page, { statisticsError: true });

    // Reload to apply new mocks
    await page.reload();
    await waitForDoctorReady(page);

    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    // Should still render without crashing
    const statsContent = page.locator('#doctor-stats-content');
    await expect(statsContent).toBeVisible();

    // Should show error message after async load completes
    await expect(statsContent).toContainText(/0|No data|Failed|Error|Missing/i);
  });

  test('should persist active stats tab', async ({ page }) => {
    // Click stats tab
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await expect(page.locator('#doctor-stats-content')).toBeVisible();

    // Reload page
    await page.reload();
    await waitForDoctorReady(page);

    // Check localStorage was set
    const storedState = await page.evaluate(() => {
      return localStorage.getItem('doctor_active_tab');
    });
    expect(storedState).toBe('stats');

    // Check if it restored the active tab (content visible)
    await expect(page.locator('#doctor-stats-content')).toBeVisible();
  });

  test('should support i18n (multilingual UI)', async ({ page }) => {
    // Setup mocks with Japanese UI text before reload
    await setupMocks(page, { uiText: MOCK_UI_TEXT_JA, language: 'ja' });

    // Reload with Japanese text
    await page.reload();
    await page.evaluate(() => { if (window.api) window.api.fetchApi = undefined; });
    await waitForDoctorReady(page);

    // We can't check title of tab bar without waiting for render?
    // But statistics title might only render when tab is active?
    // Wait, the test checked summary text.
    // Now we check tab content.
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    // Check the full stats panel which contains the summary with the title
    const statsPanel = page.locator('#doctor-statistics-panel');
    const text = await statsPanel.textContent();

    // Should display Japanese text from MOCK_UI_TEXT_JA.statistics_title
    // The title is in the <summary> element inside #doctor-statistics-panel
    expect(text).toContain('エラー統計');
  });

  test('should format pattern names correctly', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const patternItems = page.locator('.pattern-item');
    await expect(patternItems).toHaveCount(5);

    const patternNames = page.locator('.pattern-name');
    const text = await patternNames.allTextContents();

    expect(text.join(' ')).toMatch(/CUDA/);
    expect(text.join(' ')).toMatch(/OOM/);
    expect(text.join(' ')).not.toMatch(/cuda_oom_classic/);
  });

  test('should calculate category percentages', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    // Memory: 20/42 = 47.6%
    const categoryBars = page.locator('.category-bar .bar-fill');
    const firstBarWidth = await categoryBars.first().evaluate(el => el.style.width);

    // Should have a percentage width
    expect(firstBarWidth).toMatch(/%/);
  });

  test('should display resolution rate statistics', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    const resolved = page.locator('#stats-resolved-count');
    const unresolved = page.locator('#stats-unresolved-count');
    const ignored = page.locator('#stats-ignored-count');

    await expect(resolved).toHaveText('20');
    await expect(unresolved).toHaveText('18');
    await expect(ignored).toHaveText('4');
  });

  // F15: Resolution Marking UI Tests
  test('should display resolution action buttons', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    const actionsSection = page.locator('#resolution-actions');
    await expect(actionsSection).toBeVisible();

    const resolvedBtn = page.locator('#btn-mark-resolved');
    const unresolvedBtn = page.locator('#btn-mark-unresolved');
    const ignoredBtn = page.locator('#btn-mark-ignored');

    await expect(resolvedBtn).toBeVisible();
    await expect(unresolvedBtn).toBeVisible();
    await expect(ignoredBtn).toBeVisible();
  });

  test('should disable resolution buttons when no error timestamp', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    // Without a workflow context / timestamp, buttons should be disabled
    const resolvedBtn = page.locator('#btn-mark-resolved');
    await expect(resolvedBtn).toBeDisabled();

    // Should show "No error to mark" hint
    const hint = page.locator('#resolution-actions');
    await expect(hint).toContainText('No error to mark');
  });

  test('should call mark_resolved API when button clicked', async ({ page }) => {
    // Setup API interception BEFORE navigation
    let apiCalled = false;
    let requestBody = null;

    await page.route('**/doctor/mark_resolved', async route => {
      apiCalled = true;
      requestBody = JSON.parse(route.request().postData());
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Status updated' })
      });
    });

    // Navigate to stats tab
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(300);

    // Inject mock workflow context with timestamp via DoctorUI handler
    await page.evaluate(() => {
      const doctor = window.app?.Doctor;
      if (!doctor || typeof doctor.handleNewError !== 'function') {
        throw new Error('Doctor UI not ready for error injection');
      }

      doctor.handleNewError({
        last_error: 'Mock Error',
        timestamp: '2026-01-08T12:00:00Z',
        resolution_status: 'unresolved'
      });
    });

    // Some modes auto-switch tabs on new errors; ensure we stay on Stats.
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(200);

    // Wait for component to poll and pick up the new context (poll interval is 2s)
    await page.waitForTimeout(2500);

    // Now the button should be enabled - click it
    const resolvedBtn = page.locator('#btn-mark-resolved');
    await expect(resolvedBtn).toBeEnabled();
    await expect(resolvedBtn).toBeVisible();
    await resolvedBtn.click();
    await page.waitForTimeout(500);

    // Assert API was called
    expect(apiCalled).toBe(true);
    expect(requestBody).toEqual({
      timestamp: '2026-01-08T12:00:00Z',
      status: 'resolved'
    });
  });

  // F16: Quick Community Feedback (GitHub PR)
  test('should preview and submit quick community feedback from statistics tab', async ({ page }) => {
    let previewCalled = false;
    let submitCalled = false;
    let previewBody = null;
    let submitBody = null;

    await page.route('**/doctor/feedback/preview', async route => {
      previewCalled = true;
      previewBody = JSON.parse(route.request().postData() || '{}');
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          submission_id: '20260226_123456_deadbeef00',
          include_stats: true,
          files: {
            submission: 'feedback/submissions/20260226/20260226_123456_deadbeef00.json',
            stats: 'feedback/stats/20260226/20260226_123456_deadbeef00.json'
          },
          warnings: [],
          github: { ready: true, repo: 'rookiestar28/ComfyUI-Doctor' },
          preview: {
            schema_version: '1.0',
            pattern_candidate: {
              id: 'community_user_feedback',
              regex: 'RuntimeError',
              category: 'generic',
              priority: 60
            },
            suggestion_candidate: { language: 'en', message: 'Test suggestion' },
            context: { error_summary: 'RuntimeError: mock' }
          }
        })
      });
    });

    await page.route('**/doctor/feedback/submit', async route => {
      submitCalled = true;
      submitBody = JSON.parse(route.request().postData() || '{}');
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          submission_id: '20260226_123456_deadbeef00',
          files: {
            submission: 'feedback/submissions/20260226/20260226_123456_deadbeef00.json',
            stats: 'feedback/stats/20260226/20260226_123456_deadbeef00.json'
          },
          preview: {
            schema_version: '1.0',
            pattern_candidate: { id: 'community_user_feedback' }
          },
          warnings: [],
          github: {
            ready: true,
            repo: 'rookiestar28/ComfyUI-Doctor',
            branch: 'feedback/20260226/20260226_123456_deadbeef00',
            pr_number: 123,
            pr_url: 'https://github.com/rookiestar28/ComfyUI-Doctor/pull/123'
          }
        })
      });
    });

    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(250);

    // Seed latest error context for autofill payload
    await page.evaluate(() => {
      const doctor = window.app?.Doctor;
      doctor?.handleNewError?.({
        last_error: 'RuntimeError: mock tensor mismatch',
        error_summary: 'RuntimeError: mock',
        suggestion: 'Test suggestion',
        timestamp: '2026-02-26T12:00:00Z',
        node_context: { node_id: '12', node_name: 'KSampler' }
      });
    });

    const feedbackPanel = page.locator('#doctor-feedback-panel');
    await feedbackPanel.locator('summary').click();
    await expect(feedbackPanel).toBeVisible();

    await page.fill('#doctor-feedback-suggestion', 'Test suggestion');

    await page.click('#doctor-feedback-preview-btn');
    await expect.poll(() => previewCalled, { timeout: 3000 }).toBe(true);

    expect(previewBody.pattern_candidate.id).toBeTruthy();
    expect(previewBody.suggestion_candidate.message).toBe('Test suggestion');
    await expect(page.locator('#doctor-feedback-preview-output')).toContainText('schema_version');

    await page.click('#doctor-feedback-submit-btn');
    await expect.poll(() => submitCalled, { timeout: 3000 }).toBe(true);

    expect(submitBody.pattern_candidate).toBeTruthy();
    await expect(page.locator('#doctor-feedback-status')).toContainText('GitHub PR created');
    await expect(page.locator('#doctor-feedback-status a')).toHaveAttribute('href', /pull\/123$/);
  });

  test('should show validation error for invalid quick community feedback preview', async ({ page }) => {
    await page.route('**/doctor/feedback/preview', async route => {
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: 'Invalid regex',
          field_errors: { 'pattern_candidate.regex': 'missing or invalid' }
        })
      });
    });

    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(250);

    const feedbackPanel = page.locator('#doctor-feedback-panel');
    await feedbackPanel.locator('summary').click();

    await page.fill('#doctor-feedback-pattern-regex', '');
    await page.fill('#doctor-feedback-suggestion', 'test');

    await page.click('#doctor-feedback-preview-btn');
    await page.waitForTimeout(200);

    await expect(page.locator('#doctor-feedback-status')).toContainText('Invalid regex');
    await expect(page.locator('#doctor-feedback-preview-output')).toContainText('pattern_candidate.regex');
  });

  // ════════════════════════════════════════════════════════════════════════
  // Trust & Health Tests (Moved from Settings tab - 260115 Plan)
  // ════════════════════════════════════════════════════════════════════════

  test('should display Trust & Health panel in Statistics tab', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    const trustHealthPanel = page.locator('#doctor-trust-health-panel');
    await expect(trustHealthPanel).toBeVisible();
    await expect(trustHealthPanel).toContainText('Trust');
  });

  test('should load health and plugin trust report on refresh', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');

    const refreshBtn = page.locator('#doctor-trust-health-refresh-btn');
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    await page.waitForTimeout(300);

    await expect(page.locator('#doctor-health-output')).toContainText('pipeline_status=ok');
    await expect(page.locator('#doctor-health-output')).toContainText('ssrf_blocked=1');
    await expect(page.locator('#doctor-health-output')).toContainText('dropped_logs=2');

    await expect(page.locator('#doctor-plugins-output')).toContainText('example.plugin');
    await expect(page.locator('#doctor-plugins-output')).toContainText('untrusted');
  });

  // ════════════════════════════════════════════════════════════════════════
  // Telemetry Tests (Moved from Settings tab - 260115 Plan)
  // ════════════════════════════════════════════════════════════════════════

  test('should display Telemetry panel in Statistics tab', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    const telemetryPanel = page.locator('#doctor-telemetry-panel');
    await expect(telemetryPanel).toBeVisible();
    await expect(telemetryPanel).toContainText('Telemetry');
  });

  test('should display telemetry toggle and buttons', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(200);

    const viewBtn = page.locator('#doctor-telemetry-view-btn');
    const clearBtn = page.locator('#doctor-telemetry-clear-btn');
    const exportBtn = page.locator('#doctor-telemetry-export-btn');

    await expect(viewBtn).toBeVisible();
    await expect(clearBtn).toBeVisible();
    await expect(exportBtn).toBeVisible();
  });

  test('should show telemetry buffer count', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(300);

    // Mock returns count: 5
    const statsText = page.locator('#doctor-telemetry-stats');
    await expect(statsText).toContainText(/5|buffered/i);
  });

  // ════════════════════════════════════════════════════════════════════════
  // R16: Statistics Reset Tests
  // ════════════════════════════════════════════════════════════════════════

  test('should display reset button in statistics panel', async ({ page }) => {
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(100);

    const resetBtn = page.locator('#doctor-stats-reset-btn');
    await expect(resetBtn).toBeVisible();
  });

  test('should call reset API and show empty state after confirmation', async ({ page }) => {
    let resetApiCalled = false;
    let statsReturnEmpty = false;

    // Remove default handler so this test can deterministically control responses.
    await page.unroute('**/doctor/statistics*').catch(() => { });

    // Override routes to track reset API and return empty stats after reset
    await page.route('**/doctor/statistics/reset', async route => {
      resetApiCalled = true;
      statsReturnEmpty = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Statistics reset successfully' })
      });
    });

    await page.route('**/doctor/statistics?*', async route => {
      // Stats requests may happen multiple times on initial mount/activation.
      // Only switch to EMPTY_STATISTICS after the reset endpoint is called.
      const stats = statsReturnEmpty ? EMPTY_STATISTICS : MOCK_STATISTICS;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(stats)
      });
    });

    // Navigate to stats tab
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(200);

    // Verify initial stats are shown
    const total = page.locator('#stats-total');
    await expect(total).toHaveText('42');

    // Mock window.confirm to auto-accept
    await page.evaluate(() => {
      window.confirm = () => true;
    });

    // Click reset button
    const resetBtn = page.locator('#doctor-stats-reset-btn');
    await resetBtn.click();
    await expect.poll(() => resetApiCalled, { timeout: 3000 }).toBe(true);

    // Verify API was called

    // Verify stats refreshed to show empty/0 state
    await expect(total).toHaveText('0');
  });

  test('should not call reset API when confirmation is cancelled', async ({ page }) => {
    let resetApiCalled = false;

    await page.route('**/doctor/statistics/reset', async route => {
      resetApiCalled = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });

    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(200);

    // Mock window.confirm to cancel
    await page.evaluate(() => {
      window.confirm = () => false;
    });

    const resetBtn = page.locator('#doctor-stats-reset-btn');
    await resetBtn.click();
    await page.waitForTimeout(200);

    // API should NOT be called
    expect(resetApiCalled).toBe(false);
  });

  // ════════════════════════════════════════════════════════════════════════
  // F14: Diagnostics UX Tests (P3)
  // ════════════════════════════════════════════════════════════════════════

  test('should display multi-intent banner with stage badges', async ({ page }) => {
    // Mock the report response with multiple intents
    const multiIntentReport = {
      success: true,
      report: {
        timestamp: Date.now(),
        health_score: 95,
        duration_ms: 120,
        issues: [],
        intent_signature: {
          top_intents: [
            {
              intent_id: 'txt2img',
              confidence: 0.9,
              stage: 'generation',
              evidence: [
                { explain: 'Ksampler found', signal_id: 'node.KSampler' },
                { explain: 'SaveImage found', signal_id: 'node.SaveImage' },
                { explain: 'CLIPTextEncode found', signal_id: 'node.CLIPText' }
              ]
            },
            {
              intent_id: 'img2img',
              confidence: 0.4,
              stage: 'generation',
              evidence: [
                { explain: 'LoadImage found', signal_id: 'node.LoadImage' }
              ]
            }
          ]
        }
      }
    };

    // Override route for this specific test
    await page.route('**/doctor/health_report', route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(multiIntentReport) });
    });

    // Reload to trigger mount fetch in DiagnosticsSection
    await page.reload();
    await waitForDoctorReady(page);
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(500); // Wait for render

    // Assert Banner
    const banner = page.locator('#diagnostics-intent-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Likely intents');

    // Check Primary Intent (txt2img -> "Text to Image" in mock ui-text)
    await expect(banner).toContainText('Text to Image');
    await expect(banner).toContainText('90%');
    await expect(banner).toContainText('Generation'); // Stage localization

    // Check Secondary Intent
    await expect(banner).toContainText('Image to Image');

    // Check Evidence Expansion
    // Mock has 3 items for txt2img. Default view usually shows 2.
    // "Show more" should be visible.
    const toggle = banner.getByText('Show more').first();
    await expect(toggle).toBeVisible();

    // Click toggle
    await toggle.click();

    // Expect text to change to "Show less" (using regex for flexibility)
    await expect(banner).toContainText(/Show less/i);
  });

  test('should render no-intent message when intent signature exists but no top intents', async ({ page }) => {
    // Mock report with empty top_intents
    const noIntentReport = {
      success: true,
      report: {
        timestamp: Date.now(),
        health_score: 100,
        intent_signature: {
          top_intents: [] // Empty list
        }
      }
    };

    await page.route('**/doctor/health_report', route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(noIntentReport) });
    });

    await page.reload();
    await waitForDoctorReady(page);
    await page.click('.doctor-tab-button[data-tab-id="stats"]');
    await page.waitForTimeout(500);

    // Banner should still be visible (fallback mode)
    const banner = page.locator('#diagnostics-intent-banner');
    await expect(banner).toBeVisible();

    // Should contain the fallback text
    // "No dominant intent detected" is the default or mocked en value
    await expect(banner).toContainText(/No dominant intent detected/i);
  });

});
