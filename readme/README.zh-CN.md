# ComfyUI-Doctor

[繁中](README.zh-TW.md) | 简体中文 | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [项目进度与开发蓝图](../ROADMAP.md)

这是一个 ComfyUI 专用的全时即时运行阶段诊断套件。能自动拦截启动后的所有终端输出，捕捉完整的 Python 追踪回溯 (Tracebacks)，并通过节点层级 (Node-level) 的上下文提取，提供具优先顺序的修复建议。内置 57+ 种错误模式（22 个内置 + 35 个社区模式）、采用 JSON 热重载模式，让使用者自行维护管理其他 Error 类型；目前已支持 9 种语言、具备日志持久化功能，并提供便于前端整合的 RESTful API。

## 最新更新（2026 年 1 月）

<details>
<summary><strong>更新 (v1.4.0, 2026 年 1 月)</strong> - 点击展开</summary>

- A7 Preact 迁移完成（Phase 5A–5C：Chat/Stats islands、fallback、registry、shared rendering）。
- 整合加固：生命周期处理与 E2E 覆盖加强。
- UI 修复：Locate Node 按钮保留、Sidebar tooltip 加载时序修正。

</details>

---

<details>
<summary><strong>F4：统计仪表板</strong> - 点击展开</summary>

**一眼掌握 ComfyUI 稳定性！**

ComfyUI-Doctor 现在包含**统计仪表板**，提供错误趋势、常见问题与解决进度的深入洞察。

**功能特色**：

- 📊 **错误趋势**：追踪 24 小时/7 天/30 天的错误统计
- 🔥 **Top 5 模式**：查看最常发生的错误类型
- 📈 **分类统计**：依类别可视化错误分布（内存、工作流、模型加载等）
- ✅ **解决追踪**：监控已解决 vs. 未解决的错误
- 🌍 **完整 i18n 支持**：支持全部 9 种语言

![统计仪表板](assets/statistics_panel.png)

**使用方法**：

1. 打开 Doctor 侧边栏面板（点击左侧 🏥 图标）
2. 展开“📊 错误统计”区块
3. 检视实时错误分析与趋势
4. 将错误标记为已解决/已忽略以追踪进度

**后端 API**：

- `GET /doctor/statistics?time_range_days=30` - 获取统计资料
- `POST /doctor/mark_resolved` - 更新解决状态

**测试覆盖率**：17/17 后端测试 ✅ | 14/18 E2E 测试（78% 通过率）

**实作细节**：见 `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

---

<details>
<summary><strong>T8：Pattern 验证 CI </strong> - 点击展开</summary>

**自动化质量检查现在保护 pattern 完整性！**

ComfyUI-Doctor 现在包含**持续集成测试**，用于所有错误模式，确保零缺陷贡献。

**T8 验证项目**：

- ✅ **JSON 格式**：全部 8 个 pattern 文件正确编译
- ✅ **Regex 语法**：全部 57 个 patterns 具有有效的正则表达式
- ✅ **i18n 完整性**：100% 翻译覆盖率（57 patterns × 9 语言 = 513 项检查）
- ✅ **Schema 符合性**：必填字段（`id`、`regex`、`error_key`、`priority`、`category`）
- ✅ **Metadata 质量**：有效的 priority 范围（50-95）、唯一 ID、正确的类别

**GitHub Actions 整合**：

- 在每次 push/PR 影响 `patterns/`、`i18n.py` 或测试时触发
- 约 3 秒内执行，成本为 $0（GitHub Actions 免费额度）
- 如果验证失败则阻止合并

**对于贡献者**：

```bash
# 在 commit 前本地验证
python run_pattern_tests.py

# 输出：
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (共 9 种语言)
```

**测试结果**：所有检查均以 100% 通过率通过

**实作细节**：见 `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

---

<details>
<summary><strong>Phase 4B：模式系统全面升级（阶段 1-3 完成）</strong> - 点击展开</summary>

ComfyUI-Doctor 完成重大架构升级，具备 **57+ 错误模式**与 **JSON 热重载模式管理**！

**阶段 1：Logger 架构修复**

- 实作 SafeStreamWrapper 与 queue-based 背景处理
- 消除 deadlock 风险与 race condition
- 修复与 ComfyUI LogInterceptor 的冲突问题

**阶段 2：JSON 模式管理（F2）**

