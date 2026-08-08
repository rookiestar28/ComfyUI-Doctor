"""Canonical terminal formatting for ComfyUI-Doctor backend output.

This module intentionally depends only on the Python standard library. The
prestartup hook loads it by file path before the custom-node package is
importable, while normal package modules import it relatively.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Mapping
from typing import TextIO


DOCTOR_IDENTITY = "ComfyUI-Doctor"
DOCTOR_LEVELS = ("DEBUG", "DETAIL", "INFO", "WARNING", "ERROR", "CRITICAL")

_ANSI_COLORS = {
    "DEBUG": "\033[36m",
    "DETAIL": "\033[34m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
_ANSI_BOLD = "\033[1m"
_ANSI_RESET = "\033[0m"
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_BOLD_LEVELS = frozenset({"WARNING", "ERROR", "CRITICAL"})
_HOST_COLOR_STREAM_TYPES = frozenset({"LogInterceptor", "StreamWrapper"})
_WRAPPED_STREAM_ATTRIBUTES = ("_original_stream", "stream")


ASCII_BANNER_LINES = (
    "+-----------------------------------------------------------+",
    "|                     COMFYUI-DOCTOR                       |",
    "|              Startup diagnostics are active              |",
    "+-----------------------------------------------------------+",
)

# Original banner from bbe2c23. It is Unicode block art (not strict ASCII),
# so emit_doctor_banner selects it only when the effective stream can encode it.
UNICODE_BANNER_LINES = (
    "   ██████╗ ██████╗ ███╗   ███╗███████╗██╗   ██╗██╗   ██╗██╗      ██████╗  ██████╗  ██████╗████████╗ ██████╗ ██████╗ ",
    "  ██╔════╝██╔═══██╗████╗ ████║██╔════╝╚██╗ ██╔╝██║   ██║██║      ██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗",
    "  ██║     ██║   ██║██╔████╔██║█████╗   ╚████╔╝ ██║   ██║██║█████╗██║  ██║██║   ██║██║        ██║   ██║   ██║██████╔╝",
    "  ██║     ██║   ██║██║╚██╔╝██║██╔══╝    ╚██╔╝  ██║   ██║██║╚════╝██║  ██║██║   ██║██║        ██║   ██║   ██║██╔══██╗",
    "  ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║        ██║   ╚██████╔╝██║      ██████╔╝╚██████╔╝╚██████╗   ██║   ╚██████╔╝██║  ██║",
    "   ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝        ╚═╝    ╚═════╝ ╚═╝      ╚═════╝  ╚═════╝  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
)


def _iter_stream_chain(stream: TextIO | None):
    current = stream
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        yield current

        wrapped_stream = None
        for attribute in _WRAPPED_STREAM_ATTRIBUTES:
            candidate = getattr(current, attribute, None)
            if candidate is not None and candidate is not current:
                wrapped_stream = candidate
                break
        current = wrapped_stream


def _ascii_safe(value: object) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def normalize_doctor_level(level: object) -> str:
    """Return a supported host-aligned severity without blocking startup."""
    normalized = str(level or "INFO").strip().upper()
    return normalized if normalized in DOCTOR_LEVELS else "INFO"


def strip_ansi(value: object) -> str:
    """Remove SGR color/style sequences before Doctor-owned persistence."""
    return _ANSI_RE.sub("", str(value))


def stream_supports_color(
    stream: TextIO | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return whether a stream should receive Doctor severity highlighting."""
    if stream is None:
        return False
    environment = os.environ if environ is None else environ
    if "NO_COLOR" in environment or environment.get("TERM", "").lower() == "dumb":
        return False

    # CRITICAL: ComfyUI/Desktop console wrappers can report isatty() == False
    # even while the host's ColoredFormatter emits ANSI on the same transport.
    for current in _iter_stream_chain(stream):
        if type(current).__name__ in _HOST_COLOR_STREAM_TYPES:
            return True
        try:
            if current.isatty():
                return True
        except (AttributeError, OSError, ValueError):
            pass

    return False


