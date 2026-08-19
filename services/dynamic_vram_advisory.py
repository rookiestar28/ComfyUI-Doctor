"""Bounded nonfatal advisory for source-pinned DynamicVRAM fallbacks."""

from __future__ import annotations

import sys
import threading
from collections import deque
from collections.abc import Mapping
from typing import Any

from .time_utils import utc_isoformat

try:
    from ..terminal_output import strip_ansi
except ImportError as import_error:
    from import_compat import ensure_absolute_import_fallback_allowed

    ensure_absolute_import_fallback_allowed(import_error)
    from terminal_output import strip_ansi


PYTORCH_FALLBACK_WARNING = (
    "Unsupported Pytorch detected. DynamicVRAM support requires Pytorch version "
    "2.8 or later. Falling back to legacy ModelPatcher. VRAM estimates may be "
    "unreliable especially on Windows"
)
COMFY_AIMDO_FALLBACK_WARNING = (
    "No working comfy-aimdo install detected. DynamicVRAM support disabled. "
    "Falling back to legacy ModelPatcher. VRAM estimates may be unreliable "
    "especially on Windows"
)
DYNAMIC_VRAM_RECOMMENDATION = (
    "Automatic DynamicVRAM requires PyTorch 2.8 or later and working comfy-aimdo; "
    "ComfyUI base support remains PyTorch 2.7."
)

MAX_HOST_LOG_ENTRIES = 300
MAX_REPEAT_COUNT = 65535
MAX_REASON_CODES = 2

_WARNING_PREFIX = "[WARNING] "
_REASON_ORDER = ("pytorch_threshold", "comfy_aimdo_unavailable")
_WARNING_REASONS = {
    PYTORCH_FALLBACK_WARNING: "pytorch_threshold",
    COMFY_AIMDO_FALLBACK_WARNING: "comfy_aimdo_unavailable",
}

_state_lock = threading.RLock()
_active_state: dict[str, Any] | None = None


def classify_dynamic_vram_warning(message: object) -> str | None:
    """Return an allowlisted reason only for an exact current host warning."""
    if not isinstance(message, str):
        return None

    normalized = strip_ansi(message).strip()
    if normalized.startswith(_WARNING_PREFIX):
        normalized = normalized[len(_WARNING_PREFIX) :].strip()
    return _WARNING_REASONS.get(normalized)


def _record_reason(reason: str) -> bool:
    if reason not in _REASON_ORDER:
        return False

    now = utc_isoformat()
    with _state_lock:
        global _active_state
        if _active_state is None:
            _active_state = {
                "reasons": {reason},
                "repeat_count": 1,
                "first_seen": now,
                "last_seen": now,
            }
            return True

        reasons = _active_state["reasons"]
        if len(reasons) < MAX_REASON_CODES:
            reasons.add(reason)
        _active_state["repeat_count"] = min(
            int(_active_state["repeat_count"]) + 1,
            MAX_REPEAT_COUNT,
        )
        _active_state["last_seen"] = now
        return True


def record_dynamic_vram_warning(message: object) -> bool:
    """Record one exact warning without retaining the source line."""
    reason = classify_dynamic_vram_warning(message)
    if reason is None:
        return False
    return _record_reason(reason)


def get_dynamic_vram_advisory() -> dict[str, Any]:
    """Return a caller-owned, allowlisted health projection."""
    with _state_lock:
        if _active_state is None:
            return {"active": False}
        try:
            reasons = _active_state["reasons"]
            ordered_reasons = [reason for reason in _REASON_ORDER if reason in reasons]
            repeat_count = int(_active_state["repeat_count"])
            first_seen = str(_active_state["first_seen"])
            last_seen = str(_active_state["last_seen"])
        except (KeyError, TypeError, ValueError):
            return {"active": False}

        return {
            "active": True,
            "kind": "dynamic_vram_fallback",
            "severity": "warning",
            "fatal": False,
            "reasons": ordered_reasons,
            "title": "DynamicVRAM fallback",
            "message": "Automatic DynamicVRAM fell back to legacy ModelPatcher.",
            "recommendation": DYNAMIC_VRAM_RECOMMENDATION,
            "repeat_count": repeat_count,
            "first_seen": first_seen,
            "last_seen": last_seen,
        }


def clear_dynamic_vram_advisory() -> None:
    """Clear only the nonfatal advisory; runtime error state is independent."""
    with _state_lock:
        global _active_state
        _active_state = None


def replay_host_dynamic_vram_advisory() -> bool:
    """Replay one bounded snapshot from the already-loaded public host log API."""
    # CRITICAL: do not import app.logger here. DynamicVRAM warnings predate
    # custom-node loading, so only the already-loaded public buffer is in scope.
    host_logger = sys.modules.get("app.logger")
    if host_logger is None:
        return False

    try:
        get_logs = host_logger.get_logs
        if not callable(get_logs):
            return False
        source = get_logs()
        if type(source) not in (list, tuple, deque):
            return False

        source_length = len(source)
        if source_length > MAX_HOST_LOG_ENTRIES:
            return False
        snapshot = list(source)
        if len(source) != source_length or len(snapshot) != source_length:
            return False

        messages: list[str] = []
        for entry in snapshot:
            if not isinstance(entry, Mapping):
                return False
            message = entry.get("m")
            if not isinstance(message, str):
                return False
            messages.append(message)
    except Exception:
        return False

    reasons = [classify_dynamic_vram_warning(message) for message in messages]
    matched = False
    for reason in reasons:
        if reason is not None:
            matched = _record_reason(reason) or matched
    return matched