- 全新 PatternLoader 支持热重载（无需重启！）
- 模式定义于 `patterns/` 目录下的 JSON 文件
- 22 个内置模式位于 `patterns/builtin/core.json`
- 易于扩展与维护

**阶段 3：社区模式扩充（F12）**

- **35 个全新社区模式**，涵盖热门扩展功能：

  - **ControlNet**（8 个模式）：模型加载、预处理、图像尺寸
  - **LoRA**（6 个模式）：加载错误、兼容性、权重问题
  - **VAE**（5 个模式）：编码/解码失败、精度、拼接
  - **AnimateDiff**（4 个模式）：模型加载、帧数、上下文长度
  - **IPAdapter**（4 个模式）：模型加载、图像编码、兼容性
  - **FaceRestore**（3 个模式）：CodeFormer/GFPGAN 模型、侦测
  - **杂项**（5 个模式）：Checkpoint、采样器、调度器、CLIP
- 完整 i18n 支持：英文、繁体中文、简体中文
- 总计：**57 个错误模式**（22 个内置 + 35 个社区）

**优势**：

- ✅ 更全面的错误覆盖率
- ✅ 热重载模式，无需重启 ComfyUI
- ✅ 社区可透过 JSON 文件贡献模式
- ✅ 更简洁、易维护的代码库

</details>

---

<details>
<summary><strong>先前更新（2025 年 12 月）</strong> - 点击展开</summary>

### F9：多语系支持扩展

已将语系支持从 4 种扩展至 9 种！ComfyUI-Doctor 现在能以以下语言提供错误建议：

- **English** 英文 (en)
- **繁體中文** (zh_TW)
- **简体中文** 简体中文 (zh_CN)
- **日本語** 日文 (ja)
- **🆕 Deutsch** 德文 (de)
- **🆕 Français** 法文 (fr)
- **🆕 Italiano** 意大利文 (it)
- **🆕 Español** 西班牙文 (es)
- **🆕 한국어** 韩文 (ko)

所有 57 种错误模式已完整翻译至所有语言，确保一致的诊断质量。

### F8：侧边栏设置整合

设置已简化！直接从侧边栏配置 Doctor：

- 点击侧边栏标题的 ⚙️ 图标即可存取所有设置
- 语言选择（9 种语言）
- AI 提供商快速切换（OpenAI、DeepSeek、Groq、Gemini、Ollama 等）
- 更换提供商时自动填入 Base URL
- API 密钥管理（密码保护输入）
- 模型名称配置
- 设置透过 localStorage 跨工作阶段保存
- 保存时视觉反馈（✅ 已保存！/ ❌ 错误）

ComfyUI 设置面板现在仅显示启用/停用切换 - 所有其他设置已移至侧边栏，提供更简洁、更整合的体验。

</details>

---

## 功能特色

- **自动错误监控**：实时拦截所有终端输出并侦测 Python Traceback
- **智能错误分析**：内置 57+ 种错误模式（22 个内置 + 35 个社区模式），提供可行的修复建议
- **节点上下文提取**：自动识别发生错误的节点（节点 ID、名称、类别）
- **系统环境上下文**：AI 分析时自动包含 Python 版本、已安装包（pip list）与操作系统信息
- **多语系支持**：支持 9 种语言（英文、繁体中文、简体中文、日文、德文、法文、意大利文、西班牙文、韩文）
- **JSON 模式管理**：热重载错误模式，无需重启 ComfyUI
- **社区模式支持**：涵盖 ControlNet、LoRA、VAE、AnimateDiff、IPAdapter、FaceRestore 等
- **除错节点**：深度检查工作流中的数据流动 (Tensor 形状、数值统计等)
- **错误历史记录**：透过 API 保留最近的错误缓冲区
- **RESTful API**：提供七个端点供前端整合使用
- **AI 智能分析**：一键呼叫 LLM 进行错误分析，支持 8+ 种 AI 提供商（OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等）
- **交互式对话界面**：整合于 ComfyUI 侧边栏的多轮 AI 除错助手
- **交互式侧边栏界面**：可视化错误面板，可定位节点并实时诊断
- **灵活配置**：完整的设置面板，自定义各项行为

### 🆕 AI 对话界面

全新的交互式对话界面提供直接整合于 ComfyUI 左侧边栏的对话式除错体验。当错误发生时，只需点击“Analyze with AI”即可开始与您偏好的 LLM 进行多轮对话。

