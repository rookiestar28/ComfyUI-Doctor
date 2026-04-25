# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | 简中 | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor 是 ComfyUI 的实时诊断与调试助手。它会捕获运行时错误、识别可能的节点上下文、显示本地修复建议，并可选择使用 LLM 对话流程进行更深入的错误分析。

## 最新状态

- 已加入宿主兼容性检查，覆盖 Doctor 依赖的 ComfyUI、ComfyUI frontend 与 Desktop 接口。
- 前端设置整合已对齐当前 ComfyUI settings API，旧版 fallback 已集中隔离。
- 执行错误可从近期 execution/progress 事件补强节点 lineage。
- Shared server 可启用严格 admin token 模式；单机 loopback convenience mode 会提供更清楚的提示。
- Server-side credential store 支持加密存储与 encrypt-then-MAC 文档说明。
- 新增可选 coverage baseline lane；默认完整验证流程不变。

## 核心功能

- 从 ComfyUI 启动阶段开始监控 console 与 traceback。
- 58 个 JSON 错误模式，包含 22 个核心模式与 36 个社区 extension 模式。
- 根据宿主事件数据提取节点 ID、名称、类别与 custom-node path。
- Doctor sidebar 提供 Chat、Statistics、Settings 三个主要分页。
- 支持 OpenAI-compatible、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio 等 LLM 工作流程。
- 隐私模式可在发送 LLM 请求前遮蔽路径、credential-looking values、email、private IP 等内容。
- 可选 admin-gated server-side credential store，并支持 encryption-at-rest。
- 内置 diagnostics、statistics、plugin trust report、telemetry controls 与 community feedback preview/submit。
- 支持英文、繁中、简中、日文、韩文、德文、法文、意大利文、西班牙文。

## 安装

### ComfyUI-Manager

1. 打开 ComfyUI，点击 **Manager**。
2. 选择 **Install Custom Nodes**。
3. 搜索 `ComfyUI-Doctor`。
4. 安装后重启 ComfyUI。

### 手动安装

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

重启 ComfyUI 后，左侧 sidebar 应出现 **Doctor** 入口。

## 基本使用

- **自动诊断**：Doctor 会自动捕获错误、匹配已知模式，并显示最新诊断。
- **Doctor Sidebar**：Chat 查看最新错误并进行 LLM 对话；Statistics 查看趋势、诊断与健康信息；Settings 管理语言、Provider、Model、Privacy Mode 与 credential 来源。
- **Smart Debug Node**：可插入 workflow 连接中检查数据类型、shape、dtype、device 与数值统计，且不改变数据输出。

## 文档

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## 验证

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## 许可证

MIT License
