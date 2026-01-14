# R15: Canonicalize `system_info` + Populate Pipeline `execution_logs` - Implementation Plan

**Date:** 2026-01-14  
**Status:** 📝 Planning Complete  
**Priority:** 🟡 Medium  
**Related Work:** R14 (PromptComposer + LogRingBuffer), R12 (Token Budgets)  
**Target Branch:** `dev` (merge to `main` after CI green + spot-check prompts)

---

## 1. Executive Summary

R15 is a follow-up quality/consistency hardening item after R14.

It closes two optional but high-leverage gaps:

1. **`system_info` shape canonicalization** so that PromptComposer can reliably render OS/Python/CUDA/PyTorch + *a small, relevant* package subset across endpoints and pipeline.
2. **Pipeline `execution_logs` population** from the same `LogRingBuffer` used by endpoint-level error context, so the pipeline’s `llm_context` can be the canonical structured source.

Deliverable: a stable, token-efficient, privacy-respecting context format that behaves consistently regardless of endpoint (`/doctor/analyze`, `/doctor/chat`) or pipeline usage.

---

## 2. Problem Statement (Current Gaps)

### 2.1 `system_info` mismatch → PromptComposer renders incomplete env

- `system_info.get_system_environment()` currently returns:
  - `pytorch_info` (nested dict: `pytorch_version`, `cuda_available`, …)
  - `installed_packages` (pip freeze string)
- `services/prompt_composer.py` currently expects a *different* flattened schema:
  - `torch_version`, `cuda_available`, `packages` (list)

Result:
- When PromptComposer is used (e.g. `/doctor/analyze`), the “System Environment” section often contains only OS + Python, missing CUDA/PyTorch and relevant packages.

### 2.2 Pipeline `execution_logs` is defined but not auto-populated

- `pipeline/context.py` includes `execution_logs: List[str]`.
- `pipeline/stages/llm_builder.py` places `execution_logs` into `llm_context`, but assumes `context.execution_logs` is already filled.
- In practice, logs are primarily attached in endpoint-side `collect_error_context(...)`, not in pipeline stage execution.

Result:
- Pipeline-produced `llm_context` may omit logs even when the ring buffer contains useful context.

---

## 3. Goals / Non-Goals

### 3.1 Goals

1. **Single canonical `system_info` schema** used by PromptComposer and pipeline.
2. **Smart, token-efficient packages subset** (`system_info.packages`) with strict caps by default.
3. **Pipeline fills `execution_logs`** from `LogRingBuffer` when not already provided.
4. **Privacy-aware**: respect `privacy_mode` (`none/basic/strict`) for outbound content.
5. **Test coverage**: add targeted unit tests for canonicalization and log population.

### 3.2 Non-Goals (R15)

- Do not add new UI features (Phase 5 UI transparency remains separate).
- Do not upload telemetry or introduce network reporting.
- Do not include full `pip list` by default (must remain strictly capped).
- Do not refactor the entire pipeline wiring in `analyzer.py` (keep changes scoped).

---

## 4. Canonical Schemas (Contracts)

### 4.1 Canonical `system_info` (v1)

Use this shape when passing to PromptComposer and when storing in pipeline `llm_context`:

```json
{
  "os": "Windows 11 10.0.22631",
  "python_version": "3.10.11",
  "torch_version": "2.1.0+cu121",
  "cuda_available": true,
  "cuda_version": "12.1",
  "gpu_count": 1,
  "packages": ["torch==2.1.0", "xformers==0.0.23", "comfyui==..."],
  "packages_total": 412,
  "cache_age_seconds": 3600,
  "source": "get_system_environment"
}
```

Notes:
- `packages` MUST be a list of strings (pip-freeze style) and MUST be capped (default ≤ 20).
- Optional keys are allowed (`cuda_version`, `gpu_count`, etc.), but the core keys above should be present when available.
- Keep raw/legacy fields out of the default schema to avoid token bloat (if needed, store under an internal-only key or omit).

### 4.2 Canonical `execution_logs`

- `execution_logs` MUST be a list of strings.
- Default max lines is aligned with PromptComposer (`PromptComposerConfig.max_logs_lines`, currently 50).

---

## 5. Proposed Implementation

### 5.1 Add a canonicalization helper (source-of-truth)

**Add to** `system_info.py` (preferred) or a new file `services/system_info_canonicalizer.py`:

- `canonicalize_system_info(env_info: dict, *, error_text: str | None = None, privacy_mode: str = "basic", max_packages: int = 20) -> dict`

Responsibilities:
1. **Flatten Torch info**:
   - From `env_info["pytorch_info"]` → `torch_version`, `cuda_available`, `cuda_version`, `gpu_count`
2. **Parse packages**:
   - From `env_info["installed_packages"]` (pip freeze string) → dict/list
3. **Smart package selection**:
   - Always include a small baseline set (e.g. `torch`, `comfy`, `numpy`, `pillow`, `opencv`, `diffusers`, `transformers`, `safetensors`, `accelerate`, `xformers`, `triton`)
   - Extract package keywords from `error_text` when present:
     - `ModuleNotFoundError: No module named 'pkg.sub'` → include `pkg`
     - `ImportError: cannot import name ... from 'pkg'` → include `pkg`
     - Include common “runtime” keywords if seen in error (`xformers`, `triton`, `onnx`, `insightface`, `torch`, `cuda`, etc.)
   - Select up to `max_packages` packages:
     - Priority order: error-referenced → baseline → other “known important”
4. **Privacy**:
   - Package list usually has no PII, but keep a final sanitization pass consistent with `privacy_mode` for any derived text fields.
