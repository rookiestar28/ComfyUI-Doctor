"""
Test fixtures for outbound safety violations.
This file should NOT pass the static check.
"""
import aiohttp
import json


async def violation_1_raw_field_in_payload(context):
    """BAD: Direct context field in payload."""
    payload = {
        "error": context.traceback,  # VIOLATION
        "workflow": context.workflow_json  # VIOLATION
    }
    await session.post(url, json=payload)


async def violation_2_dangerous_fallback(context):
    """BAD: Dangerous or fallback."""
    data = {
        "traceback": context.sanitized_traceback or context.traceback  # VIOLATION
    }
    return data


async def violation_3_post_without_sanitization(context):
    """BAD: POST without sanitize_outbound_payload."""
    sanitizer, _ = get_outbound_sanitizer(base_url, privacy_mode)
    payload = {"data": "test"}
    await session.post(url, json=payload)  # VIOLATION - never sanitized


def violation_4_json_dumps_raw(context):
    """BAD: json.dumps on raw field."""
    return json.dumps({
        "system": context.system_info  # VIOLATION
    })


async def violation_5_nested_raw_field(context):
    """BAD: Nested raw field."""
    payload = {
        "analysis": {
            "details": {
                "trace": context.traceback  # VIOLATION - deep nesting
            }
        }
    }
    await session.post(url, json=payload)
