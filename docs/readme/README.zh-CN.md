# ComfyUI-Doctor

[繁中](README.zh-TW.md) | 简中 | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor 是 ComfyUI 的实时诊断与调试助手。它会捕获运行时错误、识别可能相关的节点上下文、显示可执行的本地建议，并可选择使用 LLM 聊天流程进行更深入的排查。

## 最新更新

最新更新内容以英文 README 为准，请参阅 [Latest Updates](../../README.md#latest-updates---click-to-expand)。

## 核心功能

- 从启动阶段开始实时捕获 ComfyUI console/error 输出。
- 内置 58 个基于 JSON 的错误模式建议，包含 22 个核心模式与 36 个社区扩展模式。
- 当 ComfyUI 提供足够事件数据时，可针对近期 workflow 执行错误提取并验证节点上下文。
- Doctor 侧边栏包含 Chat、Statistics、Settings 选项卡。
- 可选用 OpenAI-compatible services、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio 进行 LLM 分析，并使用统一的 provider request/response 处理。
- 对外 LLM 请求具备隐私控制，包含路径、密钥、邮箱、IP 的清理模式。
- 可选用服务器端凭据存储，支持 admin guard 与静态加密存储。
- 提供本地诊断、统计、plugin trust report、telemetry 控制，以及社区反馈预览/提交工具。
- Doctor API 失败响应采用一致的 JSON error envelope。
- UI 与建议完整支持英文、繁体中文、简体中文、日文、韩文、德文、法文、意大利文、西班牙文。

## 截图

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## 安装

### ComfyUI-Manager

1. 打开 ComfyUI 并点击 **Manager**。
2. 选择 **Install Custom Nodes**。
3. 搜索 `ComfyUI-Doctor`。
4. 安装后重启 ComfyUI。

### 手动安装

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Clone 完成后重启 ComfyUI。Doctor 应会输出启动诊断信息，并注册 `Doctor` 侧边栏入口。

## 基本使用

### 自动诊断

安装后，Doctor 会被动记录 ComfyUI 运行时输出、检测 traceback、匹配已知错误模式，并在侧边栏与可选的右侧报告面板显示最新诊断。
使用可选 LLM 分析时，Doctor 会通过同一个结构化 pipeline 构建 prompt context；该 pipeline 负责清理敏感信息、节点上下文、执行日志、workflow pruning 与系统信息。

### Doctor 侧边栏

在 ComfyUI 左侧侧边栏打开 **Doctor**：

- **Chat**：查看最新错误上下文，并提出后续调试问题。
- **Statistics**：查看近期错误趋势、诊断信息、信任/健康状态、telemetry 控制与反馈工具。
- **Settings**：选择语言、LLM provider、base URL、model、隐私模式、自动打开行为，以及可选的服务器端凭据存储。

### Smart Debug Node

在 canvas 上右键，添加 **Smart Debug Node**，并将其放入 workflow 中检查流经的数据，而不改变 workflow 输出。

## 可选 LLM 设置

云端 provider 需要通过 session-only UI 字段、环境变量，或可选的 admin-gated server store 提供凭据。Ollama 与 LMStudio 等本地 provider 可在没有云端凭据的情况下运行。
Doctor 会标准化 OpenAI-compatible APIs、Anthropic、Ollama 的 provider-specific request/response 格式，让 chat、single-shot analysis、model listing、connectivity check 共用一致的后端行为。

推荐默认值：

- 对云端 provider 使用 **Privacy Mode: Basic** 或 **Strict**。
- 在共享或类 production 环境中使用环境变量。
- 在共享服务器上设置 `DOCTOR_ADMIN_TOKEN` 与 `DOCTOR_REQUIRE_ADMIN_TOKEN=1`。
- 只在单用户桌面环境中保留 local-only loopback convenience mode。

## 文档

- [User Guide](../USER_GUIDE.md)：UI 导览、诊断、隐私模式、LLM 设置与反馈流程。
- [Configuration and Security](../CONFIGURATION_SECURITY.md)：环境变量、admin guard 行为、凭据存储、outbound safety、telemetry 与 CSP 注意事项。
- [API Reference](../API_REFERENCE.md)：公开的 Doctor 与 debugger endpoints。
- [Validation Guide](../VALIDATION.md)：本地 full-gate 命令与可选的兼容性/coverage lanes。
- [Plugin Guide](../PLUGIN_GUIDE.md)：社区 plugin trust model 与 plugin authoring notes。
- [Plugin Migration](../PLUGIN_MIGRATION.md)：plugin manifest 与 allowlist 的 migration tooling。
- [Outbound Safety](../OUTBOUND_SAFETY.md)：static checker 与 outbound request safety rules。

## 支持的错误模式

错误模式以 JSON 文件存放于 `patterns/`，可在不修改代码的情况下更新。

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

社区 pack 目前涵盖常见的 ControlNet、LoRA、VAE、AnimateDiff、IPAdapter、FaceRestore、checkpoint、sampler、scheduler 与 CLIP 失败模式。

## 验证

若要执行本地 CI-parity 验证，请使用项目 full-test script：

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Full gate 会覆盖 secrets detection、pre-commit hooks、host-like startup validation、backend unit tests 与 frontend Playwright E2E tests。明确的分阶段命令与可选 lanes 请参阅 [Validation Guide](../VALIDATION.md)。

## 要求

- ComfyUI custom-node 环境。
- Python 3.10 或更新版本。
- 只有 frontend E2E validation 需要 Node.js 18 或更新版本。
- 除 ComfyUI 内置环境与 Python standard library 之外，不需要额外 runtime Python package dependency。

## 许可证

MIT License

## 贡献

欢迎提交错误模式与文档贡献。若要修改代码，请在开启 pull request 前执行完整 validation gate，并避免提交生成的本地状态、日志、凭据或内部规划文件。