5. **Back-compat**:
   - If `env_info` is already canonical (has `torch_version`/`packages`), return it (or normalize minimal differences).

### 5.2 Make PromptComposer tolerant (optional but recommended)

**Update** `services/prompt_composer.py`:

- `_format_system_info()` should accept either:
  - canonical (`torch_version`, `packages`, …) OR
  - legacy (`pytorch_info`, `installed_packages`) by internally calling `canonicalize_system_info`.

This keeps older callers safe and reduces the chance of silent “missing env” regressions.

### 5.3 Endpoint integration (no duplicated env blocks)

**Update** `__init__.py`:

1. `/doctor/analyze` (PromptComposer path):
   - Replace `llm_context["system_info"] = env_info` with canonical form:
     - `llm_context["system_info"] = canonicalize_system_info(env_info, error_text=error_text, privacy_mode=privacy_mode)`
2. `/doctor/chat`:
   - When PromptComposer path is used, include canonical `system_info` directly in `llm_context` and **do not** append `format_env_for_llm(...)` afterwards (avoid double env data / token waste).
   - When legacy formatting is used, keep the existing `format_env_for_llm(...)` append behavior.

### 5.4 Populate pipeline `execution_logs` from `LogRingBuffer`

**Update** `pipeline/stages/llm_builder.py`:

- If `context.execution_logs` is empty:
  - Pull from ring buffer:
    - `raw_logs = get_ring_buffer().get_recent(n, sanitize=False)`
  - Sanitize using `privacy_mode = context.settings.get("privacy_mode", "basic")`:
    - `sanitize_for_llm(line, level=privacy_mode)` (or equivalent)
  - Assign:
    - `context.execution_logs = sanitized_logs`

Optional hardening (recommended):
- Apply noise filtering or de-dup to keep logs useful (bounded by max lines anyway).
- If the ring buffer is unavailable, keep the existing behavior (empty logs).

### 5.5 (Optional) Populate pipeline `system_info` when missing

If pipeline usage is expected to be standalone (not only used by endpoints):
- In `LLMContextBuilderStage`, if `context.system_info` is empty, attempt:
  - `env_info = get_system_environment()` (cached 24h)
  - `context.system_info = canonicalize_system_info(env_info, error_text=context.sanitized_traceback, privacy_mode=context.settings.get("privacy_mode", "basic"))`

⚠️ Keep this behind a small guard (e.g., only if `context.settings.get("include_system_info", True)`), to avoid surprising test/CI cost.

---

## 6. Test Plan

### 6.1 Unit tests (Python)

Add `tests/test_r15_system_info.py`:

- `test_canonicalize_system_info_from_legacy_shape()`
  - input: legacy `env_info` with `pytorch_info` + `installed_packages`
  - assert: output has `torch_version`, `cuda_available`, `packages` (list), `packages_total`
- `test_canonicalize_system_info_keyword_selection()`
  - error contains `ModuleNotFoundError: No module named 'insightface'`
  - assert: `packages` contains `insightface==...` when present in freeze
- `test_canonicalize_system_info_caps_packages()`
  - freeze contains many packages
  - assert: `len(packages) <= max_packages`

Add/extend `tests/test_context_extraction.py` or `tests/test_r14_services.py`:
- Ensure PromptComposer renders torch/cuda + packages when canonical info is provided.

### 6.2 Pipeline behavior tests

Add to `tests/test_pipeline_infra.py` or a new `tests/test_r15_pipeline_logs.py`:

- Reset ring buffer, add known lines, run `LLMContextBuilderStage.process()` with empty `context.execution_logs`
- Assert: `context.llm_context["execution_logs"]` contains those lines (sanitized according to `privacy_mode`)

---

## 7. Acceptance Criteria (Definition of Done)

1. **/doctor/analyze** (PromptComposer enabled):
   - “System Environment” shows OS + Python + CUDA/PyTorch when available.
   - Shows a small “Key Packages” subset (capped; no full pip list).
2. **/doctor/chat** (PromptComposer enabled):
   - Env info is included via PromptComposer (canonical schema).
   - No duplicate env blocks (PromptComposer + `format_env_for_llm`) in the same prompt.
3. **Pipeline `llm_context`**:
   - Includes `execution_logs` from ring buffer when logs exist.
4. **Tests**:
   - Existing unit tests stay green.
   - New R15 unit tests pass.

---

## 8. Risks & Mitigations

- **Token bloat**: enforce strict caps (`max_packages`, PromptComposer `max_env_chars`).
- **Privacy regressions**: always sanitize derived env/log strings based on `privacy_mode`.
- **CI variance**: tests must not depend on the runner’s actual `pip list`; use synthetic fixtures.
- **Backwards compatibility**: keep PromptComposer tolerant of legacy schema and keep legacy env formatting path intact.

---

## 9. Implementation Checklist (For Expert A)

- [ ] Implement `canonicalize_system_info(...)` + helpers (parsing + keyword extraction + selection).
- [ ] Wire canonicalization into `/doctor/analyze` PromptComposer path.
- [ ] Wire canonicalization into `/doctor/chat` PromptComposer path and remove duplicate env append when composer succeeds.
- [ ] Update pipeline `LLMContextBuilderStage` to populate `execution_logs` from `LogRingBuffer` when missing.
- [ ] Add unit tests for canonicalization and pipeline log fill.
- [ ] Run: `npm test` (E2E) + targeted pytest set for pipeline/services.
- [ ] Create implementation record: `.planning/260114-R15_SYSTEM_INFO_CANONICALIZATION_AND_PIPELINE_LOGS_RECORD.md`