<div align="center">
<img src="assets/chat-ui.png" alt="AI Chat Interface">
</div>

**核心特色：**

- **情境感知**：自动包含错误详情、节点信息与工作流程上下文
- **环境感知**：包含 Python 版本、已安装包与操作系统信息以提升侦错准确度
- **串流响应**：实时显示 LLM 响应，并正确格式化
- **多轮对话**：提出后续问题以深入探讨问题
- **永远可见**：输入区域固定于底部，使用粘性定位保持可见
- **支持 8+ 种 LLM 提供商**：OpenAI、DeepSeek、Groq、Gemini、Ollama、LMStudio 等
- **智能缓存**：包列表缓存 24 小时，避免效能影响

**使用方式：**

1. 当错误发生时，打开 Doctor 侧边栏（左侧面板）
2. 点击错误上下文区域中的“✨ Analyze with AI”按钮
3. AI 会自动分析错误并提供建议
4. 在输入框中输入后续问题以继续对话
5. 按 Enter 或点击“Send”按钮送出消息

> **💡 免费 API 提示**：[Google AI Studio](https://aistudio.google.com/app/apikey)（Gemini）提供丰富的免费额度，无需信用卡即可使用。非常适合零成本开始使用 AI 智能除错功能！

---

## 安装

### 方式一：使用 ComfyUI-Manager（推荐）

1. 打开 ComfyUI，点击菜单中的 **Manager** 按钮
2. 选择 **Install Custom Nodes**
3. 搜索 `ComfyUI-Doctor`
4. 点击 **Install** 并重新启动 ComfyUI

### 方式二：手动安装（Git Clone）

1. 进入 ComfyUI 的自定义节点目录：

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. 下载此项目：

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. 重新启动 ComfyUI

4. 在终端查看初始化消息确认安装成功：

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

### 被动模式（自动监控）

安装后无需任何操作，ComfyUI-Doctor 会自动：

- 记录所有日志至 `logs/` 目录
- 侦测错误并提供建议
- 记录系统环境信息

**错误输出范例**：

```text
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM（内存不足）：GPU VRAM 已满。建议：
   1. 减少 Batch Size
   2. 使用 '--lowvram' 参数
   3. 关闭其他 GPU 程序
----------------------------------------
```

### 主动模式（除错节点）

1. 在画布上右键点选：`Add Node` → `Smart Debug Node`
2. 将节点串接在任何连线中（支持通配输入 `*`）
3. 执行工作流

**输出范例**：

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

此节点会透传数据，不会影响工作流执行。

---

## 前端界面

ComfyUI-Doctor 提供交互式侧边栏界面，用于实时错误监控和诊断。

### 打开 Doctor 面板

点击 ComfyUI 菜单（左侧边栏）中的 **🏥 Doctor** 按钮即可打开 Doctor 面板。面板会从画面右侧滑入。

### 界面功能

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Error Report">
</div>

Doctor 界面由两个面板组成：

#### 左侧边栏面板（Doctor 侧边栏）

点击 ComfyUI 左侧菜单中的 **🏥 Doctor** 图标即可存取：

- **设置面板**（⚙️ 图标）：配置语言、AI 提供商、API 密钥和模型选择
- **错误上下文卡片**：当错误发生时显示：
  - **💡 建议**：简洁、可操作的建议（例如“请检查输入连接并确保符合节点要求。”）
  - **时间戳**：错误发生时间
  - **节点上下文**：节点 ID 和名称（如适用）
  - **✨ 使用 AI 分析**：启动交互式聊天进行详细除错
- **AI 聊天界面**：与您的 LLM 进行多轮对话以深入分析错误
- **固定输入区域**：始终显示在底部，方便提出后续问题

#### 右侧错误面板（最新诊断）

右上角的实时错误通知：

![Doctor Error Report](./assets/error-report.png)

- **状态指示灯**：显示系统健康状态的彩色圆点
  - 🟢 **绿色**：系统正常运作，未侦测到错误
  - 🔴 **红色（闪烁）**：侦测到活动错误
- **最新诊断卡片**：显示最近的错误信息，包含：
  - **错误摘要**：简短的错误描述（红色主题，长错误可折叠）
  - **💡 建议**：简洁的可操作建议（绿色主题）
  - **时间戳**：错误发生时间
  - **节点上下文**：节点 ID、名称和类别
  - **🔍 在画布上定位节点**：自动居中并高亮显示问题节点

**关键设计原则**：

- ✅ **简洁建议**：仅显示可操作的建议（例如“请检查输入连接...”），而非冗长的错误描述
- ✅ **视觉区隔**：错误消息（红色）和建议（绿色）清楚区分
- ✅ **智能截断**：长错误显示前 3 行 + 后 3 行，并可展开查看完整细节
- ✅ **实时更新**：两个面板透过 WebSocket 事件自动更新新错误

---

## AI 智能错误分析

ComfyUI-Doctor 整合了主流 LLM 服务，提供智能化、上下文感知的除错建议。

### 支持的 AI 提供商

#### 云端服务

- **OpenAI**（GPT-4、GPT-4o 等）
- **DeepSeek**（DeepSeek-V2、DeepSeek-Coder）
- **Groq Cloud**（Llama 3、Mixtral - 超高速 LPU 推理）
- **Google Gemini**（Gemini Pro、Gemini Flash）
- **xAI Grok**（Grok-2、Grok-beta）
- **OpenRouter**（存取 Claude、GPT-4 及 100+ 种模型）

#### 本地服务（无需 API Key）

- **Ollama**（`http://127.0.0.1:11434`）- 在本地执行 Llama、Mistral、CodeLlama
- **LMStudio**（`http://localhost:1234/v1`）- 具备图形界面的本地模型推理

> **💡 跨平台兼容性**：默认 URL 可透过环境变量覆盖：
>
> - `OLLAMA_BASE_URL` - 自定义 Ollama 端点（默认：`http://127.0.0.1:11434`）
> - `LMSTUDIO_BASE_URL` - 自定义 LMStudio 端点（默认：`http://localhost:1234/v1`）
>
> 这可避免 Windows 和 WSL2 Ollama 实例之间的冲突，或在 Docker/自定义环境中运行与的问题。

### 配置设置

![设置面板](./assets/settings.png)

在 **Doctor 侧边栏** → **Settings** 面板中配置 AI 分析：

1. **AI Provider**：从下拉菜单中选择您偏好的 LLM 服务提供商。Base URL 会自动填入。
2. **AI Base URL**：API 端点（自动填入，但可自定义）
3. **AI API Key**：您的 API 密钥（本地 LLM（如 Ollama/LMStudio）可留空）
4. **AI Model Name**：
   - 从下拉菜单中选择模型（自动从您的提供商 API 获取）
   - 点击 🔄 重新整理按钮可重新加载可用模型
   - 或勾选“手动输入模型名称”以输入自定义模型名称
5. **Privacy Mode (隐私模式)**：选择云端 AI 服务的 PII 净化等级（详见下方[设置 (Settings)](#设置-settings) 章节中的“10. Privacy Mode”说明）

### 使用 AI 分析

1. 当发生错误时，自动弹出 Doctor 面板
2. 参考默认的系统建议、或点击错误卡片上的 **✨ 使用 AI 分析** 按钮
3. 等待 LLM 分析错误（通常需要 3-10 秒）
4. 检视 AI 生成的除错建议

**安全性说明**：您的 API 密钥仅在分析请求期间从前端传输至后端。系统不会记录或持久存储该密钥。

### LLM 来源设置范例

| 服务提供者             | Base URL                                                   | 模型范例                        |
|--------------------|------------------------------------------------------------|---------------------------------|
| OpenAI             | `https://api.openai.com/v1`                                | `gpt-4o`                        |
| DeepSeek           | `https://api.deepseek.com/v1`                              | `deepseek-chat`                 |
| Groq               | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`       |
| Gemini             | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`              |
| Ollama（本地）     | `http://localhost:11434/v1`                                | `llama3.1:8b`                   |
| LMStudio（本地）   | `http://localhost:1234/v1`                                 | LMStudio 中加载的模型           |

---

## 设置 (Settings)

您可以透过 ComfyUI 设置面板（齿轮图标）自定义 ComfyUI-Doctor 的行为。

### 1. Show error notifications (显示错误通知)

**功能**：控制是否在画面右上角显示浮动错误通知卡片。
**用途**：如果您希望安静地记录错误而不受打扰，可关闭此选项。

### 2. Auto-open panel on error (错误时自动开启面板)

**功能**：侦测到新错误时，自动展开 Doctor 侧边栏。
**用途**：**最推荐开启**。省去手动查找原因的时间，即时看到诊断结果。

### 3. Error Check Interval (ms) (错误检查间隔)

**功能**：前端检查错误的频率（毫秒）。默认：`2000`。
**用途**：调低（如 500）反应更灵敏；调高（如 5000）节省资源。通常保持默认即可。

### 4. Suggestion Language (语系选择)

**功能**：选择诊断报告与 Doctor 的显示语系。
**用途**：目前已支持英文、繁体中文、简体中文、日文 (陆续新增中)。设置后对新错误生效。

### 5. Enable Doctor (requires restart) (启用 Doctor)

**功能**：日志拦截系统的总开关。
**用途**：若需完全停用 Doctor 功能，可关闭此项（需重启 ComfyUI 生效）。

### 6. LLM Provider (LLM 服务提供者)

**功能**：从下拉菜单中选择您偏好的 LLM 服务供应来源。
**选项**：OpenAI、DeepSeek、Groq Cloud、Google Gemini、xAI Grok、OpenRouter、Ollama（本地）、LMStudio（本地）、Custom（自定义）。
**用途**：选择提供来源后会自动填入对应的 Base URL。对于本地提供商（Ollama/LMStudio），会自动弹出对话视窗提示可用模型清单；若没有出现，请尝试重新整理 ComfyUI 的前端（浏览器）。

### 7. AI Base URL (AI 基础网址)

**功能**：LLM 服务的 API 端点。
**用途**：选择提供来源后自动填入，但可针对自架或自定义端点进行修改。

### 8. AI API Key (AI API 密钥)

**功能**：用于云端 LLM 服务身份验证的 API 密钥。
**用途**：云端 LLM 提供来源（OpenAI、DeepSeek 等）必填。本地 LLM（Ollama、LMStudio）可留空。
**安全性**：密钥仅在分析请求时传输，不会被记录或持久存储。

### 9. AI Model Name (AI 模型名称)

**功能**：指定用于错误分析的模型。
**用途**：

- **下拉菜单模式**（默认）：从自动填充的下拉菜单中选择模型。点击 🔄 重新整理按钮可重新加载可用模型。
- **手动输入模式**：勾选“手动输入模型名称”以手动输入自定义模型名称（例如：`gpt-4o`、`deepseek-chat`、`llama3.1:8b`）。
- 当您变更提供商或点击重新整理时，模型会自动从所选提供商的 API 获取。
- 对于本地 LLM（Ollama/LMStudio），下拉菜单会显示所有本地可用的模型。

### 10. Privacy Mode (隐私模式)

**功能**：设定发送至云端 AI 服务时的 PII (个人识别信息) 净化等级。
**选项**：

- **None (无)**：不进行任何净化 - 建议用于本地 LLM (Ollama、LMStudio)
- **Basic (基本)** (默认)：标准保护 - 移除使用者路径、API 密钥、电子邮件、IP 地址
- **Strict (严格)**：最高隐私保护 - 在 Basic 基础上额外移除 IPv6、SSH 指纹等

**用途**：使用云端 LLM 时建议开启至少 Basic 等级,以保护个人信息不被传送至第三方服务。企业用户建议使用 Strict 等级以符合合规要求。

**净化内容范例** (Basic 等级):

- ✅ Windows 使用者路径: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOS 家目录: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API 密钥: `sk-abc123...` → `<API_KEY>`
- ✅ 电子邮件: `user@example.com` → `<EMAIL>`
- ✅ 私有 IP: `192.168.1.1` → `<PRIVATE_IP>`

**GDPR 合规性**：此功能支持 GDPR 第 25 条（数据保护设计原则），建议企业部署时启用。

### 统计仪表板

![统计面板](assets/statistics_panel.png)

**统计仪表板**提供 ComfyUI 错误模式与稳定性趋势的即时洞察。

**功能特色**：

- **📊 错误趋势**：总错误数及最近 24 小时/7 天/30 天的计数
- **🔥 Top 错误模式**：显示发生次数最多的前 5 种错误类型
- **📈 分类统计**：依错误类别（内存、工作流、模型加载、框架、一般）可视化分布
- **✅ 解决追踪**：追踪已解决、未解决和已忽略的错误

**使用方法**：

1. 打开 Doctor 侧边栏（点击左侧 🏥 图标）
2. 找到 **📊 错误统计** 可折叠区块
3. 点击展开以检视错误分析数据
4. 直接从错误卡片将错误标记为已解决/已忽略，以更新解决追踪

**数据说明**：

- **总计 (30天)**：过去 30 天累积的错误数量
- **过去 24 小时**：最近 24 小时的错误数（有助于识别最新问题）
- **解决率**：显示解决已知问题的进度
  - 🟢 **已解决**：您已修复的问题
  - 🟠 **未解决**：需要处理的活跃问题
  - ⚪ **已忽略**：您选择忽略的非关键问题
- **Top 模式**：识别需要优先处理的错误类型
- **分类**：协助您了解问题是内存相关、工作流问题、模型加载失败等

**面板状态持久化**：面板的开启/关闭状态会存储在浏览器的 localStorage 中，您的偏好设置会跨工作阶段保留。

---

## API 端点

### GET `/debugger/last_analysis`

取得最近一次错误分析结果：

```bash
curl http://localhost:8188/debugger/last_analysis
```

**响应范例**：

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

取得错误历史记录（最近 20 笔）：

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

切换 Doctor 的语系（请见语系切换章节）。

### POST `/doctor/analyze`

使用已配置的 LLM 服务分析错误。

**请求内容 (Payload)**：

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

**响应 (Response)**：

```json
{
  "analysis": "AI 生成的除错建议..."
}
```

### POST `/doctor/verify_key`

透过测试与 LLM 提供商的连线来验证 API 密钥的有效性。

**请求内容 (Payload)**：

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**响应 (Response)**：

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

列出已配置的 LLM 提供商的可用模型。

**请求内容 (Payload)**：

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**响应 (Response)**：

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

## 日志文件

所有日志存放于：

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

文件名格式为：`comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

系统会自动保留最新的 10 个日志文件（可透过 `config.json` 调整）。

---

## 配置参数

建立 `config.json` 可自定义以下行为：

```json
{
  "max_log_files": 10,           // 最多保留几个日志文件
  "buffer_limit": 100,            // Traceback 缓冲区大小（行数）
  "traceback_timeout_seconds": 5.0,  // Traceback 超时秒数
  "history_size": 20,             // 错误历史记录数量
  "default_language": "zh_TW",    // 默认语系
  "enable_api": true,             // 启用 API 端点
  "privacy_mode": "basic"         // 隐私模式: "none"、"basic" (默认)、"strict"
}
```

**参数说明**：

- `max_log_files`: 最多保留几个日志文件
- `buffer_limit`: Traceback 缓冲区大小（行数）
- `traceback_timeout_seconds`: Traceback 超时秒数
- `history_size`: 错误历史记录数量
- `default_language`: 默认语系
- `enable_api`: 启用 API 端点
- `privacy_mode`: PII 净化等级 - `"none"`、`"basic"` (默认) 或 `"strict"` (详见上方隐私模式说明)

## 支持的错误模式

ComfyUI-Doctor 可侦测并提供以下建议：

- 格式类型不符（如 fp16 vs float32）
- 维度不匹配
- CUDA/MPS 内存不足 (OOM)
- 矩阵乘法错误
- 装置/类型冲突
- 缺少 Python 模块
- Assertion 失败
- Key/Attribute 错误
- Tensor 形状不匹配
- 找不到文件
- SafeTensors 加载错误
- CUDNN 执行失败
- 缺少 InsightFace 函式库
- Model/VAE 不匹配
- 无效的 Prompt JSON

等等...

## 使用技巧

1. **搭配 ComfyUI Manager**：自动安装缺少的自定义节点
2. **查看日志文件**：问题回报时，完整的 Traceback 都有记录
3. **使用内置侧边栏**：点击左侧菜单的 🏥 Doctor 图标，实时查看诊断
4. **节点除错**：怀疑哪个节点有问题，就将除错节点串接上去检视数据

## 授权

MIT License

## 贡献

欢迎提交各种 feedback：

**回报问题**：发现 bug 或有任何建议？请在 GitHub 上提交 issue。
**提交 PR**：透过修复 bug 或进行常规优化来帮助我们完善代码库。
**功能请求**：有其他需求、或新功能的好点子？请透过 GitHub issues 告诉我们。
