# ComfyUI-Doctor

[繁中](docs/readme/README.zh-TW.md) | [简中](docs/readme/README.zh-CN.md) | [日本語](docs/readme/README.ja.md) | [한국어](docs/readme/README.ko.md) | [Deutsch](docs/readme/README.de.md) | [Français](docs/readme/README.fr.md) | [Italiano](docs/readme/README.it.md) | [Español](docs/readme/README.es.md) | English |

<div align="center">
<img src="assets/icon.png" alt="ComfyUI Doctor">
</div>

A continuous, real-time runtime diagnostics suite for ComfyUI featuring **LLM-powered analysis**, **interactive debugging chat**, and **50+ fix patterns**. Automatically intercepts all terminal output from startup, captures complete Python tracebacks, and delivers prioritized fix suggestions with node-level context extraction. Now supports **JSON-based pattern management** with hot-reload and **full i18n support** for 9 languages (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

<details> <summary><h2>Latest Updates - Click to expand</h2></summary>

<details>
<summary><strong>Security Hardening Refresh (Admin Gate + Network Boundary + Secret Storage)</strong></summary>

- Consolidated write-sensitive API routes under a unified admin guard path so state-changing operations consistently require authorized access.
- Strengthened outbound URL safety with DNS-resolution checks to block hostname-based private/metadata target rebinding attempts.
- Upgraded server-side secret storage with optional at-rest encryption, safer migration behavior for existing plaintext files, and stronger Windows ACL hardening behavior.
- Hardened outbound proxy trust defaults: shared HTTP sessions now ignore ambient proxy environment variables unless explicitly opted in, and effective policy is exposed in health diagnostics.

</details>

<details>
<summary><strong>Data-Driven Diagnostics Signature Packs</strong></summary>

- Added JSON-based signature packs for proactive diagnostics so heuristic rule updates can be maintained as data instead of code-only changes.
- Added bounded, local-only diagnostic enrichment for common ComfyUI workflow issues (model path anomalies, missing assets/placeholders, node config anti-patterns, and environment mismatch hints).
- Diagnostics issues can now include machine-readable confidence and provenance metadata for signature-pack matches.

</details>

<details>
<summary><strong>Validation Expansion Remediation: Desktop Hardening + Isolation Test Pack</strong></summary>

- Added targeted desktop failure-injection regression tests for corrupt state recovery, flush-failure non-crash paths, and history migration continuity.
- Added non-ComfyUI isolation coverage for metadata contract validation and PromptComposer/harness payload compatibility.
- Added an opt-in online API test lane scaffold (`RUN_ONLINE_API_TESTS=true`) to separate secret-scoped provider checks from default local runs.
- Validation gate status: detect-secrets + pre-commit + backend full pytest + frontend E2E passed; online provider smoke tests remain opt-in/secret-scoped and skip safely when credentials are absent.

</details>

<details>
<summary><strong>Validation Expansion Foundation: Runtime Guardrail Config (partial rollout)</strong></summary>

- Added centralized runtime guardrail configuration (ENV-driven) for history limits, job retention, aggregation/rate windows, and provider timeout/retry defaults.
- Applied initial runtime wiring for stale job cleanup retention while keeping default behavior unchanged for existing users.
- Hardened config persistence by treating guardrails as runtime-only policy (excluded from `config.json`) with compatibility handling for legacy payloads.
- Added regression tests for defaults, ENV override precedence, runtime-only persistence, and config loader compatibility.

</details>

<details>
<summary><strong>External Enrichment Safety Foundation + Resumable Job APIs</strong></summary>

- Added a fail-closed external enrichment foundation with provider contract/capability registry, submission policy checks, confirmation tokens, and redacted audit logging.
- Added resumable, checkpointed long-job APIs (job status/resume/cancel + provider status) with corruption-tolerant state handling.
- Hardened route wiring and integrated non-stream output cleanup for `/doctor/analyze` and non-stream `/doctor/chat` to reduce hidden marker leakage.
- Added dedicated regression coverage for policy engine, adapter behavior, resumable jobs, contract normalization, and API routes.

</details>

<details>
<summary><strong>(v1.6.3): Dual-Mode API Key Strategy (ENV-first + Advanced Server Key Store)</strong></summary>

- API keys are no longer persisted in frontend settings; the API key input is session-only by default.
- Added a default-collapsed **🔐 Advanced Key Store (Server-side)** section for explicit save/delete actions.
- Backend key resolution order is now: request key → provider ENV → generic ENV → optional server store.
- Existing users with legacy frontend-stored keys are auto-migrated once to runtime memory, then the persisted key is cleared.
- UI now includes inline risk guidance (`?`) warning that server store uses plaintext `secrets.json`; ENV keys remain the recommended path.

</details>

<details>
<summary><strong>Proactive Diagnostics (Health Check + Intent Signature)</strong></summary>

- Added a **Diagnostics** section to the **Statistics** tab for proactive workflow troubleshooting (no LLM required).
- **Health checks**: workflow lint + environment/deps + privacy/safety checks, with actionable issues.
- **Intent Signature (ISS)**: deterministic intent inference with **top intents + evidence** to help triage what the workflow is “trying to do”.
- Includes UX hardening: safe fallbacks (e.g. “No dominant intent detected”) and improved evidence sanitization.

</details>

<details>
<summary><strong>(v1.5.8) QoL: Auto-open Right Error Report Panel Toggle</strong></summary>

- Added a **dedicated toggle** in **Doctor → Settings** to control whether the **right-side error report panel** auto-opens when a new error is detected.
- **Default: ON** for new installs, and the choice is persisted.

</details>

<details>
<summary><strong> (v1.5.0) Smart Token Budget Management</strong></summary>

**Smart Context Management (Cost Optimization):**

- **Automatic trimming** for remote LLMs (60-80% token reduction)
- **Progressive strategy**: workflow pruning → system info removal → traceback truncation
- **Local Opt-in**: Gentle trimming for Ollama/LMStudio (12K/16K limits)
- **Enhanced Observability**: Step-by-step token tracking & A/B validation harness

**Network Resilience:**

- **Exponential Backoff**: Automatic retry for 429/5xx errors with jitter
- **Streaming Protection**: 30s timeout watchdog for stalled SSE chunks
- **Rate & Concurrency Limits**: Token bucket (30/min) + Concurrency semaphore (max 3)

**New Configuration:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | Enable Smart Budget (Remote) |
| `retry_max_attempts` | `3` | Max retry attempts |
| `stream_chunk_timeout` | `30` | Stream stall timeout (sec) |

</details>

<details>
<summary><strong>(v1.4.5) Major Fix: Pipeline Governance & Plugin Security</strong></summary>

**Security Hardening:**

- **SSRF Protection++**: Replaced substring checks with host/port parsing; blocked outbound redirects (`allow_redirects=False`)
- **Outbound Sanitization Funnel**: Single boundary (`outbound.py`) ensuring all external payloads are sanitized; `privacy_mode=none` only for verified local LLMs

**Plugin Trust System:**

- **Safe-by-default**: Plugins disabled by default, requires explicit allowlist + manifest/SHA256
- **Trust Taxonomy**: `trusted | unsigned | untrusted | blocked` classification
- **Filesystem Hardening**: realpath containment, symlink rejection, size limits, strict filename rules
- **Optional HMAC Signature**: Shared-secret integrity verification (not public-key signing)

**Pipeline Governance:**

- **Metadata Contract**: Schema versioning + end-of-run validation + quarantine for invalid keys
- **Dependency Policy**: `requires/provides` enforcement; missing deps → stage skipped, status `degraded`
- **Logger Backpressure**: `DroppingQueue` with priority-aware eviction + drop metrics
- **Prestartup Handoff**: Clean logger uninstall before SmartLogger takes over

**Observability:**

- `/doctor/health` endpoint with queue metrics, drop counters, SSRF blocks, pipeline status

**Test Results**: 159 Python tests passed | 17 Phase 2 gate tests

</details>

<details>
<summary><strong>Enhancement: CI Gates & Plugin Tooling</strong></summary>

**T11 - Phase 2 Release CI Gate:**

- GitHub Actions workflow (`phase2-release-gate.yml`) enforcing 4 pytest suites + E2E
- Local validator script (`scripts/phase2_gate.py`) with `--fast` and `--e2e` modes

**T12 - Outbound Safety Static Checker:**

- AST-based analyzer (`scripts/check_outbound_safety.py`) detecting bypass patterns
- 6 detection rules: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION`, etc.
- CI workflow + 8 unit tests + documentation (`docs/OUTBOUND_SAFETY.md`)

**A8 - Plugin Migration Tooling:**

- `scripts/plugin_manifest.py`: Generate manifest with SHA256 hash
- `scripts/plugin_allowlist.py`: Scan plugins and suggest config
- `scripts/plugin_validator.py`: Validate manifests and config
- `scripts/plugin_hmac_sign.py`: Optional HMAC signature generation
- Documentation: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md` updates

</details>

<details>
<summary><strong>Enhancement: CSP Documentation & Telemetry</strong></summary>

**S1 - CSP Compliance Documentation:**

- Verified all assets load locally (`web/lib/`); CDN URLs are fallback-only
- Added "CSP Compatibility" section to README
- Code audit complete (manual verification pending)

**S3 - Local Telemetry Infrastructure:**

- Backend: `telemetry.py` with TelemetryStore, RateLimiter, PII detection
- 6 API endpoints: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- Frontend: Statistics UI controls for telemetry management
- Security: Origin check (403 cross-origin), 1KB payload limit, field whitelist
- **Default OFF**: No recording/network until explicitly enabled
- 81 i18n strings (9 keys × 9 languages)

**Test Results**: 27 telemetry unit tests | 8 E2E tests

</details>

<details>
<summary><strong>Enhancement: E2E Runner Hardening & Trust/Health UI</strong></summary>

**E2E Runner Hardening (WSL `/mnt/c` Support):**

- Fixed Playwright transform cache permission issues on WSL
- Added writable temp dir under repo (`.tmp/playwright`)
- `PW_PYTHON` override for cross-platform compatibility

**Trust & Health UI Panel:**

- Added "Trust & Health" panel in Statistics tab
- Displays: pipeline_status, ssrf_blocked, dropped_logs
- Plugin trust list with badges and reasons
- `GET /doctor/plugins` scan-only endpoint (no code import)

**Test Results**: 61/61 E2E tests | 159/159 Python tests

</details>

<details>
<summary><strong> (v1.4.0) Previous Update</strong></summary>

- A7 Preact migration completed across Phases 5A–5C (Chat/Stats islands, registry, shared rendering, robust fallbacks).
- Integration hardening: strengthened Playwright E2E coverage.
- UI fixes: Sidebar tooltip timing.

</details>

<details>
<summary><strong>Statistics Dashboard</strong></summary>

**Track your ComfyUI stability at a glance!**

ComfyUI-Doctor now includes a **Statistics Dashboard** that provides insights into error trends, common issues, and resolution progress.

**Features**:

- 📊 **Error Trends**: Track errors across 24h/7d/30d time ranges
- 🔥 **Top 5 Patterns**: See which errors occur most frequently
- 📈 **Category Breakdown**: Visualize errors by category (Memory, Workflow, Model Loading, etc.)
- ✅ **Resolution Tracking**: Monitor resolved vs. unresolved errors
- 🌍 **Full i18n Support**: Available in all 9 languages

![Statistics Dashboard](assets/statistics_panel.png)

**How to Use**:

1. Open the Doctor sidebar panel (click the 🏥 icon on the left)
2. Expand the "📊 Error Statistics" section
3. View real-time error analytics and trends
4. Mark errors as resolved/ignored to track your progress

**Backend API**:

- `GET /doctor/statistics?time_range_days=30` - Fetch statistics
- `POST /doctor/mark_resolved` - Update resolution status

**Test Coverage**: 17/17 backend tests ✅ | 14/18 E2E tests (78% pass rate)

**Implementation Details**: See `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

<details>
<summary><strong>Pattern Validation CI </strong></summary>

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
python scripts/run_pattern_tests.py

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

<details>
<summary><strong>Pattern System Overhaul (STAGE 1-3 Complete)</strong></summary>

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

<details>
<summary><strong>Previous Updates (Dec 2025)</strong></summary>

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

</details>

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Frontend UI](#frontend-ui)
- [Settings](#settings)
- [External Enrichment Safety and Resumable Jobs](#external-enrichment-safety-and-resumable-jobs)
- [Data-Driven Diagnostics Signature Packs](#data-driven-diagnostics-signature-packs)
- [Quick Community Feedback (GitHub PR)](#quick-community-feedback-github-pr)
- [API Endpoints](#api-endpoints)
- [Supported Error Patterns](#supported-error-patterns)
- [Phase 2 Release Gate](#phase-2-release-gate)
- [CSP Compatibility](#csp-compatibility)
- [Contributing](#contributing)

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
- **RESTful API**: Expanded endpoint surface for analysis, diagnostics, telemetry, and resumable job control
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


## External Enrichment Safety and Resumable Jobs

ComfyUI-Doctor includes a fail-closed foundation for optional external enrichment providers.

### Safety Model

- **Read/query actions are allowed by default** for safe enrichment and diagnostics.
- **Submit/upload actions are blocked by default** and require explicit enablement per provider capability/policy.
- **Confirmation is required** for submit/upload paths (single-use, short-lived token).
- **Outbound sanitization remains mandatory** for provider-bound payloads.
- **Audit records are redacted** (provider/action/timestamp/policy decision + payload digest; no raw secrets/content).

### Resumable Job Foundation

- Long-running enrichment work uses checkpointed job state for interruption safety.
- Resume/cancel/status APIs support controlled recovery after restart/interruption.
- Checkpoint storage is corruption-tolerant (rotate/rebuild behavior).

### LLM Output Cleanup Scope

- Hidden-marker/non-user-facing output cleanup is enforced for:
  - `POST /doctor/analyze`
  - Non-stream `POST /doctor/chat`
- Streaming chunk-level cleanup remains a follow-up item by design.

## Installation

### Option 1: Using ComfyUI-Manager (Recommended)

1. Open ComfyUI and click the **Manager** button in the menu
2. Select **Install Custom Nodes**
3. Search for `ComfyUI-Doctor`
4. Click **Install** and restart ComfyUI

### Option 2: Manual Installation (Git Clone)

1. Navigate to your ComfyUI custom nodes directory:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clone this repository:

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

<img src="assets/settings.png" alt="side bar - settings">

Configure AI analysis in the **Doctor Sidebar** → **Settings** panel:

1. **AI Provider**: Select from the dropdown menu. The Base URL will auto-fill.
2. **AI Base URL**: The API endpoint (auto-populated, but customizable)
3. **AI API Key**: Session-only key input for cloud providers (leave empty for local LLMs like Ollama/LMStudio)
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

**Security Note**: API keys are **session-only** in the browser (cleared on reload). The backend resolves keys via this priority chain: request key → `DOCTOR_{PROVIDER}_API_KEY` → `DOCTOR_LLM_API_KEY` → optional server-side store (`secrets.json`). Keys are never logged and the server store is admin-gated. `secrets.json` is plaintext on disk (OS-permission protected), so for maximum security use environment variables.

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

### Statistics Dashboard

![Statistics Panel](assets/statistics_panel.png)

The **Statistics Dashboard** provides real-time insights into your ComfyUI error patterns and stability trends.

**Features**:

- **📊 Error Trends**: Total errors and counts for last 24h/7d/30d
- **🔥 Top Error Patterns**: Top 5 most frequent error types with occurrence counts
- **📈 Category Breakdown**: Visual breakdown by error category (Memory, Workflow, Model Loading, Framework, Generic)
- **✅ Resolution Tracking**: Track resolved, unresolved, and ignored errors
- **🧭 Status Controls**: Mark the latest error as Resolved / Unresolved / Ignored from the Stats tab
- **🩺 Diagnostics (F14)**: Proactive health checks + Intent Signature for the current workflow (no LLM required)
- **🛡️ Trust & Health**: View `/doctor/health` metrics and plugin trust report (scan-only)
- **📊 Anonymous Telemetry (Under Construction 🚧)**: Opt-in local-only buffer for usage events (toggle/view/clear/export)

**How to Use**:

1. Open the Doctor sidebar (click 🏥 icon on left)
2. Find the **📊 Error Statistics** collapsible section
3. Click to expand and view your error analytics
4. Use **Mark as** buttons to set the latest error status (Resolved / Unresolved / Ignored)
5. Scroll down to the bottom of the Statistics tab to find **Trust & Health** and **Anonymous Telemetry**

**Diagnostics (F14)**:

1. Open **Statistics** → **Diagnostics**
2. Click **Run / Refresh** to generate the report
3. Review issues and use actions (e.g. **Locate Node**, **Acknowledge / Ignore / Resolve**)

> Note: If you want the report text in another language, set **Suggestion Language** in **Settings** first.

#### Data-Driven Diagnostics Signature Packs

![Diagnostics](assets/Diagnostics.png)

The Diagnostics panel also supports **JSON-based signature packs** for maintainable heuristic checks that do not require an LLM call.

- **Data-driven rules**: Signature packs are versioned JSON files, making rule updates easier to review and maintain.
- **Local-only enrichment**: These checks add diagnostic hints only (no outbound calls and no malware verdict claims).
- **Current built-in signal families**: model path anomalies, missing assets/placeholders, node config anti-patterns, and environment mismatch hints.
- **Traceable results**: Signature-pack matches include machine-readable confidence and provenance metadata in diagnostics output.
- **Bounded runtime**: Deterministic scan caps are applied to avoid unbounded workflow scanning.

Advanced runtime controls (optional):

- `DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED` to globally enable/disable signature-pack checks
- `DOCTOR_DIAGNOSTICS_SIGNATURE_PACK_IDS` to allowlist specific pack IDs
  - If unset, all enabled builtin packs are loaded
  - Use a comma-separated list (example: `builtin.comfyui_heuristics`)

Signature-pack matches are stored in diagnostics issue metadata as machine-readable provenance (for example: pack/rule IDs, confidence, and provenance tags).

#### Quick Community Feedback (GitHub PR)

![Diagnostics](assets/feedback.png)

The Statistics tab also includes a **Quick Community Feedback** panel for preparing a sanitized feedback payload and opening a GitHub PR from the server side.

**What it does**:

- Prefills from the latest error / statistics context (when available)
- Lets you preview the sanitized payload before submission
- Submits an append-only feedback JSON file and opens a PR (server-side GitHub token flow)

**Prerequisites**:

- Server-side GitHub token configured (`DOCTOR_GITHUB_TOKEN`)
- Admin authorization for submit actions (submit route is admin-guarded)

**How to Use**:

1. Open **Doctor** → **Statistics**
2. Scroll to **Quick Community Feedback**
3. Fill or confirm the pattern candidate / suggestion fields
4. Click **Preview** and review the sanitized payload
5. Click **Submit** to create the GitHub PR
6. Open the returned PR URL to review/edit the final submission on GitHub

**Resolution Status Controls**:

- Buttons are enabled only when a latest error timestamp is available
- Status updates persist in history and refresh the resolution rate automatically

**Understanding the Data**:

- **Total (30d)**: Cumulative errors in the past 30 days
- **Last 24h**: Errors in the last 24 hours (helps identify recent issues)
- **Resolution Rate**: Shows progress toward resolving known issues
  - 🟢 **Resolved**: Issues you've fixed
  - 🟠 **Unresolved**: Active issues requiring attention
  - ⚪ **Ignored**: Non-critical issues you've chosen to ignore
- **Top Patterns**: Identifies which error types need priority attention
- **Categories**: Helps you understand whether issues are memory-related, workflow problems, model loading failures, etc.

**Panel State Persistence**: The panel's open/closed state is saved in your browser's localStorage, so your preference persists across sessions.

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

You can customize ComfyUI-Doctor behavior via the **Doctor sidebar → Settings** tab.

### 1. Show error notifications

**Function**: Toggle floating error notification cards (toasts) in the top-right corner.
**Usage**: Disable if you prefer to check errors manually in the sidebar without visual interruptions.

### 2. Auto-open panel on error

**Function**: Automatically opens the **right-side error report panel** when a new error is detected.
**Default**: **ON** (recommended).
**Usage**: Disable if you prefer to keep the panel closed and open it manually.

### 3. Error Check Interval (ms)

**Function**: Frequency of frontend-backend error checks (in milliseconds). Default: `2000`.
**Usage**: Lower values (e.g., 500) give faster feedback but increase load; higher values (e.g., 5000) save resources.

### 4. Suggestion Language

**Function**: Language for diagnostic reports and Doctor suggestions.
**Usage**: Supports 9 languages: English, Traditional Chinese, Simplified Chinese, Japanese, German, French, Italian, Spanish, and Korean. Changes apply to new errors and refreshed UI text.

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
**Default Behavior**: Session-only in frontend (cleared on reload); not persisted in ComfyUI settings.
**Runtime Resolution Priority**: Request key → provider-specific ENV → generic ENV → optional server-side key store.
**Security Warning**: The server-side key store writes plaintext `secrets.json` to disk. Use ENV for production or multi-user environments.

**Advanced Key Store Setup (optional)**:

<img src="assets/key_store.png" alt="side bar - Advanced Key Store">

1. Expand **🔐 Advanced Key Store (Server-side)** in Settings (collapsed by default).
2. Select provider, paste API key, and provide admin token if configured.
3. Click **💾 Save to Server** to persist, or **🗑️ Delete** to remove.
4. Confirm provider status badge (`ENV`, `Server`, `None`) to verify effective source.

### 9. AI Model Name

**Function**: Specify which model to use for error analysis.
**Usage**:

- **Dropdown Mode** (default): Select a model from the automatically-populated dropdown list. Click the 🔄 refresh button to reload available models.
- **Manual Input Mode**: Check "Enter model name manually" to type a custom model name (e.g., `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- Models are automatically fetched from your selected provider's API when you change providers or click refresh.
- For local LLMs (Ollama/LMStudio), the dropdown displays all locally available models.

> Note: **Trust & Health** and **Anonymous Telemetry** have moved to the **Statistics** tab.

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
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"],
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

### GET `/doctor/secrets/status` (S8)

Get provider key source/status information without exposing secret values.

- Admin-gated (loopback convenience may apply depending on `DOCTOR_ADMIN_TOKEN` configuration)
- Used by the **Advanced Key Store (Server-side)** panel

**Response (shape)**:

```json
{
  "success": true,
  "providers": {
    "openai": {"effective_source": "env|server|none"},
    "gemini": {"effective_source": "env|server|none"}
  }
}
```

### PUT `/doctor/secrets` (S8)

Save a provider API key to the optional server-side key store (`secrets.json`).

**Payload**:

```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "admin_token": "optional-if-configured"
}
```

### DELETE `/doctor/secrets/{provider}` (S8)

Delete a provider API key from the optional server-side key store.

- Admin-gated (token may be provided via request body and/or headers per server policy)

```bash
curl -X DELETE http://localhost:8188/doctor/secrets/openai
```

### POST `/doctor/mark_resolved` (F15)

Update the latest error resolution status used by the Statistics dashboard.

**Payload**:

```json
{
  "timestamp": "2026-01-04T12:00:00",
  "status": "resolved"
}
```

`status` supports: `resolved`, `unresolved`, `ignored`

### POST `/doctor/feedback/preview` (F16)

Validate and sanitize a Quick Community Feedback payload before GitHub PR submission.

**Payload (example)**:

```json
{
  "pattern_candidate": {
    "id": "community_user_feedback",
    "regex": "RuntimeError",
    "category": "generic",
    "priority": 60
  },
  "suggestion_candidate": {
    "language": "en",
    "message": "Describe the verified fix here"
  },
  "error_context": {},
  "include_stats": true,
  "stats_snapshot": {}
}
```

**Response (shape)**:

```json
{
  "success": true,
  "submission_id": "fb_...",
  "files": {
    "submission": "feedback/submissions/...json"
  },
  "preview": {},
  "warnings": [],
  "github": {
    "ready": false,
    "repo": "rookiestar28/ComfyUI-Doctor",
    "base_branch": "main"
  }
}
```

### POST `/doctor/feedback/submit` (F16)

Create a GitHub PR from a sanitized feedback payload (append-only files under `feedback/`).

- Admin-gated write endpoint
- Requires server-side GitHub token (`DOCTOR_GITHUB_TOKEN`)
- Payload is the same shape as `/doctor/feedback/preview` (optionally including `admin_token`)

**Response (shape)**:

```json
{
  "success": true,
  "submission_id": "fb_...",
  "preview": {},
  "warnings": [],
  "github": {
    "ready": true,
    "repo": "rookiestar28/ComfyUI-Doctor",
    "branch": "feedback/20260226/...",
    "base_branch": "main",
    "pr_number": 123,
    "pr_url": "https://github.com/.../pull/123"
  }
}
```

### GET `/doctor/health`

Fetch internal Doctor health metrics (logger queue stats, SSRF counters, storage path, and last pipeline status).

```bash
curl http://localhost:8188/doctor/health
```

### GET `/doctor/plugins`

Fetch a scan-only plugin trust report (no plugin code import).

```bash
curl http://localhost:8188/doctor/plugins
```

### GET `/doctor/telemetry/status` (S3)

Get telemetry enable state and local buffer stats.

```bash
curl http://localhost:8188/doctor/telemetry/status
```

### GET `/doctor/telemetry/buffer` (S3)

Fetch buffered local telemetry events (used by the Statistics tab telemetry panel).

```bash
curl http://localhost:8188/doctor/telemetry/buffer
```

### POST `/doctor/telemetry/track` (S3)

Record a telemetry event (same-origin, JSON-only, bounded payload).

**Payload**:

```json
{
  "category": "ui",
  "action": "click",
  "label": "stats_refresh",
  "value": 1
}
```

### POST `/doctor/telemetry/clear` (S3)

Clear all buffered local telemetry events.

```bash
curl -X POST http://localhost:8188/doctor/telemetry/clear
```

### GET `/doctor/telemetry/export` (S3)

Export telemetry buffer as a downloadable JSON file.

```bash
curl -OJ http://localhost:8188/doctor/telemetry/export
```

### POST `/doctor/telemetry/toggle` (S3)

Enable or disable local telemetry collection.

**Payload**:

```json
{
  "enabled": true
}
```


### GET `/doctor/jobs/{job_id}`

Get checkpointed job status for a long-running enrichment task.

```bash
curl http://localhost:8188/doctor/jobs/<job_id>
```

### POST `/doctor/jobs/{job_id}/resume`

Resume a previously interrupted/suspended enrichment job.

```bash
curl -X POST http://localhost:8188/doctor/jobs/<job_id>/resume
```

### POST `/doctor/jobs/{job_id}/cancel`

Cancel a running/pending enrichment job.

```bash
curl -X POST http://localhost:8188/doctor/jobs/<job_id>/cancel
```

### GET `/doctor/providers/{provider_id}/status`

Fetch provider capability/policy status used by enrichment controls.

```bash
curl http://localhost:8188/doctor/providers/<provider_id>/status
```

> Note: Job resume semantics depend on provider adapter implementation. The API provides the resumable foundation and policy boundary.

### POST `/doctor/health_check` (F14)

Run proactive diagnostics on a workflow snapshot (no LLM required).

**Payload**:

```json
{
  "workflow": { "...": "ComfyUI workflow JSON" },
  "scope": "manual",
  "options": { "include_intent": true, "max_paths": 50 }
}
```

### GET `/doctor/health_report` (F14)

Fetch the last computed health report (cached; falls back to latest stored report).

```bash
curl http://localhost:8188/doctor/health_report
```

### GET `/doctor/health_history` (F14)

Fetch recent report metadata (no heavy payload).

```bash
curl "http://localhost:8188/doctor/health_history?limit=50&offset=0"
```

### POST `/doctor/health_ack` (F14)

Acknowledge/ignore/resolve an issue.

**Payload**:

```json
{
  "report_id": "report_...",
  "issue_id": "issue_...",
  "status": "acknowledged"
}
```

`status` supports: `acknowledged`, `ignored`, `resolved`

---

## Log Files

All logs are stored in:

```text
<ComfyUI user directory>/ComfyUI-Doctor/logs/
```

Filename format: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

The system automatically retains the 10 most recent log files (configurable via `config.json`).

> Tip: You can check the resolved data directory via `GET /doctor/health` → `health.storage.data_dir`.
> Legacy installs may still have logs under `ComfyUI/custom_nodes/ComfyUI-Doctor/logs/` (migrated when possible).

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

### Community Plugins (Advanced)

Community plugins extend pattern matching with custom Python logic. For safety, they are **disabled by default** and are only loaded if they pass the trust policy.

Enable via `config.json`:

```json
{
  "enable_community_plugins": true,
  "plugin_allowlist": ["example.plugin"],
  "plugin_blocklist": [],
  "plugin_signature_required": false,
  "plugin_signature_key": "",
  "plugin_signature_alg": "hmac-sha256"
}
```

Notes:

- Plugins live under `pipeline/plugins/community/` and require a manifest (`*.json` next to the plugin, or `plugin.json` if there is only one plugin file).
- Trust rules include allowlist, manifest/sha256 verification, filesystem hardening (containment, symlink rejection, size/scan limits), and optional HMAC verification.
- **HMAC signature is a shared-secret integrity check**, not a public-key signature; keep `plugin_signature_key` secret and never commit it to Git.

See `docs/PLUGIN_GUIDE.md` for the manifest schema and details.

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

## Phase 2 Release Gate

Before merging Phase 2 changes (pipeline, security, plugin hardening), all code must pass the **Phase 2 Release Gate**.

### Required Checks

- **Plugin security suite** (10 tests) - Allowlist, trust states, DoS limits
- **Metadata contract suite** (1 test) - Schema validation
- **Dependency policy suite** (2 tests) - Requires/provides enforcement
- **Outbound payload safety suite** (4 tests) - Sanitization funnel
- **E2E regression suite** (61 tests) - UI stability

### Run Locally

```bash
# Full gate (Python + E2E)
python scripts/phase2_gate.py

# Fast mode (Python only, < 2 minutes)
python scripts/phase2_gate.py --fast
```

### Validation Expansion Pack (Targeted)

```powershell
# Targeted remediation pack (R17/T13/T9 + scaffolded T5 lane)
.\.venv\Scripts\python.exe -m pytest tests/test_r17_guardrails.py tests/test_t13_desktop_failures.py tests/test_t13_flush_storm.py tests/test_t13_migration.py tests/test_t9_pipeline_contract.py tests/test_t9_harness.py tests/integration/test_pipeline_isolation.py tests/integration/test_online_api_opt_in.py

# Opt-in online lane (secret-scoped)
$env:RUN_ONLINE_API_TESTS='true'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_online_api_opt_in.py -q
Remove-Item Env:RUN_ONLINE_API_TESTS
```

**CI Status**: The gate runs automatically on push/PR to `main` and `dev` branches.

---

## CSP Compatibility

ComfyUI-Doctor is **Content Security Policy (CSP) compliant** by design:

- ✅ **Server-side LLM calls**: All AI analysis requests are made from the backend, not the browser
- ✅ **Local asset bundling**: JavaScript libraries (Preact, marked.js, highlight.js, DOMPurify) are bundled locally in `web/lib/`
- ✅ **CDN fallback only**: External CDN URLs exist only as fallback paths that execute only if local files fail to load
- ✅ **Verified with `--disable-api-nodes`**: Works correctly when ComfyUI enforces strict CSP headers

**For strict CSP environments**:

- Ensure the backend server can reach your LLM provider endpoints (not blocked by firewall/proxy)
- For air-gapped or highly restricted networks, use local LLMs (Ollama, LMStudio) instead of cloud providers

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

**Report Issues**: Found a bug or have a suggestion? Open an issue on GitHub.
**Submit PRs**: Help improve the codebase with bug fixes or general improvements.
**Feature Requests**: Have some ideas for new features? Let us know please.
