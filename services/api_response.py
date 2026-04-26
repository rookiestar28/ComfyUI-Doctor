"""Shared JSON response helpers for Doctor API routes."""

from __future__ import annotations

from typing import Any, Mapping


def error_payload(message: Any, code: str | None = None, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the standard Doctor API error envelope."""
    text = str(message)
    payload: dict[str, Any] = {
        "success": False,
        "error": code or text,
        "message": text,
    }
    if extra:
        payload.update(dict(extra))
    return payload


def error_response(web, message: Any, status: int, code: str | None = None, extra: Mapping[str, Any] | None = None):
    """Return a standardized JSON error response without importing aiohttp at module import time."""
    return web.json_response(error_payload(message, code=code, extra=extra), status=status)


def admin_denied_response(web, code: str, message: str):
    """Return the standard admin denial response while preserving 401/403 semantics."""
    status_code = 401 if code == "unauthorized" else 403
    return error_response(web, message, status_code, code=code)
