# ComfyUI-Doctor

[繁體中文](README.zh-TW.md) | English | [Roadmap & Development Status](ROADMAP.md)

A continuous, real-time runtime diagnostics suite for ComfyUI featuring **LLM-powered analysis**, **interactive debugging chat**, and **50+ fix patterns**. Automatically intercepts all terminal output from startup, captures complete Python tracebacks, and delivers prioritized fix suggestions with node-level context extraction. Now supports **JSON-based pattern management** with hot-reload and **full i18n support** for 9 languages (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

---

## Latest Updates (Jan 2026)

<details>
<summary><strong>T8: Pattern Validation CI </strong> - Click to expand</summary>

**Automated quality checks now protect pattern integrity!**

ComfyUI-Doctor now includes **continuous integration testing** for all error patterns, ensuring zero-defect contributions.

**What T8 Validates**:

- ✅ **JSON Format**: All 8 pattern files compile correctly
- ✅ **Regex Syntax**: All 57 patterns have valid regular expressions  
- ✅ **i18n Completeness**: 100% translation coverage (57 patterns × 9 languages = 513 checks)
- ✅ **Schema Compliance**: Required fields (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Metadata Quality**: Valid priority ranges (50-95), unique IDs, correct categories

**GitHub Actions Integration**:

- Triggers on every push/PR affecting `patterns/`, `i18n.py`, or tests
- Runs in ~3 seconds with $0 cost (GitHub Actions free tier)
- Blocks merges if validation fails

**For Contributors**:

```bash
# Local validation before commit
python run_pattern_tests.py

# Output:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (9 languages total)
```

**Test Results**: 100% pass rate across all checks

**Implementation Details**: See `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

---

<details>
<summary><strong>Phase 4B: Pattern System Overhaul (STAGE 1-3 Complete)</strong> - Click to expand</summary>

ComfyUI-Doctor has undergone a major architecture upgrade with **57+ error patterns** and **JSON-based pattern management**!

**STAGE 1: Logger Architecture Fix**

- Implemented SafeStreamWrapper with queue-based background processing
- Eliminated deadlock risks and race conditions
- Fixed log interception conflicts with ComfyUI's LogInterceptor

**STAGE 2: JSON Pattern Management (F2)**

- New PatternLoader with hot-reload capability (no restart needed!)
- Patterns now defined in JSON files under `patterns/` directory
- 22 builtin patterns in `patterns/builtin/core.json`
- Easy to extend and maintain

**STAGE 3: Community Pattern Expansion (F12)**

- **35 new community patterns** covering popular extensions:
  - **ControlNet** (8 patterns): Model loading, preprocessing, image sizing
  - **LoRA** (6 patterns): Loading errors, compatibility, weight issues
  - **VAE** (5 patterns): Encoding/decoding failures, precision, tiling
  - **AnimateDiff** (4 patterns): Model loading, frame count, context length
  - **IPAdapter** (4 patterns): Model loading, image encoding, compatibility
  - **FaceRestore** (3 patterns): CodeFormer/GFPGAN models, detection
  - **Miscellaneous** (5 patterns): Checkpoints, samplers, schedulers, CLIP
- Full i18n support for English, Traditional Chinese, and Simplified Chinese
- Total: **57 error patterns** (22 builtin + 35 community)

**Benefits**:

- ✅ More comprehensive error coverage
- ✅ Hot-reload patterns without restarting ComfyUI
- ✅ Community can contribute patterns via JSON files
- ✅ Cleaner, more maintainable codebase

</details>

---

<details>
<summary><strong>Previous Updates (Dec 2025)</strong> - Click to expand</summary>

### F9: Multi-language Support Expansion

We've expanded language support from 4 to 9 languages! ComfyUI-Doctor now provides error suggestions in:

- **English** (en)
- **繁體中文** Traditional Chinese (zh_TW)
- **简体中文** Simplified Chinese (zh_CN)
- **日本語** Japanese (ja)
- **🆕 Deutsch** German (de)
- **🆕 Français** French (fr)
- **🆕 Italiano** Italian (it)
- **🆕 Español** Spanish (es)
- **🆕 한국어** Korean (ko)

All 57 error patterns are fully translated across all languages, ensuring consistent diagnostic quality worldwide.

### F8: Sidebar Settings Integration

Settings have been streamlined! Configure Doctor directly from the sidebar:

- Click the ⚙️ icon in the sidebar header to access all settings
- Language selection (9 languages)
- AI Provider quick-switch (OpenAI, DeepSeek, Groq, Gemini, Ollama, etc.)
- Base URL auto-fill when changing providers
- API Key management (password-protected input)
- Model name configuration
- Settings persist across sessions with localStorage
- Visual feedback on save (✅ Saved! / ❌ Error)

ComfyUI Settings panel now only shows the Enable/Disable toggle - all other settings moved to the sidebar for a cleaner, more integrated experience.

</details>

---

## Features

- **Automatic Error Monitoring**: Captures all terminal output and detects Python tracebacks in real-time
- **Intelligent Error Analysis**: 57+ error patterns (22 builtin + 35 community) with actionable suggestions
- **Node Context Extraction**: Identifies which node caused the error (Node ID, Name, Class)
- **System Environment Context**: Automatically includes Python version, installed packages (pip list), and OS info in AI analysis
- **Multi-language Support**: 9 languages supported (English, 繁體中文, 简体中文, 日本語, Deutsch, Français, Italiano, Español, 한국어)
- **JSON-based Pattern Management**: Hot-reload error patterns without restarting ComfyUI
- **Community Pattern Support**: Covers ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, and more
- **Debug Inspector Node**: Deep inspection of data flowing through your workflow
- **Error History**: Maintains a buffer of recent errors via API
- **RESTful API**: Seven endpoints for frontend integration
- **AI-Powered Analysis**: One-click LLM error analysis with support for 8+ providers (OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio, and more)
- **Interactive Chat Interface**: Multi-turn AI debugging assistant integrated into ComfyUI sidebar
- **Interactive Sidebar UI**: Visual error panel with node location and instant diagnostics
- **Flexible Configuration**: Comprehensive settings panel for behavior customization

### 🆕 AI Chat Interface

The new interactive chat interface provides a conversational debugging experience directly within ComfyUI's left sidebar. When an error occurs, simply click "Analyze with AI" to start a multi-turn conversation with your preferred LLM.

<div align="center">
<img src="assets/chat-ui.png" alt="AI Chat Interface">
</div>

**Key Features:**

- **Context-Aware**: Automatically includes error details, node information, and workflow context
- **Environment-Aware**: Includes Python version, installed packages, and OS info for accurate debugging
- **Streaming Responses**: Real-time LLM responses with proper formatting
- **Multi-Turn Conversations**: Ask follow-up questions to dig deeper into issues
- **Always Accessible**: Input area stays visible at the bottom with sticky positioning
- **Supports 8+ LLM Providers**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio, and more
- **Smart Caching**: Package list cached for 24 hours to avoid performance impact

**How to Use:**

1. When an error occurs, open the Doctor sidebar (left panel)
2. Click the "✨ Analyze with AI" button in the error context area
3. The AI will automatically analyze the error and provide suggestions
4. Continue the conversation by typing follow-up questions in the input box
5. Press Enter or click "Send" to submit your message

> **💡 Free API Tip**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) offers a generous free tier with no credit card required. Perfect for getting started with AI-powered debugging without any costs!

---

## Installation

1. Navigate to your ComfyUI custom nodes directory:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clone or download this repository:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. Restart ComfyUI

4. Look for the initialization message in the console:

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

---

## Usage

### Passive Mode (Automatic)

Once installed, ComfyUI-Doctor automatically:

- Records all console output to `logs/` directory
- Detects errors and provides suggestions
- Logs system environment information

**Example Error Output**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory): Your GPU VRAM is full. Try:
   1. Reducing Batch Size
   2. Using '--lowvram' flag
   3. Closing other GPU apps
----------------------------------------
```

### Active Mode (Debug Node)

1. Right-click on the canvas → `Add Node` → `Smart Debug Node`
2. Connect the node inline with any connection (supports wildcard input `*`)
3. Execute your workflow

**Example Output**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

The node passes data through without affecting workflow execution.

---

## Frontend UI

ComfyUI-Doctor provides an interactive sidebar interface for real-time error monitoring and diagnostics.

### Accessing the Doctor Panel

Click the **🏥 Doctor** button in the ComfyUI menu (left sidebar) to open the Doctor panel. The panel slides in from the right side of the screen.

### Interface Features

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Error Report">
</div>

The Doctor interface consists of two panels:

#### Left Sidebar Panel (Doctor Sidebar)

Click the **🏥 Doctor** icon in ComfyUI's left menu to access:

- **Settings Panel** (⚙️ icon): Configure language, AI provider, API keys, and model selection
- **Error Context Card**: When an error occurs, displays:
  - **💡 Suggestion**: Concise, actionable advice (e.g., "Check input connections and ensure node requirements are met.")
  - **Timestamp**: When the error occurred
  - **Node Context**: Node ID and name (if applicable)
  - **✨ Analyze with AI**: Launch interactive chat for detailed debugging
- **AI Chat Interface**: Multi-turn conversation with your LLM for in-depth error analysis
- **Sticky Input Area**: Always accessible at bottom for follow-up questions

#### Right Error Panel (Latest Diagnosis)

Real-time error notifications in the top-right corner:

![Doctor Error Report](./assets/error-report.png)

- **Status Indicator**: Colored dot showing system health
  - 🟢 **Green**: System running normally, no errors detected
  - 🔴 **Red (pulsing)**: Active error detected
- **Latest Diagnosis Card**: Displays the most recent error with:
  - **Error Summary**: Brief error description (red-themed, collapsible for long errors)
  - **💡 Suggestion**: Concise actionable advice (green-themed)
  - **Timestamp**: When the error occurred
  - **Node Context**: Node ID, name, and class
  - **🔍 Locate Node on Canvas**: Automatically centers and highlights the problematic node

**Key Design Principles**:

- ✅ **Concise Suggestions**: Only the actionable advice is shown (e.g., "Check input connections...") instead of verbose error descriptions
- ✅ **Visual Separation**: Error messages (red) and suggestions (green) are clearly distinguished
- ✅ **Smart Truncation**: Long errors show first 3 + last 3 lines with collapsible full details
- ✅ **Real-time Updates**: Both panels automatically update when new errors occur via WebSocket events

---

## AI-Powered Error Analysis

ComfyUI-Doctor integrates with popular LLM services to provide intelligent, context-aware debugging suggestions.

### Supported AI Providers

#### Cloud Services

- **OpenAI** (GPT-4, GPT-4o, etc.)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - ultra-fast LPU inference)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Access to Claude, GPT-4, and 100+ models)

