# Outbound Safety Check

## What This Checks

The static safety check prevents accidental bypass of the outbound sanitization funnel by detecting:

1. **Direct use of raw `context` fields in POST payloads**
2. **Missing `sanitize_outbound_payload()` calls**
3. **Dangerous fallback patterns** like `sanitized_X or X`
4. **`json.dumps()` on sensitive data**

## Why This Matters

ComfyUI-Doctor sends error context to LLM providers for analysis. To protect user privacy, all outbound payloads MUST go through the sanitization funnel in `outbound.py`.

**Sensitive Fields**:
- `context.traceback` - Raw Python stack trace with user paths
- `context.workflow_json` - Full workflow with potential paths
- `context.system_info` - System environment data
- `context.settings` - App settings

## How to Fix Violations

### ❌ Wrong: Direct Field Access

```python
payload = {"error": context.traceback}
await session.post(url, json=payload)
```

### ✅ Right: Sanitize Before Use

```python
sanitizer, _ = get_outbound_sanitizer(base_url, privacy_mode)
error_text = sanitizer.sanitize(context.traceback).sanitized_text
payload = {"error": error_text}
payload = sanitize_outbound_payload(payload, sanitizer)
await session.post(url, json=payload)
```

### ❌ Wrong: Dangerous Fallback

```python
data = {
    "traceback": context.sanitized_traceback or context.traceback  # BAD!
}
```

### ✅ Right: Fail Safe

```python
if not context.sanitized_traceback:
    logger.warning("Sanitized traceback missing")
    context.llm_context = None
    return context

data = {
    "traceback": context.sanitized_traceback  # Only use sanitized
}
```

### ❌ Wrong: POST Without Sanitization

```python
async def handler():
    sanitizer, _ = get_outbound_sanitizer(url, mode)
    payload = {"data": "test"}
    await session.post(url, json=payload)  # Never sanitized!
```

### ✅ Right: Always Sanitize

```python
async def handler():
    sanitizer, _ = get_outbound_sanitizer(url, mode)
    payload = {"data": "test"}
    payload = sanitize_outbound_payload(payload, sanitizer)
    await session.post(url, json=payload)
```

## Suppressing False Positives

If you have a legitimate exception (e.g., local debug endpoint), add a suppression comment:

```python
# nosec: outbound-bypass-allowed - Reason: local debugging only
payload = {"raw": context.traceback}
```

**Important**: Use suppressions sparingly. Most cases should use the proper sanitization pattern.

## Running Locally

```bash
python scripts/check_outbound_safety.py
```

**Output Example**:
```
🔒 Outbound Funnel Safety Check (T12)
Scanning: /path/to/ComfyUI-Doctor

Checking 42 Python files...

❌ 1 violation(s) detected:

  File: pipeline/stages/llm_builder.py:63:12
  Rule: DANGEROUS_FALLBACK
  Message: Dangerous fallback: context.sanitized_traceback or context.traceback

   61:         # 2. Build LLM Context Dict
   62:         llm_data = {
   63:             "traceback": context.sanitized_traceback or context.traceback,
   64:             "node_info": context.node_context.to_dict() if context.node_context else {},

--------------------------------------------------------------------------------

🚫 1 outbound safety violation(s) found
```

## CI Integration

This check runs automatically on all Python file changes via `.github/workflows/outbound-safety.yml`.

**Exit Codes**:
- `0` = All checks passed
- `1` = Violations detected (fails CI)
- `2` = Script error

## Whitelisted Files

The following files are excluded from checking:
- `tests/` - Tests need to verify behavior
- `outbound.py` - Sanitization module itself
- `sanitizer.py` - PII sanitization module
- `pipeline/stages/sanitizer.py` - Stage that reads raw fields

## Detection Rules

| Rule | Description | Example |
|------|-------------|---------|
| `RAW_FIELD_IN_PAYLOAD` | Direct assignment of raw context field to payload | `payload["error"] = context.traceback` |
| `DANGEROUS_FALLBACK` | Fallback to raw field if sanitized missing | `context.sanitized_traceback or context.traceback` |
| `POST_WITHOUT_SANITIZATION` | POST without prior `sanitize_outbound_payload()` | `await session.post(url, json=payload)` |
| `JSON_DUMPS_RAW_FIELD` | `json.dumps()` on raw context field | `json.dumps(context.system_info)` |

## Resources

- **Sanitization Funnel**: `outbound.py`
- **Privacy Modes**: `sanitizer.py`
- **Test Fixtures**: `tests/fixtures/outbound_violations.py`
- **Test Suite**: `tests/test_outbound_safety_gate.py`

## Questions?

If you're unsure whether your code violates the policy, run the check locally before pushing.