def stream_supports_unicode(stream: TextIO | None) -> bool:
    """Return whether the effective stream can encode the historical banner."""
    banner_text = "\n".join(UNICODE_BANNER_LINES)
    for current in _iter_stream_chain(stream):
        encoding = getattr(current, "encoding", None)
        if not encoding:
            continue
        try:
            banner_text.encode(str(encoding), "strict")
            return True
        except (LookupError, UnicodeEncodeError):
            return False
    return False


def format_doctor_log(
    message: object,
    level: object = "INFO",
    *,
    color_enabled: bool = False,
) -> str:
    """Render one ASCII-safe Doctor line with a canonical identity token."""
    safe_level = normalize_doctor_level(level)
    safe_message = strip_ansi(_ascii_safe(message))
    safe_message = safe_message.replace("\x1b", "\\x1b").replace("\r", "\\r").replace("\n", "\\n")
    rendered_level = safe_level
    if color_enabled:
        bold = _ANSI_BOLD if safe_level in _BOLD_LEVELS else ""
        rendered_level = f"{bold}{_ANSI_COLORS[safe_level]}{safe_level}{_ANSI_RESET}"
    prefix = f"[{DOCTOR_IDENTITY} {rendered_level}]"
    return f"{prefix} {safe_message}" if safe_message else prefix


def emit_doctor_log(
    message: object,
    level: object = "INFO",
    *,
    stream: TextIO | None = None,
    color_enabled: bool | None = None,
) -> list[str]:
    """Write canonical Doctor lines and return their plain representations.

    Multiline input is split so every physical line has an owner and severity.
    Output failures are best-effort because Doctor must never block host startup.
    """
    target = sys.stdout if stream is None else stream
    raw_message = str(message)
    logical_lines = raw_message.splitlines() or [""]
    use_color = stream_supports_color(target) if color_enabled is None else bool(color_enabled)
    plain_lines: list[str] = []

    for logical_line in logical_lines:
        plain_line = format_doctor_log(logical_line, level, color_enabled=False)
        rendered_line = format_doctor_log(logical_line, level, color_enabled=use_color)
        plain_lines.append(plain_line)
        try:
            target.write(rendered_line + "\n")
        except (AttributeError, OSError, UnicodeError, ValueError):
            continue

    try:
        target.flush()
    except (AttributeError, OSError, UnicodeError, ValueError):
        pass
    return plain_lines


def emit_doctor_banner(
    *,
    stream: TextIO | None = None,
    color_enabled: bool | None = None,
    unicode_enabled: bool | None = None,
) -> list[str]:
    """Emit one canonical header plus an aligned, encoding-safe banner."""
    target = sys.stdout if stream is None else stream
    use_unicode = stream_supports_unicode(target) if unicode_enabled is None else unicode_enabled
    banner_lines = UNICODE_BANNER_LINES if use_unicode else ASCII_BANNER_LINES
    emitted = emit_doctor_log(
        "Startup banner:",
        "INFO",
        stream=target,
        color_enabled=color_enabled,
    )
    # IMPORTANT: keep the art in one write; host wrappers may space writes as separate log entries.
    banner_block = "\n".join(banner_lines) + "\n"
    try:
        target.write(banner_block)
        emitted.extend(banner_lines)
    except (AttributeError, OSError, UnicodeError, ValueError):
        pass
    try:
        target.flush()
    except (AttributeError, OSError, UnicodeError, ValueError):
        pass
    return emitted


class DoctorLogFormatter(logging.Formatter):
    """Logging formatter for handlers owned by ComfyUI-Doctor."""

    def __init__(
        self,
        *,
        include_timestamp: bool = False,
        color_enabled: bool = False,
        datefmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        super().__init__(datefmt=datefmt)
        self.include_timestamp = include_timestamp
        self.color_enabled = color_enabled

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            message = f"{message}\n{exception_text}" if message else exception_text

        lines = str(message).splitlines() or [""]
        rendered = [
            format_doctor_log(line, record.levelname, color_enabled=self.color_enabled)
            for line in lines
        ]
        if self.include_timestamp:
            timestamp = self.formatTime(record, self.datefmt)
            rendered = [f"[{timestamp}] {line}" for line in rendered]
        return "\n".join(rendered)
