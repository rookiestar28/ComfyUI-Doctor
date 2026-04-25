# ComfyUI-Doctor

[English](../../README.md) | 繁中 | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor 是 ComfyUI 的即時診斷與除錯輔助工具。它會擷取執行期錯誤、辨識可能的節點脈絡、顯示本地修復建議，並可選擇使用 LLM 對話流程進行更深入的錯誤分析。

## 最新狀態

- 已加入宿主相容性檢查，涵蓋 Doctor 依賴的 ComfyUI、ComfyUI frontend 與 Desktop 介面。
- 前端設定整合已對齊目前的 ComfyUI settings API，舊版 fallback 已集中隔離。
- 執行錯誤可從近期 execution/progress 事件補強節點 lineage。
- Shared server 可啟用嚴格 admin token 模式；單機 loopback convenience mode 會有更清楚的提示。
- Server-side credential store 支援加密儲存與 encrypt-then-MAC 文件化說明。
- 新增選用 coverage baseline lane；預設完整驗證流程不變。

## 核心功能

- 從 ComfyUI 啟動階段開始監控 console 與 traceback。
- 58 個 JSON 錯誤模式，包含 22 個核心模式與 36 個社群 extension 模式。
- 依宿主事件資料擷取節點 ID、名稱、類別與 custom-node path。
- Doctor sidebar 提供 Chat、Statistics、Settings 三個主要分頁。
- 支援 OpenAI-compatible、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio 等 LLM 工作流程。
- 隱私模式可在外送 LLM 前遮蔽路徑、credential-looking values、email、private IP 等內容。
- 選用 admin-gated server-side credential store，並支援 encryption-at-rest。
- 內建 diagnostics、statistics、plugin trust report、telemetry controls 與 community feedback preview/submit。
- 支援英文、繁中、簡中、日文、韓文、德文、法文、義大利文、西班牙文。

## 安裝

### ComfyUI-Manager

1. 開啟 ComfyUI，點選 **Manager**。
2. 選擇 **Install Custom Nodes**。
3. 搜尋 `ComfyUI-Doctor`。
4. 安裝後重新啟動 ComfyUI。

### 手動安裝

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

重新啟動 ComfyUI 後，左側 sidebar 應出現 **Doctor** 入口。

## 基本使用

- **自動診斷**：Doctor 會自動擷取錯誤、比對已知模式，並顯示最新診斷。
- **Doctor Sidebar**：Chat 檢視最新錯誤並進行 LLM 對話；Statistics 檢視趨勢、診斷與健康資訊；Settings 管理語言、Provider、Model、Privacy Mode 與 credential 來源。
- **Smart Debug Node**：可插入 workflow 連線中檢查資料型別、shape、dtype、device 與數值統計，且不改變資料輸出。

## 文件

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## 驗證

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## 授權

MIT License
