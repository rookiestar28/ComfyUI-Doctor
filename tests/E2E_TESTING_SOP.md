# ComfyUI-Doctor E2E 測試 SOP

> Standard Operating Procedure for E2E Testing

---

## 1. 環境需求

| 項目 | 版本 | 安裝方式 |
|------|------|----------|
| Node.js | 18+ | <https://nodejs.org> |
| Python | 3.8+ | 已安裝 |
| npm packages | - | `npm install` |
| Playwright browsers | - | `npx playwright install chromium` |

---

## 2. 快速開始

```bash
# 1. 安裝依賴
cd c:\Users\Win\Documents\我的專案\ComfyUI-Doctor
npm install
npx playwright install chromium

# 2. 執行所有測試
npm test

# 3. 互動式 UI 模式 (推薦用於開發)
npm run test:ui

# 4. 可視化模式 (看到瀏覽器操作)
npm run test:headed
```

---

## 3. 測試結構

```
tests/
├── e2e/                          # E2E 測試 (Playwright)
│   ├── specs/                    # 測試規格檔
│   │   ├── settings.spec.js      # 設定面板測試
│   │   ├── sidebar.spec.js       # 側邊欄測試
│   │   ├── statistics.spec.js    # 統計面板測試
│   │   └── preact-loader.spec.js # Preact 載入器測試 (A7)
│   ├── mocks/                    # Mock 物件
│   │   ├── comfyui-app.js        # ComfyUI app/api mock
│   │   └── ui-text.json          # i18n mock
│   ├── utils/                    # 測試工具
│   │   └── helpers.js            # 共用函數
│   ├── test-harness.html         # 測試頁面
│   └── README.md                 # 說明文件
│
├── test_*.py                     # Python 單元測試
├── conftest.py                   # pytest 設定
└── __init__.py
```

---

## 4. 常用指令

| 指令 | 用途 |
|------|------|
| `npm test` | 執行所有 E2E 測試 |
| `npm run test:ui` | Playwright UI 模式 (互動式) |
| `npm run test:headed` | 顯示瀏覽器視窗 |
| `npm run test:debug` | 進入除錯模式 |
| `npm run test:report` | 開啟上次測試報告 |
| `npx playwright test <file>` | 執行特定測試檔 |
| `npx playwright test --grep "test name"` | 執行特定測試 |

---

## 5. 撰寫新測試

### 5.1 基本範例

```javascript
// tests/e2e/specs/my-feature.spec.js
const { test, expect } = require('@playwright/test');

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/test-harness.html');
    await page.waitForFunction(() => window.__doctorTestReady === true);
  });

  test('should do something', async ({ page }) => {
    const element = page.locator('#my-element');
    await expect(element).toBeVisible();
  });
});
```

### 5.2 測試動態 import

```javascript
test('should load module', async ({ page }) => {
  const result = await page.evaluate(async () => {
    const module = await import('/web/my-module.js');
    return typeof module.myFunction === 'function';
  });
  expect(result).toBe(true);
});
```

### 5.3 模擬網路失敗

```javascript
test('should handle network failure', async ({ page }) => {
  await page.route('**/api/**', route => route.abort());
  // ... test error handling
});
```

---

## 6. 除錯技巧

### 6.1 暫停執行

```javascript
await page.pause(); // 在測試中暫停
```

### 6.2 截圖

```javascript
await page.screenshot({ path: 'debug.png' });
```

### 6.3 查看 Console 輸出

```javascript
page.on('console', msg => console.log(msg.text()));
```

### 6.4 慢動作執行

```bash
npx playwright test --headed --slow-mo=1000
```

---

## 7. CI 整合

測試會在以下情況自動執行：

- Push 到 `main` 或 `dev` 分支
- 開啟 Pull Request
- 修改 `web/` 或 `tests/e2e/` 目錄內的檔案

設定檔：`.github/workflows/playwright-tests.yml`

---

## 8. 測試 Harness 說明

`test-harness.html` 提供獨立的測試環境：

1. **Mock ComfyUI**: `window.app` 和 `window.api` 為 mock 物件
2. **載入 Doctor UI**: 動態 import `web/doctor.js`
3. **狀態指示**: `window.__doctorTestReady = true` 表示初始化完成
4. **事件通知**: `doctor-ready` 自訂事件

### 測試前提

```javascript
// 等待 Doctor UI 初始化完成
await page.waitForFunction(() => window.__doctorTestReady === true, { timeout: 10000 });
```

---

## 9. Preact Loader 測試說明

`preact-loader.spec.js` 測試項目：

| 測試類別 | 測試項目 |
|----------|----------|
| Module Loading | 模組載入成功 |
| Module Loading | isPreactEnabled 預設值 |
| Module Loading | loadPreact 返回所有 exports |
| Feature Flag | localStorage 禁用旗標 |
| Feature Flag | PREACT_ISLANDS_ENABLED |
| Error Handling | CDN 失敗處理 |
| Error Handling | getLoadError 報告錯誤 |
| Single Instance | 多次呼叫返回相同實例 |

### 執行 Preact 測試

```bash
npx playwright test tests/e2e/specs/preact-loader.spec.js
```

---

## 10. 常見問題

### Q: 測試卡住在 "Loading..."

**A**: 檢查 test-harness.html 是否正確載入 doctor.js

```bash
# 手動啟動 server 並訪問
python -m http.server 3000
# 瀏覽器開啟 http://127.0.0.1:3000/tests/e2e/test-harness.html
```

### Q: CDN 載入測試失敗

**A**: 確認網路連線正常，esm.sh CDN 可訪問

### Q: 找不到 preact-loader.js

**A**: 確認檔案在 `web/` 根目錄，不是子目錄

---

## 11. 相關文件

- [Playwright 官方文件](https://playwright.dev/)
- [tests/e2e/README.md](./e2e/README.md)
- [A7 Implementation Record](../.planning/260105-A7_IMPLEMENTATION_RECORD.md)
