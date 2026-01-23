# ComfyUI-Doctor

繁體中文 | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [專案進度與開發藍圖](../ROADMAP.md)

這是一個 ComfyUI 專用的全時即時執行階段診斷套件。能自動攔截自啟動後的所有終端機輸出，捕捉完整的 Python 追蹤回溯 (Tracebacks)，並透過節點層級 (Node-level) 的上下文提取，提供具優先順序的修復建議。內建 57+ 種錯誤模式（22 個內建 + 35 個社群模式）、採用 JSON 熱重載模式，讓使用者自行維護管理其他 Error 類型；目前已支援 9 種語言、具備日誌持久化功能，並提供便於前端整合的 RESTful API。

## 最新更新 (2026 年 1 月) - 點擊展開

<details>
<summary><strong>(v1.5.8) 品質改善: 自動開啟右側錯誤報告面板開關</strong></summary>

- 在 **Doctor → Settings** 中新增了一個**專用開關**，用於控制當偵測到新錯誤時，**右側錯誤報告面板**是否自動開啟。
- **預設值: 開啟 (ON)**（針對新安裝），且使用者的選擇會被保留。

</details>

<details>
<summary><strong>Smart Token 預算管理 (v1.5.0)</strong></summary>

**智慧上下文管理 (成本優化):**

- **自動修剪**：針對雲端 LLM 自動縮減上下文 (減少 60-80% Token 用量)
- **漸進式策略**：工作流修剪 → 移除系統資訊 → 截斷 Traceback
- **本地模式選項**：針對 Ollama/LMStudio 的溫和修剪 (12K/16K 限制)
- **增強可觀測性**：逐步 Token 追蹤 & A/B 驗證工具

**網路韌性:**

- **指數退避重試**：自動重試 429/5xx 錯誤 (含抖動機制)
- **串流保護**：30秒逾時監控，防止 SSE 串流卡住
- **速率與並發限制**：令牌桶 (30次/分) + 並發信號量 (最大 3)

**新配置:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | 啟用智慧預算 (遠端) |
| `retry_max_attempts` | `3` | 最大重試次數 |
| `stream_chunk_timeout` | `30` | 串流逾時 (秒) |

</details>

<details>
<summary><strong>重大修復: 管道治理與插件安全性 (v1.4.5)</strong></summary>

**安全性強化:**

- **SSRF 防護升級**: 將子字串檢查替換為 Host/Port 解析；阻擋外送請求的重新導向 (`allow_redirects=False`)
- **外送資料淨化漏斗**: 單一邊界 (`outbound.py`) 確保所有外部 payload 皆經過淨化；僅已驗證的本地 LLM 允許使用 `privacy_mode=none`

**插件信任系統:**

- **預設安全**: 插件預設停用，需要明確的允許清單 (Allowlist) + 資訊清單 (Manifest) / SHA256 雜湊
- **信任分類**: `trusted` (受信任) | `unsigned` (未簽署) | `untrusted` (不受信任) | `blocked` (已封鎖)
- **檔案系統強化**: 真實路徑限制 (realpath containment)、符號連結 (symlink) 拒絕、檔案大小限制、嚴格的檔名規則
- **可選 HMAC 簽章**: 共用密鑰完整性驗證 (非公開金鑰簽署)

**管道治理:**

- **元資料契約**: Schema 版本控制 + 執行結束後驗證 + 無效鍵值隔離區 (Quarantine)
- **相依性策略**: `requires/provides` 強制執行；缺少依賴 → 跳過階段，狀態設為 `degraded` (降級)
- **Logger 背壓**: 具備優先級感知的 `DroppingQueue` + 丟棄指標 (drop metrics)
- **啟動前交接**: 在 SmartLogger 接管前執行乾淨的 Logger 解除安裝

**可觀測性:**

- `/doctor/health` 端點提供佇列指標、丟棄計數、SSRF 阻擋數、管道狀態

**測試結果**: 通過 159 個 Python 測試 | 17 個 Phase 2 閘道測試

</details>

<details>
<summary><strong>增強功能: CI 閘道與插件工具</strong></summary>

**T11 - Phase 2 發布 CI 閘道:**

- GitHub Actions 工作流程 (`phase2-release-gate.yml`) 強制執行 4 個 pytest 套件 + E2E 測試
- 本地驗證腳本 (`scripts/phase2_gate.py`) 支援 `--fast` 和 `--e2e` 模式

