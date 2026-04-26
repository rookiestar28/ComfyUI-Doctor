# ComfyUI-Doctor

繁中 | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor 是 ComfyUI 的即時診斷與除錯助手。它會擷取執行期錯誤、辨識可能相關的節點脈絡、顯示可操作的本機建議，並可選擇透過 LLM 聊天流程進行更深入的疑難排解。

## 最新更新

最新更新內容以英文 README 為準，請參閱 [Latest Updates](../../README.md#latest-updates---click-to-expand)。

## 核心功能

- 從啟動階段開始即時擷取 ComfyUI console/error 輸出。
- 內建 58 個 JSON 錯誤模式建議，包含 22 個核心模式與 36 個社群擴充模式。
- 當 ComfyUI 提供足夠事件資料時，會針對近期 workflow 執行錯誤擷取並驗證節點脈絡。
- Doctor 側邊欄包含 Chat、Statistics、Settings 分頁。
- 可選用 OpenAI-compatible services、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio 進行 LLM 分析，並使用統一的 provider request/response 處理。
- 對外 LLM 請求具備隱私控制，包含路徑、金鑰、Email、IP 的清理模式。
- 可選用伺服器端憑證儲存，支援 admin guard 與靜態加密儲存。
- 提供本機診斷、統計、plugin trust report、telemetry 控制，以及社群回饋預覽/提交工具。
- Doctor API 失敗回應採用一致的 JSON error envelope。
- UI 與建議完整支援英文、繁體中文、簡體中文、日文、韓文、德文、法文、義大利文、西班牙文。

## 截圖

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## 安裝

### ComfyUI-Manager

1. 開啟 ComfyUI 並點選 **Manager**。
2. 選擇 **Install Custom Nodes**。
3. 搜尋 `ComfyUI-Doctor`。
4. 安裝後重新啟動 ComfyUI。

### 手動安裝

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Clone 完成後重新啟動 ComfyUI。Doctor 應會輸出啟動診斷資訊，並註冊 `Doctor` 側邊欄入口。

## 基本使用

### 自動診斷

安裝後，Doctor 會被動記錄 ComfyUI 執行期輸出、偵測 traceback、比對已知錯誤模式，並在側邊欄與可選的右側報告面板顯示最新診斷。
使用可選 LLM 分析時，Doctor 會透過同一個結構化 pipeline 建立 prompt context；該 pipeline 負責清理敏感資訊、節點脈絡、執行紀錄、workflow pruning 與系統資訊。

### Doctor 側邊欄

在 ComfyUI 左側側邊欄開啟 **Doctor**：

- **Chat**：檢視最新錯誤脈絡，並提出後續除錯問題。
- **Statistics**：查看近期錯誤趨勢、診斷資訊、信任/健康狀態、telemetry 控制與回饋工具。
- **Settings**：選擇語言、LLM provider、base URL、model、隱私模式、自動開啟行為，以及可選的伺服器端憑證儲存。

### Smart Debug Node

在 canvas 上按右鍵，新增 **Smart Debug Node**，並將它放入 workflow 中以檢查流經的資料，而不改變 workflow 輸出。

## 可選 LLM 設定

雲端 provider 需要透過 session-only UI 欄位、環境變數，或可選的 admin-gated server store 提供憑證。Ollama 與 LMStudio 等本機 provider 可在沒有雲端憑證的情況下運作。
Doctor 會標準化 OpenAI-compatible APIs、Anthropic、Ollama 的 provider-specific request/response 格式，讓 chat、single-shot analysis、model listing、connectivity check 共用一致的後端行為。

建議預設值：

- 對雲端 provider 使用 **Privacy Mode: Basic** 或 **Strict**。
- 在共享或類 production 環境中使用環境變數。
- 在共享伺服器上設定 `DOCTOR_ADMIN_TOKEN` 與 `DOCTOR_REQUIRE_ADMIN_TOKEN=1`。
- 只在單使用者桌面環境中保留 local-only loopback convenience mode。

## 文件

- [User Guide](../USER_GUIDE.md)：UI 導覽、診斷、隱私模式、LLM 設定與回饋流程。
- [Configuration and Security](../CONFIGURATION_SECURITY.md)：環境變數、admin guard 行為、憑證儲存、outbound safety、telemetry 與 CSP 注意事項。
- [API Reference](../API_REFERENCE.md)：公開的 Doctor 與 debugger endpoints。
- [Validation Guide](../VALIDATION.md)：本機 full-gate 指令與可選的相容性/coverage lanes。
- [Plugin Guide](../PLUGIN_GUIDE.md)：社群 plugin trust model 與 plugin authoring notes。
- [Plugin Migration](../PLUGIN_MIGRATION.md)：plugin manifest 與 allowlist 的 migration tooling。
- [Outbound Safety](../OUTBOUND_SAFETY.md)：static checker 與 outbound request safety rules。

## 支援的錯誤模式

錯誤模式以 JSON 檔案存放於 `patterns/`，可在不修改程式碼的情況下更新。

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

社群 pack 目前涵蓋常見的 ControlNet、LoRA、VAE、AnimateDiff、IPAdapter、FaceRestore、checkpoint、sampler、scheduler 與 CLIP 失敗模式。

## 驗證

若要執行本機 CI-parity 驗證，請使用專案 full-test script：

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Full gate 會涵蓋 secrets detection、pre-commit hooks、host-like startup validation、backend unit tests 與 frontend Playwright E2E tests。明確的分階段指令與可選 lanes 請參閱 [Validation Guide](../VALIDATION.md)。

## 需求

- ComfyUI custom-node 環境。
- Python 3.10 或更新版本。
- 只有 frontend E2E validation 需要 Node.js 18 或更新版本。
- 除 ComfyUI 內建環境與 Python standard library 之外，不需要額外 runtime Python package dependency。

## 授權

MIT License

## 貢獻

歡迎提交錯誤模式與文件貢獻。若要修改程式碼，請在開啟 pull request 前執行完整 validation gate，並避免提交產生的本機狀態、log、憑證或內部規劃檔案。
