"""
Prompt, fix-schema, and error-context helpers for Doctor LLM routes.

These helpers are imported by API route modules so the package entry point can
stay focused on ComfyUI startup and route wiring.
"""

from __future__ import annotations

import json
import logging

# --- F7: Parameter Fix Helper Functions ---
def validate_fix_schema(fix_json):
    """
    Validate fix JSON structure for F7 parameter injection.

    Args:
        fix_json: Dictionary containing 'fixes' array

    Returns:
        bool: True if schema is valid, False otherwise
    """
    if "fixes" not in fix_json or not isinstance(fix_json["fixes"], list):
        return False

    required_keys = {"node_id", "widget", "from", "to", "reason"}
    for fix in fix_json["fixes"]:
        if not isinstance(fix, dict):
            return False
        if not required_keys.issubset(fix.keys()):
            return False
        # Basic type check: node_id should be convertible to string
        if not isinstance(fix.get("node_id"), (str, int)):
            return False
    return True


# --- Option B Phase 1: Enhanced Error Context & Multi-Language Templates ---

def collect_error_context(error_data, workflow_data):
    """
    Collect comprehensive error context for LLM analysis (Option B Phase 1).

    Returns enriched error data with:
    - Python stack trace (if available)
    - ComfyUI execution logs (last 50 lines)
    - Failed node details (class, inputs, outputs)
    - Workflow structure (upstream dependencies, missing connections)

    Args:
        error_data: Error information dict (exception_message, exception_type, node_id, traceback)
        workflow_data: Full workflow dict mapping node_id -> node_info

    Returns:
        dict: Enriched context with error details, logs, node info, and workflow structure
    """
    context = {
        "error_message": error_data.get("exception_message", "") if error_data else "",
        "error_type": error_data.get("exception_type", "Unknown") if error_data else "Unknown",
        "traceback": None,
        "execution_logs": [],
        "failed_node": None,
        "workflow_structure": {
            "upstream_nodes": [],
            "missing_connections": []
        }
    }

    if not error_data:
        return context

    # 1. Extract Python traceback (if available)
    if "traceback" in error_data:
        context["traceback"] = error_data["traceback"]

    # 2. Get recent execution logs (R14: Prefer ring buffer for reliability)
    # Ring buffer captures ALL stdout/stderr lines, not just ComfyUI logger output
    try:
        from .log_ring_buffer import get_ring_buffer
        ring_buffer = get_ring_buffer()
        context["execution_logs"] = ring_buffer.get_recent(50)
    except Exception:
        # Fallback: Try ComfyUI's logger buffer (legacy behavior)
        try:
            comfy_logger = logging.getLogger("comfyui")
            if hasattr(comfy_logger, 'handlers'):
                for handler in comfy_logger.handlers:
                    if hasattr(handler, 'buffer'):
                        context["execution_logs"] = handler.buffer[-50:]
                        break
        except Exception:
            pass  # No logs available

    # 3. Get failed node details
    node_id = (
        error_data.get("display_node")
        or error_data.get("node_id")
        or error_data.get("real_node_id")
    )
    normalized_node_id = str(node_id).split(":")[-1] if node_id else None
    node_lookup = None
    if isinstance(workflow_data, dict):
        if "nodes" in workflow_data and isinstance(workflow_data.get("nodes"), list):
            node_lookup = {
                str(node.get("id")): node
                for node in workflow_data.get("nodes", [])
                if isinstance(node, dict) and node.get("id") is not None
            }
        else:
            node_lookup = workflow_data

    if normalized_node_id and node_lookup:
        node = node_lookup.get(normalized_node_id)
        if node:
            context["failed_node"] = {
                "id": normalized_node_id,
                "class_type": node.get("class_type") or node.get("type"),
                "inputs": node.get("inputs", {}),
                "title": node.get("_meta", {}).get("title", "") or node.get("title", ""),
                "display_node": error_data.get("display_node"),
                "parent_node": error_data.get("parent_node"),
                "real_node_id": error_data.get("real_node_id"),
                "subgraph_lineage": error_data.get("subgraph_lineage") or [],
            }

            # 4. Analyze workflow structure around failed node
            # Find upstream nodes (nodes that feed into this one)
            upstream = []
            for input_key, input_value in node.get("inputs", {}).items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    # This is a connection: [source_node_id, output_index]
                    source_node_id = str(input_value[0])
                    if node_lookup and source_node_id in node_lookup:
                        upstream.append({
                            "id": source_node_id,
                            "class_type": node_lookup[source_node_id].get("class_type") or node_lookup[source_node_id].get("type"),
                            "connection": input_key
                        })

            context["workflow_structure"]["upstream_nodes"] = upstream

            # 5. Check for missing required connections
            # This requires ComfyUI's node definition API
            try:
                try:
                    from ..nodes import NODE_CLASS_MAPPINGS
                except ImportError as import_error:
                    from import_compat import ensure_absolute_import_fallback_allowed
                    ensure_absolute_import_fallback_allowed(import_error)
                    from nodes import NODE_CLASS_MAPPINGS
                node_class = NODE_CLASS_MAPPINGS.get(node.get("class_type"))
                if node_class and hasattr(node_class, "INPUT_TYPES"):
                    required_inputs = node_class.INPUT_TYPES().get("required", {})
                    for req_input in required_inputs.keys():
                        if req_input not in node.get("inputs", {}):
                            context["workflow_structure"]["missing_connections"].append({
                                "input": req_input,
                                "type": str(required_inputs[req_input])
                            })
            except Exception:
                pass

    return context