**T12 - 外送安全性靜態檢查器:**

- 基於 AST 的分析器 (`scripts/check_outbound_safety.py`) 偵測繞過模式
- 6 條偵測規則: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION` 等
- CI 工作流程 + 8 個單元測試 + 文件 (`docs/OUTBOUND_SAFETY.md`)

**A8 - 插件遷移工具:**

- `scripts/plugin_manifest.py`: 生成帶有 SHA256 雜湊的資訊清單
- `scripts/plugin_allowlist.py`: 掃描插件並建議配置
- `scripts/plugin_validator.py`: 驗證資訊清單和配置
- `scripts/plugin_hmac_sign.py`: 可選的 HMAC 簽章生成
- 文件更新: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

<details>
<summary><strong>增強功能: S1/S3 - CSP 文件與遙測</strong></summary>

**S1 - CSP 合規性文件:**

- 驗證所有資產皆為本地載入 (`web/lib/`)；CDN URL 僅作為備援
- 在 README 新增 "CSP Compatibility" 章節
- 程式碼審計完成 (手動驗證待處理)

**S3 - 本地遙測基礎建設:**

- 後端: `telemetry.py` 包含 TelemetryStore, RateLimiter, PII 偵測
- 6 個 API 端點: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- 前端: 設定用於遙測管理的 UI 控制項
- 安全性: 來源檢查 (403 跨來源), 1KB payload 限制, 欄位白名單
- **預設關閉**: 除非明確啟用，否則不記錄/不連網
- 81 個 i18n 字串 (9 keys × 9 languages)

**測試結果**: 27 個遙測單元測試 | 8 個 E2E 測試

</details>

<details>
<summary><strong>增強功能: E2E 執行器強化與信任/健康 UI</strong></summary>

**E2E 執行器強化 (WSL `/mnt/c` 支援):**

- 修復 WSL 上的 Playwright轉換快取權限問題
- 在 repo 下新增可寫入的暫存目錄 (`.tmp/playwright`)
- `PW_PYTHON` 覆蓋以支援跨平台相容性

**信任與健康 UI 面板:**

- 在統計 (Statistics) 分頁新增 "Trust & Health" 面板
- 顯示: pipeline_status, ssrf_blocked, dropped_logs
- 插件信任列表 (附帶徽章和原因)
- `GET /doctor/plugins` 僅掃描端點 (不匯入程式碼)

**測試結果**: 通過 61/61 個 E2E 測試 | 159/159 個 Python 測試

</details>

<details>
<summary><strong>先前更新 (v1.4.0, Jan 2026)</strong></summary>

- A7 Preact 遷移完成，涵蓋 Phase 5A–5C (Chat/Stats islands, registry, shared rendering, robust fallbacks)。
- 整合強化: 加強 Playwright E2E 覆蓋率。
- UI 修復: 側邊欄工具提示時序問題。

</details>

<details>
<summary><strong>統計儀表板</strong></summary>

**一目了然地追蹤 ComfyUI 穩定性！**

ComfyUI-Doctor 現已包含**統計儀表板**，提供錯誤趨勢、常見問題及解決進度的深入分析。

**功能特色**：

- 📊 **錯誤趨勢**：追蹤 24小時/7天/30天 內的錯誤數據
- 🔥 **Top 5 模式**：查看最常發生的錯誤類型
- 📈 **分類細項**：依類別視覺化錯誤（記憶體、工作流、模型載入等）
- ✅ **解決追蹤**：監控已解決與未解決的錯誤
- 🌍 **完整 i18n 支援**：支援所有 9 種語言

![統計儀表板](../../assets/statistics_panel.png)

**使用方法**：

1. 打開 Doctor 側邊欄面板（點擊左側 🏥 圖示）
2. 展開 "📊 錯誤統計" 區塊
3. 查看即時錯誤分析與趨勢
4. 將錯誤標記為已解決/忽略以追蹤進度

**後端 API**：

- `GET /doctor/statistics?time_range_days=30` - 取得統計數據
- `POST /doctor/mark_resolved` - 更新解決狀態

**測試覆蓋率**：17/17 後端測試 ✅ | 14/18 E2E 測試 (78% 通過率)

**實作細節**：請參閱 `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

<details>
<summary><strong>模式驗證 CI</strong></summary>

**自動化品質檢查現在守護模式完整性！**

