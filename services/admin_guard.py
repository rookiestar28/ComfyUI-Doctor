"""
Admin guard helpers for write-sensitive endpoints.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Any, Dict, Optional, Tuple


def _is_truthy(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_admin_token() -> str:
    return os.getenv("DOCTOR_ADMIN_TOKEN", "").strip()


def is_remote_admin_allowed() -> bool:
    return _is_truthy(os.getenv("DOCTOR_ALLOW_REMOTE_ADMIN", "0"))


def is_loopback_request(request: Any) -> bool:
    remote = (getattr(request, "remote", None) or "").strip()
    if not remote:
        # Fallback to transport peername if available
        try:
            peer = request.transport.get_extra_info("peername")
            if isinstance(peer, tuple) and peer:
                remote = str(peer[0])
        except Exception:
            remote = ""

    if not remote:
        return False

    if remote in {"localhost", "::1"}:
        return True

    try:
        return ipaddress.ip_address(remote).is_loopback
    except Exception:
        return False


def _extract_admin_token(request: Any, payload: Optional[Dict[str, Any]] = None) -> str:
    body_token = ((payload or {}).get("admin_token") or "").strip()
    if body_token:
        return body_token

    header_token = (
        request.headers.get("X-Doctor-Admin-Token", "").strip()
        or request.headers.get("X-Admin-Token", "").strip()
    )
    if header_token:
        return header_token

    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def validate_admin_request(request: Any, payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
    """
    Returns: (allowed, code, message)
    codes: ok | unauthorized | remote_admin_denied
    """
    configured_token = get_admin_token()
    provided_token = _extract_admin_token(request, payload=payload)

    if configured_token:
        if provided_token and provided_token == configured_token:
            return True, "ok", "authorized"
        return False, "unauthorized", "Invalid or missing admin token"

    # Convenience mode: no token configured.
    if is_loopback_request(request):
        return True, "ok", "authorized (loopback convenience mode)"

    if is_remote_admin_allowed():
        return True, "ok", "authorized (remote opt-in)"

    return False, "remote_admin_denied", "Remote admin denied by default; set DOCTOR_ALLOW_REMOTE_ADMIN=1"
