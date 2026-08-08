from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from terminal_output import (
    ASCII_BANNER_LINES,
    UNICODE_BANNER_LINES,
    DoctorLogFormatter,
    emit_doctor_banner,
    emit_doctor_log,
    format_doctor_log,
    stream_supports_color,
    stream_supports_unicode,
    strip_ansi,
)


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _TTYStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class _PlainStream(io.StringIO):
    def isatty(self) -> bool:
        return False


class StreamWrapper(_PlainStream):
    """Model ComfyUI/Desktop's non-TTY-reporting console wrapper."""


class LogInterceptor(_PlainStream):
    """Model ComfyUI's raw-log preserving stream interceptor."""


class _DoctorWrapper(_PlainStream):
    def __init__(self, original_stream):
        super().__init__()
        self._original_stream = original_stream


class _EncodedPlainStream(_PlainStream):
    def __init__(self, encoding: str):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding


class _RecordingEncodedStream(_EncodedPlainStream):
    def __init__(self, encoding: str):
        super().__init__(encoding)
        self.write_calls: list[str] = []

    def write(self, value: str) -> int:
        self.write_calls.append(value)
        return super().write(value)


def test_plain_format_uses_one_canonical_identity_and_safe_level_fallback():
    assert format_doctor_log("ready", "INFO") == "[ComfyUI-Doctor INFO] ready"
    assert format_doctor_log("ready", "not-a-level") == "[ComfyUI-Doctor INFO] ready"
    assert format_doctor_log("café", "WARNING") == "[ComfyUI-Doctor WARNING] caf\\xe9"
    assert format_doctor_log("unsafe \x1b[31mred\x1b[0m", "ERROR") == (
        "[ComfyUI-Doctor ERROR] unsafe red"
    )


def test_color_format_matches_comfyui_palette_and_colors_only_level():
    expected_colors = {
        "DEBUG": "\x1b[36m",
        "DETAIL": "\x1b[34m",
        "INFO": "\x1b[32m",
        "WARNING": "\x1b[33m",
        "ERROR": "\x1b[31m",
        "CRITICAL": "\x1b[35m",
    }

    for level, color in expected_colors.items():
        rendered = format_doctor_log("message", level, color_enabled=True)
        assert strip_ansi(rendered) == f"[ComfyUI-Doctor {level}] message"
        assert color in rendered
        assert ("\x1b[1m" in rendered) is (level in {"WARNING", "ERROR", "CRITICAL"})
        assert rendered.startswith("[ComfyUI-Doctor ")
        assert rendered.endswith("] message")


def test_color_capability_requires_tty_and_honors_no_color():
    assert stream_supports_color(_TTYStream(), environ={}) is True
    assert stream_supports_color(_PlainStream(), environ={}) is False
    assert stream_supports_color(_TTYStream(), environ={"NO_COLOR": "1"}) is False


def test_color_capability_recognizes_comfyui_wrapper_even_when_isatty_is_false():
    host_stream = StreamWrapper()
    interceptor = LogInterceptor()
    doctor_stream = _DoctorWrapper(host_stream)

    assert host_stream.isatty() is False
    assert stream_supports_color(host_stream, environ={}) is True
    assert stream_supports_color(interceptor, environ={}) is True
    assert stream_supports_color(doctor_stream, environ={}) is True
    assert stream_supports_color(doctor_stream, environ={"NO_COLOR": "1"}) is False


def test_emitter_prefixes_every_line_and_plain_sink_has_no_ansi():
    stream = _PlainStream()
    emitted = emit_doctor_log("first\nsecond", "DETAIL", stream=stream)

    assert emitted == [
        "[ComfyUI-Doctor DETAIL] first",
        "[ComfyUI-Doctor DETAIL] second",
    ]
    assert stream.getvalue() == "[ComfyUI-Doctor DETAIL] first\n[ComfyUI-Doctor DETAIL] second\n"
    assert ANSI_RE.search(stream.getvalue()) is None