# Multi-language error analysis prompt templates (Option B Phase 1)
# System prompts are written in English with explicit language directives.
ERROR_ANALYSIS_BASE_TEMPLATE = """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: {response_language}

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""

ERROR_ANALYSIS_RESPONSE_LANGUAGES = {
    "en": "English",
    "zh_TW": "繁體中文",
    "zh_CN": "简体中文",
    "ja": "日本語",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "es": "Español",
    "ko": "한국어",
}


ERROR_ANALYSIS_TEMPLATES = {
    language_code: {
        "system_instruction": ERROR_ANALYSIS_BASE_TEMPLATE.replace(
            "{response_language}", response_language
        )
    }
    for language_code, response_language in ERROR_ANALYSIS_RESPONSE_LANGUAGES.items()
}


def get_error_analysis_prompt(user_language: str) -> str:
    """
    Get error analysis system prompt in English with language directive.

    This follows the Option B design principle:
    - System prompts written in English (for LLM consistency)
    - Explicit language directive for responses
    - Maintains prompt quality across all languages

    Args:
        user_language: User's preferred language (en/zh_TW/zh_CN/ja/de/fr/it/es/ko)

    Returns:
        System prompt in English with explicit language directive
    """
    template = ERROR_ANALYSIS_TEMPLATES.get(user_language, ERROR_ANALYSIS_TEMPLATES["en"])
    return template["system_instruction"]


def parse_language_code(accept_language: str) -> str:
    """
    Parse Accept-Language header to extract primary language code.

    Examples:
        "zh-TW,zh;q=0.9,en;q=0.8" → "zh_TW"
        "en-US,en;q=0.9" → "en"
        "ja" → "ja"

    Args:
        accept_language: HTTP Accept-Language header value

    Returns:
        Normalized language code (e.g., "zh_TW", "en", "ja")
    """
    if not accept_language:
        return "en"

    # Extract first language code (before comma)
    primary_lang = accept_language.split(',')[0].strip()

    # Normalize separators: "zh-TW" → "zh_TW"
    normalized = primary_lang.replace('-', '_')

    # Map to supported languages
    supported_map = {
        "zh_TW": "zh_TW",
        "zh_CN": "zh_CN",
        "zh_HK": "zh_TW",  # Fallback: Hong Kong → Traditional Chinese
        "zh": "zh_CN",      # Fallback: Generic Chinese → Simplified
        "ja": "ja",
        "de": "de",
        "fr": "fr",
        "it": "it",
        "es": "es",
        "ko": "ko",
        "en": "en"
    }

    # Try exact match first
    if normalized in supported_map:
        return supported_map[normalized]

    # Try base language (e.g., "en_US" → "en")
    base_lang = normalized.split('_')[0]
    if base_lang in supported_map:
        return supported_map[base_lang]

    # Default to English
    return "en"


# --- Option B Phase 2: Error Categorization ---

def categorize_error(error_data):
    """
    Classify error type using keyword matching (Option B Phase 2).

    This helps the LLM focus on the right fix strategy by pre-categorizing
    errors into one of 5 common types.

    Args:
        error_data: Error information (can be dict, string, or any object with str() representation)

    Returns:
        dict: {
            "category": str (connection_error|model_missing|validation_error|type_error|execution_error),
            "confidence": float (0.0-1.0),
            "keywords_matched": list[str],
            "suggested_approach": str
        }
    """
    # Convert error_data to searchable string
    if isinstance(error_data, dict):
        error_text = json.dumps(error_data).lower()
    else:
        error_text = str(error_data).lower()

    # Define keyword patterns for each error category
    # Inspired by ComfyUI-Copilot's debug_agent.py pattern matching
    patterns = {
        "connection_error": {
            "keywords": [
                "missing input", "required input", "not connected",
                "connection", "disconnected", "input is required",
                "missing required", "no input provided"
            ],
            "weight": 1.0,
            "approach": "Check node connections. Ensure all required inputs are connected to upstream nodes."
        },
        "model_missing": {
            "keywords": [
                ".safetensors", ".ckpt", ".pth", ".pt", ".bin",
                "model not found", "file not found", "no such file",
                "checkpoint", "filenotfounderror", "path does not exist"
            ],
            "weight": 1.0,
            "approach": "Check model files in your models directory. Verify the model name matches an existing file."
        },
        "validation_error": {
            "keywords": [
                "value not in list", "invalid value", "not found in list",
                "invalid parameter", "value error", "not a valid",
                "must be one of", "not in allowed values", "invalid choice"
            ],
            "weight": 0.9,
            "approach": "Use fuzzy matching to find the correct parameter value from available options."
        },
        "type_error": {
            "keywords": [
                "type mismatch", "expected", "but received",
                "cannot convert", "dtype", "typeerror",
                "incompatible type", "wrong type", "type error"
            ],
            "weight": 0.8,
            "approach": "Check data type conversions. May need a conversion node (e.g., ImageToTensor)."
        }
    }

    # Count keyword matches for each category
    matches = {}
    for category, config in patterns.items():
        matched_keywords = [kw for kw in config["keywords"] if kw in error_text]
        count = len(matched_keywords)

        if count > 0:
            # Calculate confidence: (matches / total_keywords) * weight
            # Cap at 1.0 to prevent over-confidence
            confidence = min(count / len(config["keywords"]) * config["weight"], 1.0)

            matches[category] = {
                "count": count,
                "confidence": confidence,
                "matched_keywords": matched_keywords,
                "approach": config["approach"]
            }

    # Return category with highest confidence
    if matches:
        best_category, best_match = max(matches.items(), key=lambda x: x[1]["confidence"])
        return {
            "category": best_category,
            "confidence": best_match["confidence"],
            "keywords_matched": best_match["matched_keywords"],
            "suggested_approach": best_match["approach"]
        }
    else:
        # Default: Generic execution error
        return {
            "category": "execution_error",
            "confidence": 0.5,
            "keywords_matched": [],
            "suggested_approach": "General error analysis needed. Check Python stack trace for details."
        }
