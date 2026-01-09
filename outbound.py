"""
Outbound payload safety utilities.

Goal: enforce a single, testable sanitization boundary for any outbound LLM payload.
Remote providers must never receive raw tracebacks/workflows/env strings by accident.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from sanitizer import PIISanitizer, SanitizationLevel
from security import is_local_llm_url


def get_outbound_sanitizer(base_url: str, privacy_mode: str) -> Tuple[PIISanitizer, bool]:
    """
    Resolve an outbound sanitizer with a hard policy:
    - `privacy_mode=none` is allowed ONLY for verified local providers.
    - Otherwise, downgrade to BASIC.

    Returns: (sanitizer, downgraded_from_none)
    """
    try:
        level = SanitizationLevel(privacy_mode)
    except Exception:
        level = SanitizationLevel.BASIC

    downgraded = False
    if level == SanitizationLevel.NONE and not is_local_llm_url(base_url):
        level = SanitizationLevel.BASIC
        downgraded = True

    return PIISanitizer(level), downgraded


def sanitize_outbound_payload(payload: Any, sanitizer: PIISanitizer) -> Any:
    """
    Recursively sanitize all string values in the outbound payload.
    Leaves non-strings (numbers/bools/etc) intact.
    """
    if sanitizer.level == SanitizationLevel.NONE:
        return payload

    if isinstance(payload, str):
        return sanitizer.sanitize(payload).sanitized_text

    if isinstance(payload, dict):
        sanitized_dict: Dict[str, Any] = {}
        for key, value in payload.items():
            sanitized_dict[key] = sanitize_outbound_payload(value, sanitizer)
        return sanitized_dict

    if isinstance(payload, list):
        return [sanitize_outbound_payload(item, sanitizer) for item in payload]

    return payload

