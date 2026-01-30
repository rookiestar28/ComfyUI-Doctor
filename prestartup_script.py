"""
ComfyUI-Doctor Prestartup Script
This runs BEFORE any custom nodes are imported.
Installs the SmartLogger as early as possible to capture all import errors.
"""

import sys
import os
import datetime
import tempfile

# R18: Prefer canonical Doctor data dir for persisted logs (Desktop-safe)
try:
    from services.doctor_paths import get_doctor_data_dir as _get_doctor_data_dir
except Exception:
    _get_doctor_data_dir = None

# Get the directory of this script (ComfyUI-Doctor folder)
DOCTOR_DIR = os.path.dirname(os.path.abspath(__file__))
_FALLBACK_LOG_DIR = os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor", "logs")

def _resolve_log_dir() -> str:
    """
    Resolve a writable log directory for the earliest capture phase.

    IMPORTANT:
    - Never assume the extension folder is writable (ComfyUI Desktop resources may be read-only).
    - Never raise here; prestartup must not break ComfyUI startup.
    """
    if _get_doctor_data_dir:
        try:
            return os.path.join(_get_doctor_data_dir(), "logs")
        except Exception:
            pass
    return _FALLBACK_LOG_DIR

LOG_DIR = _resolve_log_dir()

# Ensure logs directory exists
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    LOG_DIR = _FALLBACK_LOG_DIR
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        LOG_DIR = ""

# Generate log filename
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_PATH = os.path.join(LOG_DIR, f"comfyui_debug_{timestamp}.log") if LOG_DIR else ""

# ============================================================
# Minimal Logger (Prestartup Phase)
# A lightweight version that just captures output to file.
# Full analysis capabilities will be loaded in __init__.py later.
# ============================================================

class PrestartupLogger:
    """
    Minimal stdout/stderr interceptor for the prestartup phase.
    Captures output to log file before full logger is available.
    """
    _original_stdout = None
    _original_stderr = None
    _log_file = None
    _installed = False

    @classmethod
    def install(cls, log_path):
        if cls._installed:
            return
        
        cls._original_stdout = sys.stdout
        cls._original_stderr = sys.stderr
        cls._log_file = None
        if log_path:
            try:
                cls._log_file = open(log_path, "a", encoding="utf-8")
            except Exception:
                cls._log_file = None
        
        sys.stdout = cls(cls._original_stdout)
        sys.stderr = cls(cls._original_stderr)
        cls._installed = True
    
    @classmethod
    def get_log_path(cls):
        return LOG_PATH
    
    @classmethod
    def is_installed(cls):
        return cls._installed

    @classmethod
    def uninstall(cls):
        if not cls._installed:
            return
        # Restore original streams if we still have them
        try:
            if cls._original_stdout:
                sys.stdout = cls._original_stdout
            if cls._original_stderr:
                sys.stderr = cls._original_stderr
        except Exception:
            pass

        # Close log file handle
        try:
            if cls._log_file:
                cls._log_file.flush()
                cls._log_file.close()
        except Exception:
            pass

        cls._log_file = None
        cls._original_stdout = None
        cls._original_stderr = None
        cls._installed = False

    def __init__(self, stream):
        self.stream = stream

    def write(self, message):
        try:
            self.stream.write(message)
            self.stream.flush()
        except (OSError, AttributeError):
            pass  # Stream may be unavailable during early startup
        try:
            if PrestartupLogger._log_file:
                PrestartupLogger._log_file.write(message)
                PrestartupLogger._log_file.flush()
        except (OSError, AttributeError):
            pass  # Log file may be unavailable

    def flush(self):
        try:
            self.stream.flush()
            if PrestartupLogger._log_file:
                PrestartupLogger._log_file.flush()
        except (OSError, AttributeError):
            pass  # Stream or file may be unavailable

    @property
    def encoding(self):
        return getattr(self.stream, 'encoding', 'utf-8')

    def isatty(self):
        return getattr(self.stream, 'isatty', lambda: False)()

    def fileno(self):
        try:
            return self.stream.fileno()
        except Exception:
            return -1


# Install minimal logger IMMEDIATELY
PrestartupLogger.install(LOG_PATH)

print(f"\n[ComfyUI-Doctor] 🏥 Prestartup hook activated (EARLY CAPTURE)")
if LOG_PATH:
    print(f"[ComfyUI-Doctor] 📄 Log file: {LOG_PATH}")
else:
    print("[ComfyUI-Doctor] ⚠️ Log file: unavailable (fallback disabled)")

# Store log path for __init__.py to retrieve
if LOG_PATH:
    os.environ["COMFYUI_DOCTOR_LOG_PATH"] = LOG_PATH
