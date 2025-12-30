# ComfyUI-Doctor

繁體中文 | [English](README.md) | [📋 專案進度與開發藍圖](ROADMAP.md)

ComfyUI 專用的全時即時執行階段診斷套件。能自動攔截自啟動後的所有終端機輸出，捕捉完整的 Python 追蹤回溯 (Tracebacks)，並透過節點層級 (Node-level) 的上下文提取，提供具優先順序的修復建議。內建 19 種以上的錯誤模式識別、支援多國語言國際化 (i18n)、具備日誌持久化功能，並提供便於前端整合的 RESTful API。

---

## 最新更新（2025 年 12 月 30 日）

### F9：多語系支援擴展

我們已將語言支援從 4 種擴展至 9 種！ComfyUI-Doctor 現在能以以下語言提供錯誤建議：

- **English** 英文 (en)
- **繁體中文** (zh_TW)
- **简体中文** 簡體中文 (zh_CN)
- **日本語** 日文 (ja)
- **🆕 Deutsch** 德文 (de)
- **🆕 Français** 法文 (fr)
- **🆕 Italiano** 義大利文 (it)
- **🆕 Español** 西班牙文 (es)
- **🆕 한국어** 韓文 (ko)

所有 23 種錯誤模式已完整翻譯至所有語言，確保全球一致的診斷品質。

### F8：側邊欄設定整合

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

---

## 功能特色

- **自動錯誤監控**：即時攔截所有終端機輸出並偵測 Python Traceback
- **智慧錯誤分析**：內建 19+ 種常見錯誤模式，提供可行的修復建議
- **節點上下文提取**：自動識別發生錯誤的節點（節點 ID、名稱、類別）
- **多語系支援**：目前已支援：英文、繁體中文、簡體中文、日文
- **除錯節點**：深度檢查工作流中的數據流動 (Tensor 形狀、數值統計等)
- **錯誤歷史記錄**：透過 API 保留最近的錯誤緩衝區
- **RESTful API**：提供六個端點供前端整合使用
- **AI 智能分析**：一鍵呼叫 LLM 進行錯誤分析，支援 8+ 種 AI 提供商（OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等）
- **互動式對話介面**：整合於 ComfyUI 側邊欄的多輪 AI 除錯助手
- **互動式側邊欄介面**：視覺化錯誤面板，可定位節點並即時診斷
- **靈活配置**：完整的設定面板，自訂各項行為

### 🆕 AI 對話介面

全新的互動式對話介面提供直接整合於 ComfyUI 左側邊欄的對話式除錯體驗。當錯誤發生時，只需點擊「Analyze with AI」即可開始與您偏好的 LLM 進行多輪對話。

![AI 對話介面](assets/chat-ui.png)

**核心特色：**

- **情境感知**：自動包含錯誤詳情、節點資訊與工作流程上下文
- **串流回應**：即時顯示 LLM 回應，並正確格式化
- **多輪對話**：提出後續問題以深入探討問題
- **永遠可見**：輸入區域固定於底部，使用黏性定位保持可見
- **支援 8+ 種 LLM 提供商**：OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等

**使用方式：**

1. 當錯誤發生時，打開 Doctor 側邊欄（左側面板）
2. 點擊錯誤上下文區域中的「✨ Analyze with AI」按鈕
3. AI 會自動分析錯誤並提供建議
4. 在輸入框中輸入後續問題以繼續對話
5. 按 Enter 或點擊「Send」按鈕送出訊息

---

## 安裝

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

![Doctor 錯誤報告](./assets/error%20report.png)

- **狀態指示燈**：面板標題列中的彩色圓點
  - 🟢 **綠色**：系統正常運作，未偵測到錯誤
  - 🔴 **紅色（閃爍）**：偵測到活動錯誤

- **最新診斷卡片**：顯示最近的錯誤資訊，包含：
  - 錯誤訊息與時間戳記
  - 節點上下文（節點 ID、名稱、類別）
  - **🔍 在畫布上定位節點**：自動居中並高亮顯示問題節點
  - **✨ 使用 AI 分析**：將錯誤發送至已配置的 LLM 以獲取 AI 提供的除錯建議

- **即時更新**：面板透過 WebSocket 事件自動更新新錯誤

- **錯誤時自動開啟**：在設定中啟用後，偵測到錯誤時自動展開面板

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

![設定面板](./assets/settings.png)

在 **ComfyUI 設定** → **Doctor** → **LLM Settings** 中配置 AI 分析：

1. **AI Provider**：從下拉選單中選擇您偏好的 LLM 服務提供商。Base URL 會自動填入。
2. **AI Base URL**：API 端點（自動填入，但可自訂）
3. **AI API Key**：您的 API 金鑰（本地 LLM（如 Ollama/LMStudio）可留空）
4. **AI Model Name**：輸入模型名稱（例如：`gpt-4o`、`deepseek-chat`、`llama3.1:8b`）

#### 查詢本地 LLM 可用模型

當您選擇 **Ollama** 或 **LMStudio** 作為 LLM 提供來源時，系統會自動顯示可用模型的彈出視窗：

![模型列表警示](./assets/model%20list.png)

只需複製所需的模型名稱並貼到 **AI Model Name** 欄位即可。

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

您可以透過 ComfyUI 設定面板（齒輪圖標）自定義 ComfyUI-Doctor 的行為。

### 1. Show error notifications (顯示錯誤通知)

**功能**：控制是否在畫面右上角顯示浮動錯誤通知卡片。
**用途**：如果您希望安靜地記錄錯誤而不受打擾，可關閉此選項。

### 2. Auto-open panel on error (錯誤時自動開啟面板)

**功能**：偵測到新錯誤時，自動展開 Doctor 側邊欄。
**用途**：**最推薦開啟**。省去手動查找原因的時間，即時看到診斷結果。

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
**用途**：輸入模型識別碼（例如：`gpt-4o`、`deepseek-chat`、`llama3.1:8b`）。對於本地 LLM，切換提供商時會在警示對話框中顯示可用模型。

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
  "enable_api": true              // 啟用 API 端點
}
```

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

歡迎提交 Pull Request 協助改進本專案！

## 支援

如果遇到任何問題或有功能建議，請在 GitHub 上提交 Issue。
