"""
Metadata contract enforcement for the analysis pipeline.

Ensures metadata remains small, typed, and forward-compatible by
quarantining invalid keys under `_invalid`.
"""

from typing import Any, Dict, Iterable

METADATA_SCHEMA_VERSION = "v1"

ALLOWED_KEYS = {
    "metadata_schema_version": str,
    "pipeline_status": str,
    "stage_errors": list,
    "sanitization": dict,
    "matched_pattern_id": str,
    "category": str,
    "priority": int,
    "match_source": str,
    "estimated_tokens": (int, float),
    "plugin": dict,
    "context_extraction": dict,
}

ALLOWED_PREFIXES = ("stage_error_",)

MAX_TOP_LEVEL_KEYS = 64
MAX_NESTED_KEYS = 64
MAX_LIST_ITEMS = 50
MAX_STRING_LENGTH = 512
MAX_NESTED_DEPTH = 5


def _has_allowed_prefix(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _exceeds_limits(value: Any, depth: int = 0) -> bool:
    if depth > MAX_NESTED_DEPTH:
        return True

    if isinstance(value, str):
        return len(value) > MAX_STRING_LENGTH

    if isinstance(value, list):
        if len(value) > MAX_LIST_ITEMS:
            return True
        return any(_exceeds_limits(item, depth + 1) for item in value)

    if isinstance(value, dict):
        if len(value) > MAX_NESTED_KEYS:
            return True
        return any(_exceeds_limits(item, depth + 1) for item in value.values())

    return False


def validate_metadata_contract(metadata: Dict[str, Any]) -> Dict[str, Any]:
    if metadata is None:
        metadata = {}

    result: Dict[str, Any] = {}
    invalid: Dict[str, Any] = {}

    result["metadata_schema_version"] = METADATA_SCHEMA_VERSION

    pipeline_status = metadata.get("pipeline_status")
    if pipeline_status not in {"ok", "degraded", "failed"}:
        pipeline_status = "ok"
    result["pipeline_status"] = pipeline_status

    stage_errors = metadata.get("stage_errors")
    if isinstance(stage_errors, list):
        valid_errors = []
        invalid_errors = []
        for entry in stage_errors:
            if not isinstance(entry, dict):
                invalid_errors.append(entry)
                continue
            if not isinstance(entry.get("stage_id"), str):
                invalid_errors.append(entry)
                continue
            if _exceeds_limits(entry):
                invalid_errors.append(entry)
                continue
            valid_errors.append(entry)
        if valid_errors:
            result["stage_errors"] = valid_errors[:MAX_LIST_ITEMS]
        if invalid_errors:
            invalid["stage_errors"] = invalid_errors[:MAX_LIST_ITEMS]
    elif stage_errors is not None:
        invalid["stage_errors"] = stage_errors

    for key, value in metadata.items():
        if key in {"metadata_schema_version", "pipeline_status", "stage_errors", "_invalid"}:
            continue

        if not (key in ALLOWED_KEYS or _has_allowed_prefix(key)):
            invalid[key] = value
            continue

        expected_type = ALLOWED_KEYS.get(key)
        if expected_type and not isinstance(value, expected_type):
            invalid[key] = value
            continue

        if _exceeds_limits(value):
            invalid[key] = value
            continue

        result[key] = value

    if invalid:
        result["_invalid"] = invalid

    if len(result) > MAX_TOP_LEVEL_KEYS:
        overflow = sorted(result.keys())[MAX_TOP_LEVEL_KEYS:]
        for key in overflow:
            invalid[key] = result.pop(key)
        if invalid:
            result["_invalid"] = invalid

    return result