def test_logging_formatter_keeps_file_output_plain_and_canonical():
    record = logging.LogRecord("doctor", logging.ERROR, __file__, 1, "failed %s", ("safely",), None)
    formatter = DoctorLogFormatter(include_timestamp=False, color_enabled=False)

    assert formatter.format(record) == "[ComfyUI-Doctor ERROR] failed safely"
    assert ANSI_RE.search(formatter.format(record)) is None


def test_banner_restores_original_large_unicode_art_with_ascii_fallback():
    assert len(UNICODE_BANNER_LINES) == 6
    assert UNICODE_BANNER_LINES[0].startswith("   ██████╗ ██████╗")
    assert UNICODE_BANNER_LINES[-1].endswith("╚═╝  ╚═╝")
    assert all("COMFYUI-DOCTOR" not in line for line in UNICODE_BANNER_LINES)
    assert any(not line.isascii() for line in UNICODE_BANNER_LINES)

    assert len(ASCII_BANNER_LINES) >= 3
    assert any("COMFYUI-DOCTOR" in line for line in ASCII_BANNER_LINES)
    assert all(line.isascii() for line in ASCII_BANNER_LINES)

    unicode_stream = _EncodedPlainStream("utf-8")
    emitted_unicode = emit_doctor_banner(
        stream=unicode_stream,
        color_enabled=False,
        unicode_enabled=True,
    )
    unicode_lines = unicode_stream.getvalue().splitlines()
    assert emitted_unicode[0] == "[ComfyUI-Doctor INFO] Startup banner:"
    assert unicode_lines[0] == "[ComfyUI-Doctor INFO] Startup banner:"
    assert tuple(unicode_lines[1:]) == UNICODE_BANNER_LINES

    ascii_stream = _EncodedPlainStream("cp1252")
    emitted_ascii = emit_doctor_banner(
        stream=ascii_stream,
        color_enabled=False,
        unicode_enabled=False,
    )
    ascii_lines = ascii_stream.getvalue().splitlines()
    assert emitted_ascii[0] == "[ComfyUI-Doctor INFO] Startup banner:"
    assert tuple(ascii_lines[1:]) == ASCII_BANNER_LINES
    assert ascii_stream.getvalue().isascii()


def test_unicode_banner_capability_follows_wrapped_stream_encoding():
    utf8_stream = _EncodedPlainStream("utf-8")
    cp1252_stream = _EncodedPlainStream("cp1252")

    assert stream_supports_unicode(utf8_stream) is True
    assert stream_supports_unicode(_DoctorWrapper(utf8_stream)) is True
    assert stream_supports_unicode(cp1252_stream) is False
    assert stream_supports_unicode(_DoctorWrapper(cp1252_stream)) is False


def test_banner_art_is_written_as_one_tightly_packed_block():
    stream = _RecordingEncodedStream("utf-8")

    emit_doctor_banner(
        stream=stream,
        color_enabled=False,
        unicode_enabled=True,
    )

    assert len(stream.write_calls) == 2
    assert stream.write_calls[0] == "[ComfyUI-Doctor INFO] Startup banner:\n"
    assert stream.write_calls[1] == "\n".join(UNICODE_BANNER_LINES) + "\n"
    assert "\n\n" not in stream.write_calls[1]


def test_entrypoint_has_one_banner_lifecycle_call_and_no_legacy_placeholder():
    source = (PROJECT_ROOT / "__init__.py").read_text(encoding="utf-8")

    assert source.count("emit_doctor_banner(stream=sys.stdout)") == 1
    assert "=== COMFYUI DOCTOR ===" not in source


def test_active_emitters_do_not_contain_legacy_identity_literals():
    production_files = (
        "__init__.py",
        "prestartup_script.py",
        "api_routes.py",
        "history_store.py",
        "telemetry.py",
    )
    forbidden = ("[ComfyUI-Doctor]", "[Doctor]", "[Doctor-API]", "[Doctor-Internal]")

    for relative_path in production_files:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{relative_path} still contains active legacy marker {marker}"
