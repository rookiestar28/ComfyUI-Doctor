import importlib.util
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PRESTARTUP_PATH = REPO_ROOT / "prestartup_script.py"
ASCII_ONLY_FILES = [
    "prestartup_script.py",
    "__init__.py",
    "nodes.py",
    "scripts/check_outbound_safety.py",
    "scripts/lint.ps1",
    "scripts/phase2_gate.py",
    "scripts/phase2_gate.sh",
    "scripts/plugin_allowlist.py",
    "scripts/plugin_hmac_sign.py",
    "scripts/plugin_manifest.py",
    "scripts/plugin_validator.py",
    "scripts/preflight-js.mjs",
    "scripts/r12_ab_harness.py",
    "scripts/run_pattern_tests.py",
    "scripts/run_tests.ps1",
    "tests/test_pattern_loader.py",
    "tests/test_smart_debug.py",
]


def _resolve_repo_file(rel_path: str) -> Path:
    candidate = REPO_ROOT / rel_path
    if candidate.exists():
        return candidate
    if rel_path == "__init__.py":
        backup = REPO_ROOT / "__init__.py.bak"
        if backup.exists():
            return backup
    return candidate

FORBIDDEN_NON_UI_EMOJI = [
    "🏥",
    "🔍",
    "🔎",
    "📋",
    "📂",
    "📖",
    "📊",
    "🧪",
    "🎉",
    "🔐",
    "🚫",
    "ℹ️",
    "✅",
    "❌",
    "⚠️",
    "💡",
    "🎯",
    "🔧",
    "🔒",
    "🟢",
    "📄",
    "🌐",
    "💬",
    "⭐",
    "💝",
    "✓",
    "✗",
]


class AsciiOnlyStream:
    encoding = "cp1252"

    def __init__(self):
        self.messages = []

    def write(self, message):
        if any(ord(ch) > 127 for ch in message):
            raise UnicodeEncodeError("charmap", message, 0, len(message), "non-ascii blocked")
        self.messages.append(message)
        return len(message)

    def flush(self):
        return None

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("no file descriptor")


def test_prestartup_import_is_safe_without_repo_root_on_syspath():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_sys_path = list(sys.path)
    old_env = os.environ.get("COMFYUI_DOCTOR_LOG_PATH")
    module_name = "doctor_r26_prestartup_smoke"
    module = None
    stdout_stream = AsciiOnlyStream()
    stderr_stream = AsciiOnlyStream()

    try:
        sys.stdout = stdout_stream
        sys.stderr = stderr_stream
        repo_root_str = os.path.abspath(str(REPO_ROOT))
        sys.path = [p for p in sys.path if os.path.abspath(p) != repo_root_str]

        spec = importlib.util.spec_from_file_location(module_name, PRESTARTUP_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        assert module.PrestartupLogger.is_installed() is True
        combined_output = "".join(stdout_stream.messages + stderr_stream.messages)
        assert "Prestartup hook activated" in combined_output
        assert "Log file:" in combined_output or "WARNING: log file unavailable" in combined_output
    finally:
        if module is not None:
            try:
                module.PrestartupLogger.uninstall()
            except Exception:
                pass
        sys.modules.pop(module_name, None)
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.path = old_sys_path
        if old_env is None:
            os.environ.pop("COMFYUI_DOCTOR_LOG_PATH", None)
        else:
            os.environ["COMFYUI_DOCTOR_LOG_PATH"] = old_env


def test_prestartup_logger_swallows_unicode_console_failures():
    spec = importlib.util.spec_from_file_location("doctor_r26_prestartup_wrapper", PRESTARTUP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        wrapper = module.PrestartupLogger(AsciiOnlyStream())
        wrapper.write("emoji 💡 should not crash")
        wrapper.flush()
    finally:
        module.PrestartupLogger.uninstall()


def test_non_ui_files_do_not_contain_forbidden_emoji():
    for rel_path in ASCII_ONLY_FILES:
        content = _resolve_repo_file(rel_path).read_text(encoding="utf-8")
        for token in FORBIDDEN_NON_UI_EMOJI:
            assert token not in content, f"{rel_path} still contains forbidden non-UI emoji: {token}"


def test_logger_keeps_legacy_marker_compatibility_but_normalizes_output():
    from logger import _contains_tensor_alert, _normalize_backend_suggestion

    assert _contains_tensor_alert("CRITICAL: Tensor contains NaN") is True
    assert _contains_tensor_alert("WARNING: Meta Tensor (No data)") is True
    assert _contains_tensor_alert("❌ CRITICAL: Tensor contains NaN") is True
    assert _contains_tensor_alert("⚠️ Meta Tensor (No data)") is True
    assert _normalize_backend_suggestion("💡 SUGGESTION: Reduce batch size") == "SUGGESTION: Reduce batch size"