#### Local Services (No API Key Required)

- **Ollama** (`http://127.0.0.1:11434`) - Run Llama, Mistral, CodeLlama locally
- **LMStudio** (`http://localhost:1234/v1`) - Local model inference with GUI

> **💡 Cross-Platform Compatibility**: Default URLs can be overridden via environment variables:
>
> - `OLLAMA_BASE_URL` - Custom Ollama endpoint (default: `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - Custom LMStudio endpoint (default: `http://localhost:1234/v1`)
>
> This prevents conflicts between Windows and WSL2 Ollama instances, or when running in Docker/custom setups.

### Configuration

![Settings Panel](./assets/settings.png)

Configure AI analysis in the **Doctor Sidebar** → **Settings** panel:

1. **AI Provider**: Select from the dropdown menu. The Base URL will auto-fill.
2. **AI Base URL**: The API endpoint (auto-populated, but customizable)
3. **AI API Key**: Your API key (leave empty for local LLMs like Ollama/LMStudio)
4. **AI Model Name**:
   - Select a model from the dropdown list (automatically populated from your provider's API)
   - Click the 🔄 refresh button to reload available models
   - Or check "Enter model name manually" to type a custom model name
5. **Privacy Mode**: Select PII sanitization level for cloud AI services (see [Privacy Mode (PII Sanitization)](#privacy-mode-pii-sanitization) section below for details)

### Using AI Analysis

1. Automatically opens the Doctor panel when an error occurs.
2. Review the built-in suggestions, or click the ✨ Analyze with AI button on the error card.
3. Wait for the LLM to analyze the error (typically 3-10 seconds).
4. Review the AI-generated debugging suggestions.

**Security Note**: Your API key is transmitted securely from frontend to backend for the analysis request only. It is never logged or stored persistently.

### Privacy Mode (PII Sanitization)

ComfyUI-Doctor includes automatic **PII (Personally Identifiable Information) sanitization** to protect your privacy when sending error messages to cloud AI services.

**Three Privacy Levels**:

| Level | Description | What is Removed | Recommended For |
| ----- | ----------- | --------------- | --------------- |
| **None** | No sanitization | Nothing | Local LLMs (Ollama, LMStudio) |
| **Basic** (Default) | Standard protection | User paths, API keys, emails, IP addresses | Most users with cloud LLMs |
| **Strict** | Maximum privacy | All of Basic + IPv6, SSH fingerprints | Enterprise/compliance requirements |

**What is Sanitized** (Basic Level):

- ✅ Windows user paths: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOS home: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API keys: `sk-abc123...` → `<API_KEY>`
- ✅ Email addresses: `user@example.com` → `<EMAIL>`
- ✅ Private IPs: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ URL credentials: `https://user:pass@host` → `https://<USER>@host`

**What is NOT Removed**:

- ❌ Error messages (needed for debugging)
- ❌ Model names, node names
- ❌ Workflow structure
- ❌ Public file paths (`/usr/bin/python`)

**Configure Privacy Mode**: Open Doctor Sidebar → Settings → 🔒 Privacy Mode dropdown. Changes apply immediately to all AI analysis requests.

**GDPR Compliance**: This feature supports GDPR Article 25 (Data Protection by Design) and is recommended for enterprise deployments.

### Example Providers Setup

| Provider         | Base URL                                                   | Model Example                |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI           | `https://api.openai.com/v1`                                | `gpt-4o`                     |
| DeepSeek         | `https://api.deepseek.com/v1`                              | `deepseek-chat`              |
| Groq             | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`    |
| Gemini           | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`           |
| Ollama (Local)   | `http://localhost:11434/v1`                                | `llama3.1:8b`                |
| LMStudio (Local) | `http://localhost:1234/v1`                                 | Model loaded in LMStudio     |

---

## Settings

You can customize ComfyUI-Doctor behavior via the ComfyUI Settings panel (Gear icon).

### 1. Show error notifications

**Function**: Toggle floating error notification cards (toasts) in the top-right corner.
**Usage**: Disable if you prefer to check errors manually in the sidebar without visual interruptions.

### 2. Auto-open panel on error

**Function**: Automatically expands the Doctor sidebar when a new error is detected.
**Usage**: **Recommended**. Provides immediate access to diagnostic results without manual clicking.

### 3. Error Check Interval (ms)

**Function**: Frequency of frontend-backend error checks (in milliseconds). Default: `2000`.
**Usage**: Lower values (e.g., 500) give faster feedback but increase load; higher values (e.g., 5000) save resources.

### 4. Suggestion Language

**Function**: Language for diagnostic reports and Doctor suggestions.
**Usage**: Currently supports English, Traditional Chinese, Simplified Chinese, and Japanese (more coming soon). Changes apply to new errors.

### 5. Enable Doctor (requires restart)

**Function**: Master switch for the log interception system.
**Usage**: Turn off to completely disable Doctor's core functionality (requires ComfyUI restart).

### 6. AI Provider

**Function**: Select your preferred LLM service provider from a dropdown menu.
**Options**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Local), LMStudio (Local), Custom.
**Usage**: Selecting a provider automatically fills in the appropriate Base URL. For local providers (Ollama/LMStudio), an alert displays available models.

### 7. AI Base URL

**Function**: The API endpoint for your LLM service.
**Usage**: Auto-populated when you select a provider, but can be customized for self-hosted or custom endpoints.

### 8. AI API Key

**Function**: Your API key for authentication with cloud LLM services.
**Usage**: Required for cloud providers (OpenAI, DeepSeek, etc.). Leave empty for local LLMs (Ollama, LMStudio).
**Security**: The key is only transmitted during analysis requests and is never logged or persisted.

### 9. AI Model Name

**Function**: Specify which model to use for error analysis.
**Usage**:

- **Dropdown Mode** (default): Select a model from the automatically-populated dropdown list. Click the 🔄 refresh button to reload available models.
- **Manual Input Mode**: Check "Enter model name manually" to type a custom model name (e.g., `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- Models are automatically fetched from your selected provider's API when you change providers or click refresh.
- For local LLMs (Ollama/LMStudio), the dropdown displays all locally available models.

---

## API Endpoints

### GET `/debugger/last_analysis`

Retrieve the most recent error analysis:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**Response Example**:

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja"],
  "last_error": "Traceback...",
  "suggestion": "SUGGESTION: ...",
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

Retrieve error history (last 20 entries):

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

Change the suggestion language (see Language Switching section).

### POST `/doctor/analyze`

Analyze an error using configured LLM service.

**Payload**:

```json
{
  "error": "Traceback...",
  "node_context": {...},
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "en"
}
```

**Response**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

Verify API key validity by testing connection to the LLM provider.

**Payload**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**Response**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

List available models from the configured LLM provider.

**Payload**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**Response**:

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

## Log Files

All logs are stored in:

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

Filename format: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

The system automatically retains the 10 most recent log files (configurable via `config.json`).

---

## Configuration

Create `config.json` to customize behavior:

```json
{
  "max_log_files": 10,
  "buffer_limit": 100,
  "traceback_timeout_seconds": 5.0,
  "history_size": 20,
  "default_language": "zh_TW",
  "enable_api": true,
  "privacy_mode": "basic"
}
```

**Parameters**:

- `max_log_files`: Maximum number of log files to retain
- `buffer_limit`: Traceback buffer size (line count)
- `traceback_timeout_seconds`: Timeout for incomplete tracebacks
- `history_size`: Number of errors to keep in history
- `default_language`: Default suggestion language
- `enable_api`: Enable API endpoints
- `privacy_mode`: PII sanitization level - `"none"`, `"basic"` (default), or `"strict"` (see Privacy Mode section above)

---

## Supported Error Patterns

ComfyUI-Doctor can detect and provide suggestions for:

- Type mismatches (e.g., fp16 vs float32)
- Dimension mismatches
- CUDA/MPS out of memory
- Matrix multiplication errors
- Device/type conflicts
- Missing Python modules
- Assertion failures
- Key/attribute errors
- Shape mismatches
- File not found errors
- SafeTensors loading errors
- CUDNN execution failures
- Missing InsightFace library
- Model/VAE mismatches
- Invalid prompt JSON

And more...

---

## Tips

1. **Pair with ComfyUI Manager**: Install missing custom nodes automatically
2. **Check log files**: Full tracebacks are recorded for issue reporting
3. **Use the built-in sidebar**: Click the 🏥 Doctor icon in the left menu for real-time diagnostics
4. **Node Debugging**: Connect Debug nodes to inspect suspicious data flow

---

## License

MIT License

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## Support

If you encounter any issues or have suggestions, please open an issue on GitHub.