ComfyUI-Doctor 現已包含針對所有錯誤模式的**持續整合測試**，確保零瑕疵的代碼貢獻。

**T8 驗證項目**：

- ✅ **JSON 格式**：所有 8 個模式檔案皆正確編譯
- ✅ **Regex 語法**：所有 57 個模式皆有有效的正規表達式
- ✅ **i18n 完整性**：100% 翻譯覆蓋率（57 模式 × 9 語言 = 513 項檢查）
- ✅ **Schema 合規**：必要欄位 (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Metadata 品質**：有效優先級範圍 (50-95)、唯一 ID、正確分類

**GitHub Actions 整合**：

- 針對影響 `patterns/`、`i18n.py` 或測試的每次 push/PR 觸發
- 執行約需 3 秒，花費 $0（GitHub Actions 免費額度）
- 若驗證失敗則阻擋合併

**給貢獻者**：

```bash
# 提交前的本地驗證
python scripts/run_pattern_tests.py

# 輸出:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (共 9 種語言)
```

**測試結果**：所有檢查 100% 通過率

**實作細節**：請參閱 `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

<details>
<summary><strong>模式系統全面升級（階段 1-3 完成）</strong></summary>

ComfyUI-Doctor 完成重大架構升級，具備 **57+ 錯誤模式**與 **JSON 熱重載模式管理**！

**階段 1：Logger 架構修復**

- 實作 SafeStreamWrapper 與 queue-based 背景處理
- 消除 deadlock 風險與 race condition
- 修復與 ComfyUI LogInterceptor 的衝突問題

**階段 2：JSON 模式管理（F2）**

- 全新 PatternLoader 支援熱重載（無需重啟！）
- 模式定義於 `patterns/` 目錄下的 JSON 檔案
- 22 個內建模式位於 `patterns/builtin/core.json`
- 易於擴展與維護

**階段 3：社群模式擴充（F12）**

- **35 個全新社群模式**，涵蓋熱門擴充功能：

  - **ControlNet**（8 個模式）：模型載入、前處理、圖像尺寸
  - **LoRA**（6 個模式）：載入錯誤、相容性、權重問題
  - **VAE**（5 個模式）：編碼/解碼失敗、精度、拼接
  - **AnimateDiff**（4 個模式）：模型載入、幀數、上下文長度
  - **IPAdapter**（4 個模式）：模型載入、圖像編碼、相容性
  - **FaceRestore**（3 個模式）：CodeFormer/GFPGAN 模型、偵測
  - **雜項**（5 個模式）：Checkpoint、取樣器、調度器、CLIP
- 完整 i18n 支援：英文、繁體中文、簡體中文
- 總計：**57 個錯誤模式**（22 個內建 + 35 個社群）

**優勢**：

- ✅ 更全面的錯誤覆蓋率
- ✅ 熱重載模式，無需重啟 ComfyUI
- ✅ 社群可透過 JSON 檔案貢獻模式
- ✅ 更簡潔、易維護的程式碼庫

</details>

<details>
<summary><strong>先前更新（2025 年 12 月）</strong></summary>

### 多語系支援擴展

已將語系支援從 4 種擴展至 9 種！ComfyUI-Doctor 現在能以以下語言提供錯誤建議：

- **English** 英文 (en)
- **繁體中文** (zh_TW)
- **简体中文** 簡體中文 (zh_CN)
- **日本語** 日文 (ja)
- **🆕 Deutsch** 德文 (de)
- **🆕 Français** 法文 (fr)
- **🆕 Italiano** 義大利文 (it)
- **🆕 Español** 西班牙文 (es)
- **🆕 한국어** 韓文 (ko)

所有 57 種錯誤模式已完整翻譯至所有語言，確保一致的診斷品質。

### 側邊欄設定整合

設定已簡化！直接從側邊欄配置 Doctor：

- 點擊側邊欄標題的 ⚙️ 圖示即可存取所有設定
- 語言選擇（9 種語言）
- AI 提供商快速切換（OpenAI、DeepSeek、Groq、Gemini、Ollama 等）
- 更換提供商時自動填入 Base URL
- API 金鑰管理（密碼保護輸入）
- 模型名稱配置
- 設定透過 localStorage 跨工作階段保存
- 儲存時視覺回饋（✅ 已儲存！/ ❌ 錯誤）

ComfyUI 設定面板現在僅顯示啟用/停用切換 - 所有其他設定已移至側邊欄，提供更簡潔、更整合的體驗。

</details>

---

## 功能特色

- **自動錯誤監控**：即時攔截所有終端機輸出並偵測 Python Traceback
- **智慧錯誤分析**：內建 57+ 種錯誤模式（22 個內建 + 35 個社群模式），提供可行的修復建議
- **節點上下文提取**：自動識別發生錯誤的節點（節點 ID、名稱、類別）
- **系統環境上下文**：AI 分析時自動包含 Python 版本、已安裝套件（pip list）與作業系統資訊
- **多語系支援**：支援 9 種語言（英文、繁體中文、簡體中文、日文、德文、法文、義大利文、西班牙文、韓文）
- **JSON 模式管理**：熱重載錯誤模式，無需重啟 ComfyUI
- **社群模式支援**：涵蓋 ControlNet、LoRA、VAE、AnimateDiff、IPAdapter、FaceRestore 等
- **除錯節點**：深度檢查工作流中的數據流動 (Tensor 形狀、數值統計等)
- **錯誤歷史記錄**：透過 API 保留最近的錯誤緩衝區
- **RESTful API**：提供七個端點供前端整合使用
- **AI 智能分析**：一鍵呼叫 LLM 進行錯誤分析，支援 8+ 種 AI 提供商（OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等）
- **互動式對話介面**：整合於 ComfyUI 側邊欄的多輪 AI 除錯助手
- **互動式側邊欄介面**：視覺化錯誤面板，可定位節點並即時診斷
- **靈活配置**：完整的設定面板，自訂各項行為

### 🆕 AI 對話介面

全新的互動式對話介面提供直接整合於 ComfyUI 左側邊欄的對話式除錯體驗。當錯誤發生時，只需點擊「Analyze with AI」即可開始與您偏好的 LLM 進行多輪對話。

<div align="center">
<img src="../../assets/chat-ui.png" alt="AI Chat Interface">
</div>

**核心特色：**

- **情境感知**：自動包含錯誤詳情、節點資訊與工作流程上下文
- **環境感知**：包含 Python 版本、已安裝套件與作業系統資訊以提升偵錯準確度
- **串流回應**：即時顯示 LLM 回應，並正確格式化
- **多輪對話**：提出後續問題以深入探討問題
- **永遠可見**：輸入區域固定於底部，使用黏性定位保持可見
- **支援 8+ 種 LLM 提供商**：OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等
- **智慧快取**：套件列表快取 24 小時，避免效能影響

**使用方式：**

1. 當錯誤發生時，打開 Doctor 側邊欄（左側面板）
2. 點擊錯誤上下文區域中的「✨ Analyze with AI」按鈕
3. AI 會自動分析錯誤並提供建議
4. 在輸入框中輸入後續問題以繼續對話
5. 按 Enter 或點擊「Send」按鈕送出訊息

> **💡 免費 API 提示**：[Google AI Studio](https://aistudio.google.com/app/apikey)（Gemini）提供豐富的免費額度，無需信用卡即可使用。非常適合零成本開始使用 AI 智能除錯功能！

---

## 安裝

### 方式一：使用 ComfyUI-Manager（推薦）

1. 開啟 ComfyUI，點擊選單中的 **Manager** 按鈕
2. 選擇 **Install Custom Nodes**
3. 搜尋 `ComfyUI-Doctor`
4. 點擊 **Install** 並重新啟動 ComfyUI

### 方式二：手動安裝（Git Clone）

1. 進入 ComfyUI 的自訂節點目錄：

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. 下載此專案：

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. 重新啟動 ComfyUI

4. 在終端機查看初始化訊息確認安裝成功：

   ```text
   [ComfyUI-Doctor] Initializing Smart Debugger...
   [ComfyUI-Doctor] Log file: .../logs/comfyui_debug_2025-12-28.log
   
   ==================== SYSTEM SNAPSHOT ====================
   OS: Windows 11
   Python: 3.12.3
   PyTorch: 2.0.1+cu118
   CUDA Available: True
   ...
   ```

## 使用方式

### 被動模式（自動監控）

安裝後無需任何操作，ComfyUI-Doctor 會自動：

- 記錄所有日誌至 `logs/` 目錄
- 偵測錯誤並提供建議
- 記錄系統環境資訊

**錯誤輸出範例**：

```text
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM（記憶體不足）：GPU VRAM 已滿。建議：
   1. 減少 Batch Size
   2. 使用 '--lowvram' 參數
   3. 關閉其他 GPU 程式
----------------------------------------
```

### 主動模式（除錯節點）

1. 在畫布上右鍵點選：`Add Node` → `Smart Debug Node`
2. 將節點串接在任何連線中（支援萬用輸入 `*`）
3. 執行工作流

**輸出範例**：

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

此節點會透傳數據，不會影響工作流執行。

---

## 前端介面

ComfyUI-Doctor 提供互動式側邊欄介面，用於即時錯誤監控和診斷。

### 開啟 Doctor 面板

點擊 ComfyUI 選單（左側邊欄）中的 **🏥 Doctor** 按鈕即可開啟 Doctor 面板。面板會從畫面右側滑入。

### 介面功能

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Error Report">
</div>

Doctor 介面由兩個面板組成：

#### 左側邊欄面板（Doctor 側邊欄）

點擊 ComfyUI 左側選單中的 **🏥 Doctor** 圖示即可存取：

- **設定面板**（⚙️ 圖示）：配置語言、AI 提供商、API 金鑰和模型選擇
- **錯誤上下文卡片**：當錯誤發生時顯示：
  - **💡 建議**：簡潔、可操作的建議（例如「請檢查輸入連接並確保符合節點要求。」）
  - **時間戳記**：錯誤發生時間
  - **節點上下文**：節點 ID 和名稱（如適用）
  - **✨ 使用 AI 分析**：啟動互動式聊天進行詳細除錯
- **AI 聊天介面**：與您的 LLM 進行多輪對話以深入分析錯誤
- **固定輸入區域**：始終顯示在底部，方便提出後續問題

#### 右側錯誤面板（最新診斷）

右上角的即時錯誤通知：

![Doctor Error Report](../../assets/error-report.png)

- **狀態指示燈**：顯示系統健康狀態的彩色圓點
  - 🟢 **綠色**：系統正常運作，未偵測到錯誤
  - 🔴 **紅色（閃爍）**：偵測到活動錯誤
- **最新診斷卡片**：顯示最近的錯誤資訊，包含：
  - **錯誤摘要**：簡短的錯誤描述（紅色主題，長錯誤可摺疊）
  - **💡 建議**：簡潔的可操作建議（綠色主題）
  - **時間戳記**：錯誤發生時間
  - **節點上下文**：節點 ID、名稱和類別
  - **🔍 在畫布上定位節點**：自動居中並高亮顯示問題節點

**關鍵設計原則**：

- ✅ **簡潔建議**：僅顯示可操作的建議（例如「請檢查輸入連接...」），而非冗長的錯誤描述
- ✅ **視覺區隔**：錯誤訊息（紅色）和建議（綠色）清楚區分
- ✅ **智慧截斷**：長錯誤顯示前 3 行 + 後 3 行，並可展開查看完整細節
- ✅ **即時更新**：兩個面板透過 WebSocket 事件自動更新新錯誤

---

## AI 智能錯誤分析

ComfyUI-Doctor 整合了主流 LLM 服務，提供智能化、上下文感知的除錯建議。

### 支援的 AI 提供商

#### 雲端服務

- **OpenAI**（GPT-4、GPT-4o 等）
- **DeepSeek**（DeepSeek-V2、DeepSeek-Coder）
- **Groq Cloud**（Llama 3、Mixtral - 超高速 LPU 推理）
- **Google Gemini**（Gemini Pro、Gemini Flash）
- **xAI Grok**（Grok-2、Grok-beta）
- **OpenRouter**（存取 Claude、GPT-4 及 100+ 種模型）

#### 本地服務（無需 API Key）

- **Ollama**（`http://127.0.0.1:11434`）- 在本地執行 Llama、Mistral、CodeLlama
- **LMStudio**（`http://localhost:1234/v1`）- 具備圖形介面的本地模型推理

> **💡 跨平台相容性**：預設 URL 可透過環境變數覆蓋：
>
> - `OLLAMA_BASE_URL` - 自訂 Ollama 端點（預設：`http://127.0.0.1:11434`）
> - `LMSTUDIO_BASE_URL` - 自訂 LMStudio 端點（預設：`http://localhost:1234/v1`）
>
> 這可避免 Windows 和 WSL2 Ollama 實例之間的衝突，或在 Docker/自訂環境中運行時的問題。

### 配置設定

![設定面板](../../assets/settings.png)

在 **Doctor 側邊欄** → **Settings** 面板中配置 AI 分析：

1. **AI Provider**：從下拉選單中選擇您偏好的 LLM 服務提供商。Base URL 會自動填入。
2. **AI Base URL**：API 端點（自動填入，但可自訂）
3. **AI API Key**：您的 API 金鑰（本地 LLM（如 Ollama/LMStudio）可留空）
4. **AI Model Name**：
   - 從下拉選單中選擇模型（自動從您的提供商 API 取得）
   - 點擊 🔄 重新整理按鈕可重新載入可用模型
   - 或勾選「手動輸入模型名稱」以輸入自訂模型名稱
5. **Privacy Mode (隱私模式)**：選擇雲端 AI 服務的 PII 淨化等級（詳見下方[設定 (Settings)](#設定-settings) 章節中的「10. Privacy Mode」說明）

### 使用 AI 分析

1. 當發生錯誤時，自動彈出 Doctor 面板
2. 參考預設的系統建議、或點擊錯誤卡片上的 **✨ 使用 AI 分析** 按鈕
3. 等待 LLM 分析錯誤（通常需要 3-10 秒）
4. 檢視 AI 生成的除錯建議

**安全性說明**：您的 API 金鑰僅在分析請求期間從前端傳輸至後端。系統不會記錄或持久儲存該金鑰。

### LLM 來源設定範例

| 服務提供者             | Base URL                                                   | 模型範例                        |
|--------------------|------------------------------------------------------------|---------------------------------|
| OpenAI             | `https://api.openai.com/v1`                                | `gpt-4o`                        |
| DeepSeek           | `https://api.deepseek.com/v1`                              | `deepseek-chat`                 |
| Groq               | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`       |
| Gemini             | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`              |
| Ollama（本地）     | `http://localhost:11434/v1`                                | `llama3.1:8b`                   |
| LMStudio（本地）   | `http://localhost:1234/v1`                                 | LMStudio 中載入的模型           |

---

## 設定 (Settings)

您也可以透過 **Doctor 側邊欄 → Settings (設定)** 分頁自定義 ComfyUI-Doctor 的行為。

### 1. Show error notifications (顯示錯誤通知)

**功能**：控制是否在畫面右上角顯示浮動錯誤通知卡片。
**用途**：如果您希望安靜地記錄錯誤而不受打擾，可關閉此選項。

### 2. Auto-open panel on error (錯誤時自動開啟面板)

**功能**：偵測到新錯誤時，自動開啟**右側錯誤報告面板**。
**用途**：**預設開啟 (ON)**。如果您希望保持面板關閉並手動開啟，可關閉此選項。

### 3. Error Check Interval (ms) (錯誤檢查間隔)

**功能**：前端檢查錯誤的頻率（毫秒）。預設：`2000`。
**用途**：調低（如 500）反應更靈敏；調高（如 5000）節省資源。通常保持預設即可。

### 4. Suggestion Language (語系選擇)

**功能**：選擇診斷報告與 Doctor 的顯示語系。
**用途**：目前已支援英文、繁體中文、簡體中文、日文 (陸續新增中)。設定後對新錯誤生效。

### 5. Enable Doctor (requires restart) (啟用 Doctor)

**功能**：日誌攔截系統的總開關。
**用途**：若需完全停用 Doctor 功能，可關閉此項（需重啟 ComfyUI 生效）。

### 6. LLM Provider (LLM 服務提供者)

**功能**：從下拉選單中選擇您偏好的 LLM 服務供應來源。
**選項**：OpenAI、DeepSeek、Groq Cloud、Google Gemini、xAI Grok、OpenRouter、Ollama（本地）、LMStudio（本地）、Custom（自訂）。
**用途**：選擇提供來源後會自動填入對應的 Base URL。對於本地提供商（Ollama/LMStudio），會自動彈出對話視窗提示可用模型清單；若沒有出現，請嘗試重新整理 ComfyUI 的前端（瀏覽器）。

### 7. AI Base URL (AI 基礎網址)

**功能**：LLM 服務的 API 端點。
**用途**：選擇提供來源後自動填入，但可針對自架或自訂端點進行修改。

### 8. AI API Key (AI API 金鑰)

**功能**：用於雲端 LLM 服務身份驗證的 API 金鑰。
**用途**：雲端 LLM 提供來源（OpenAI、DeepSeek 等）必填。本地 LLM（Ollama、LMStudio）可留空。
**安全性**：金鑰僅在分析請求時傳輸，不會被記錄或持久儲存。

### 9. AI Model Name (AI 模型名稱)

**功能**：指定用於錯誤分析的模型。
**用途**：

- **下拉選單模式**（預設）：從自動填充的下拉選單中選擇模型。點擊 🔄 重新整理按鈕可重新載入可用模型。
- **手動輸入模式**：勾選「手動輸入模型名稱」以手動輸入自訂模型名稱（例如：`gpt-4o`、`deepseek-chat`、`llama3.1:8b`）。
- 當您變更提供商或點擊重新整理時，模型會自動從所選提供商的 API 取得。
- 對於本地 LLM（Ollama/LMStudio），下拉選單會顯示所有本地可用的模型。

> 注意：**信任與健康 (Trust & Health)** 與 **匿名遙測 (Anonymous Telemetry)** 已移動至 **統計 (Statistics)** 分頁。

### 10. Privacy Mode (隱私模式)

**功能**：設定發送至雲端 AI 服務時的 PII (個人識別資訊) 淨化等級。
**選項**：

- **None (無)**：不進行任何淨化 - 建議用於本地 LLM (Ollama、LMStudio)
- **Basic (基本)** (預設)：標準保護 - 移除使用者路徑、API 金鑰、電子郵件、IP 位址
- **Strict (嚴格)**：最高隱私保護 - 在 Basic 基礎上額外移除 IPv6、SSH 指紋等

**用途**：使用雲端 LLM 時建議開啟至少 Basic 等級,以保護個人資訊不被傳送至第三方服務。企業用戶建議使用 Strict 等級以符合合規要求。

**淨化內容範例** (Basic 等級):

- ✅ Windows 使用者路徑: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOS 家目錄: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API 金鑰: `sk-abc123...` → `<API_KEY>`
- ✅ 電子郵件: `user@example.com` → `<EMAIL>`
- ✅ 私有 IP: `192.168.1.1` → `<PRIVATE_IP>`

**GDPR 合規性**：此功能支援 GDPR 第 25 條（資料保護設計原則），建議企業部署時啟用。

### 統計儀表板

![統計面板](../../assets/statistics_panel.png)

**統計儀表板**提供 ComfyUI 錯誤模式與穩定性趨勢的即時洞察。

**功能特色**：

- **📊 錯誤趨勢**：總錯誤數及最近 24 小時/7 天/30 天的計數
- **🔥 Top 錯誤模式**：顯示發生次數最多的前 5 種錯誤類型
- **📈 分類統計**：依錯誤類別（記憶體、工作流程、模型載入、框架、一般）視覺化分布
- **✅ 解決追蹤**：追蹤已解決、未解決和已忽略的錯誤
- **🧭 狀態控制**：在統計分頁將最新錯誤標記為 已解決 / 未解決 / 已忽略
- **🛡️ 信任與健康 (Trust & Health)**：檢視 `/doctor/health` 指標與插件信任報告（僅掃描）
- **📊 匿名遙測 (Anonymous Telemetry) (建設中 🚧)**：選擇性加入的本地使用事件緩衝區（切換/檢視/清除/匯出）

**使用方法**：

1. 開啟 Doctor 側邊欄（點擊左側 🏥 圖示）
2. 找到 **📊 錯誤統計** 可摺疊區塊
3. 點擊展開以檢視錯誤分析數據
4. 使用 **標記為** 按鈕設定最新錯誤狀態（已解決 / 未解決 / 已忽略）
5. 捲動至統計分頁底部以找到 **信任與健康** 與 **匿名遙測**區塊

**解決狀態控制**：

- 按鈕只有在有最新錯誤時間戳時才會啟用
- 狀態更新會寫入歷史紀錄並自動刷新解決率

**數據說明**：

- **總計 (30天)**：過去 30 天累積的錯誤數量
- **過去 24 小時**：最近 24 小時的錯誤數（有助於識別最新問題）
- **解決率**：顯示解決已知問題的進度
  - 🟢 **已解決**：您已修復的問題
  - 🟠 **未解決**：需要處理的活躍問題
  - ⚪ **已忽略**：您選擇忽略的非關鍵問題
- **Top 模式**：識別需要優先處理的錯誤類型
- **分類**：協助您了解問題是記憶體相關、工作流程問題、模型載入失敗等

**面板狀態持久化**：面板的開啟/關閉狀態會儲存在瀏覽器的 localStorage 中，您的偏好設定會跨工作階段保留。

---

## API 端點

### GET `/debugger/last_analysis`

取得最近一次錯誤分析結果：

```bash
curl http://localhost:8188/debugger/last_analysis
```

**回應範例**：

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja"],
  "last_error": "Traceback...",
  "suggestion": "💡 SUGGESTION: ...",
  "timestamp": "2025-12-28T06:49:11",
  "node_context": {
    "node_id": "42",
    "node_name": "KSampler",
    "node_class": "KSamplerNode",
    "custom_node_path": "ComfyUI-Impact-Pack"
  }
}
```

### GET `/debugger/history`

取得錯誤歷史記錄（最近 20 筆）：

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

切換 Doctor 的語系（請見語系切換章節）。

### POST `/doctor/analyze`

使用已配置的 LLM 服務分析錯誤。

**請求內容 (Payload)**：

```json
{
  "error": "Traceback...",
  "node_context": {...},
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "zh_TW"
}
```

**回應 (Response)**：

```json
{
  "analysis": "AI 生成的除錯建議..."
}
```

### POST `/doctor/verify_key`

透過測試與 LLM 提供商的連線來驗證 API 金鑰的有效性。

**請求內容 (Payload)**：

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**回應 (Response)**：

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

列出已配置的 LLM 提供商的可用模型。

**請求內容 (Payload)**：

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**回應 (Response)**：

```json
{
  "success": true,
  "models": [
    {"id": "llama3.1:8b", "name": "llama3.1:8b"},
    {"id": "mistral:7b", "name": "mistral:7b"}
  ],
  "message": "Found 2 models"
}
```

---

## 日誌檔案

所有日誌存放於：

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

檔名格式為：`comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

系統會自動保留最新的 10 個日誌檔案（可透過 `config.json` 調整）。

---

## 配置參數

建立 `config.json` 可自訂以下行為：

```json
{
  "max_log_files": 10,           // 最多保留幾個日誌檔案
  "buffer_limit": 100,            // Traceback 緩衝區大小（行數）
  "traceback_timeout_seconds": 5.0,  // Traceback 逾時秒數
  "history_size": 20,             // 錯誤歷史記錄數量
  "default_language": "zh_TW",    // 預設語系
  "enable_api": true,             // 啟用 API 端點
  "privacy_mode": "basic"         // 隱私模式: "none"、"basic" (預設)、"strict"
}
```

**參數說明**：

- `max_log_files`: 最多保留幾個日誌檔案
- `buffer_limit`: Traceback 緩衝區大小（行數）
- `traceback_timeout_seconds`: Traceback 逾時秒數
- `history_size`: 錯誤歷史記錄數量
- `default_language`: 預設語系
- `enable_api`: 啟用 API 端點
- `privacy_mode`: PII 淨化等級 - `"none"`、`"basic"` (預設) 或 `"strict"` (詳見上方隱私模式說明)

## 支援的錯誤模式

ComfyUI-Doctor 可偵測並提供以下建議：

- 格式類型不符（如 fp16 vs float32）
- 維度不匹配
- CUDA/MPS 記憶體不足 (OOM)
- 矩陣乘法錯誤
- 裝置/類型衝突
- 缺少 Python 模組
- Assertion 失敗
- Key/Attribute 錯誤
- Tensor 形狀不匹配
- 找不到檔案
- SafeTensors 載入錯誤
- CUDNN 執行失敗
- 缺少 InsightFace 函式庫
- Model/VAE 不匹配
- 無效的 Prompt JSON

等等...

## 使用技巧

1. **搭配 ComfyUI Manager**：自動安裝缺少的自訂節點
2. **查看日誌檔案**：問題回報時，完整的 Traceback 都有記錄
3. **使用內建側邊欄**：點擊左側選單的 🏥 Doctor 圖標，即時查看診斷
4. **節點除錯**：懷疑哪個節點有問題，就將除錯節點串接上去檢視數據

## 授權

MIT License

## 貢獻

歡迎提交各種 feedback：

**回報問題**：發現 bug 或有任何建議？請在 GitHub 上提交 issue。
**提交 PR**：透過修復 bug 或進行常規優化來幫助我們完善代碼庫。
**功能請求**：有其他需求、或新功能的好點子？請透過 GitHub issues 告訴我們。
