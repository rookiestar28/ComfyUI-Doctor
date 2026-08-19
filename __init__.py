"""
ComfyUI Doctor - Main Entry Point

This module initializes the smart debugging system on ComfyUI startup.
Features:
- Automatic log capture from startup
- System environment snapshot
- Error analysis with suggestions
- API endpoint for frontend integration

===========================================================================
CRITICAL: Relative Import Warning for Test Maintainers
===========================================================================
This module uses RELATIVE IMPORTS (from .logger import ...) which is REQUIRED
for ComfyUI custom node extensions.

DO NOT change to absolute imports (from logger import ...) as this will:
  - Break ComfyUI's module loading system
  - Cause "ModuleNotFoundError" when ComfyUI tries to load this extension

IMPORTANT FOR TESTING:
  - pytest collection is isolated to tests and must not move or rename this file
  - See tests/conftest.py for root-entrypoint collection exclusion
  - See pytest.ini for importlib-mode configuration

If pytest fails with "attempted relative import with no known parent package":
  1. Check that pytest.ini has "addopts = --import-mode=importlib"
  2. Check that tests/conftest.py excludes the root entrypoint from collection
  3. Do NOT modify these imports - the issue is in test configuration

Last Modified: 2026-08-08 (Removed entrypoint-mutation workaround)
===========================================================================
"""

import sys
import os
import glob
import datetime
import platform
import json
import re
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ============================================================================
# CRITICAL: DO NOT change these to absolute imports
# These MUST be relative imports for ComfyUI compatibility
# ============================================================================
from .logger import SmartLogger, get_last_analysis, get_analysis_history, clear_analysis_history, get_logger_metrics
from .services.dynamic_vram_advisory import (
    clear_dynamic_vram_advisory,
    get_dynamic_vram_advisory,
)
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .i18n import set_language, get_language, get_ui_text, SUPPORTED_LANGUAGES, UI_TEXT
from .config import CONFIG
from .analyzer import ErrorAnalyzer
from .session_manager import SessionManager
from .system_info import get_system_environment, format_env_for_llm
from .sanitizer import PIISanitizer, SanitizationLevel
from .security import is_local_llm_url, validate_ssrf_url, get_ssrf_metrics
from .outbound import get_outbound_sanitizer, sanitize_outbound_payload
from .llm_client import llm_request_with_retry, RetryConfig, RetryResult
from .services.token_budget import TokenBudgetService, BudgetConfig
from .services.prompt_composer import get_prompt_composer, PromptComposerConfig
from .services.doctor_paths import get_doctor_data_dir, get_path_diagnostics
from .services.llm_keys import resolve_api_key, get_provider_status
from .services.secret_store import get_secret_store
from .services.admin_guard import get_admin_guard_startup_warning, validate_admin_request
from .services.api_response import admin_denied_response, error_response
from .services.llm_provider_adapters import get_llm_provider_adapter
from .services.audit import ActionAudit
from .services.community_feedback import build_feedback_preview, submit_feedback, GitHubFeedbackConfig, FeedbackValidationError
from .terminal_output import (
    DoctorLogFormatter,
    emit_doctor_banner,
    emit_doctor_log,
    stream_supports_color,
)

# Global R12 Service
TOKEN_BUDGET_SERVICE = TokenBudgetService()


# R7: Apply configurable rate/concurrency limits from CONFIG
SessionManager.configure_limits(
    core_rate_limit=getattr(CONFIG, "llm_core_rate_limit", None),
    light_rate_limit=getattr(CONFIG, "llm_light_rate_limit", None),
    max_concurrent=getattr(CONFIG, "llm_max_concurrent", None),
    rate_window_seconds=getattr(getattr(CONFIG, "guardrails", None), "RATE_LIMIT_WINDOW_SECONDS", None),
)
SessionManager.configure_proxy_policy(
    config_policy=getattr(CONFIG, "llm_proxy_policy", None),
    env_policy=os.getenv(SessionManager.ENV_PROXY_POLICY_KEY),
)


def _close_retry_response(result: RetryResult) -> None:
    resp = getattr(result, "response", None)
    if resp is None:
        return
    try:
        resp.close()
    except Exception:
        pass


def _admin_denied_response(code: str, message: str):
    """Standardized admin denial response payload/status for write-sensitive APIs."""
    return admin_denied_response(web, code, message)


def _error_response(message: str, status: int, code: str | None = None, extra: dict | None = None):
    """Standardized Doctor API error response payload/status."""
    return error_response(web, message, status, code=code, extra=extra)


def _startup_print(message: str = "", level: str = "INFO") -> None:
    emit_doctor_log(message, level, stream=sys.stdout)

# --- LLM Environment Variable Fallbacks ---
# These can be set in system environment to provide default values
DOCTOR_LLM_API_KEY = os.getenv("DOCTOR_LLM_API_KEY")
DOCTOR_LLM_BASE_URL = os.getenv("DOCTOR_LLM_BASE_URL", "https://api.openai.com/v1")
DOCTOR_LLM_MODEL = os.getenv("DOCTOR_LLM_MODEL", "gpt-4o")

# --- Local LLM Service URLs (Environment Variable Support) ---
# Allows cross-platform compatibility (Windows vs WSL2, Docker, etc.)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

# --- 1. Setup Log Directory (Local to Node) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# R18: Prefer canonical Doctor data dir for persisted logs (Desktop-safe)
log_dir = os.path.join(get_doctor_data_dir(), "logs")

if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        _startup_print(f"Could not create log directory: {e}", "WARNING")


# --- 2. Log File Cleanup ---
def cleanup_old_logs(log_directory: str, max_files: int = 10) -> None:
    """
    Keep only the most recent N log files, delete older ones.
    
    Args:
        log_directory: Path to the logs directory.
        max_files: Maximum number of log files to keep.
    """
    try:
        log_files = sorted(glob.glob(os.path.join(log_directory, "comfyui_debug_*.log")))
        if len(log_files) > max_files:
            for old_file in log_files[:-max_files]:
                try:
                    os.remove(old_file)
                except OSError:
                    pass  # File may be locked, continue with others
    except OSError:
        pass  # Directory access may fail, silently continue


cleanup_old_logs(log_dir, CONFIG.max_log_files)


# --- 3. Check if Prestartup Logger is already installed ---
prestartup_log_path = os.environ.get("COMFYUI_DOCTOR_LOG_PATH")

if prestartup_log_path and os.path.exists(prestartup_log_path):
    # Prestartup logger was installed - use the same log file
    log_path = prestartup_log_path
    _startup_print("Upgrading from prestartup logger...")
    _startup_print(f"Using existing log: {log_path}")
else:
    # No prestartup logger - generate new log filename
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"comfyui_debug_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)
    _startup_print("Initializing smart debugger...")
    _startup_print(f"Log file: {log_path}")


# --- 4. Install/Upgrade to Full Smart Logger ---
# This will replace the minimal PrestartupLogger with the full-featured SmartLogger
def _handoff_prestartup_logger():
    """
    Best-effort cleanup of the prestartup logger to avoid leaked file handles.
    This does NOT import prestartup_script.py to avoid re-running its side effects.
    """
    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", "")
        if not module_file:
            continue
        if module_file.endswith("prestartup_script.py"):
            pre_logger = getattr(module, "PrestartupLogger", None)
            if pre_logger and hasattr(pre_logger, "uninstall"):
                try:
                    pre_logger.uninstall()
                    _startup_print("Prestartup logger handoff complete")
                except Exception as handoff_error:
                    _startup_print(f"Prestartup logger handoff failed: {handoff_error}", "WARNING")
            break

_handoff_prestartup_logger()
SmartLogger.install(log_path)


# --- 5. Setup API Logger for Doctor Operations ---
def setup_api_logger():
    """
    Create a dedicated logger for API operations.
    Logs to logs/api_operations.log (separate from SmartLogger's error logs).
    """
    api_logger = logging.getLogger('ComfyUI-Doctor-API')

    # Prevent duplicate handlers if called multiple times
    if api_logger.handlers:
        return api_logger

    api_logger.setLevel(logging.INFO)

    # File handler with rotation (max 5MB, keep 3 backups)
    api_log_path = os.path.join(log_dir, 'api_operations.log')
    file_handler = RotatingFileHandler(
        api_log_path,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )

    # Doctor-owned files stay canonical and ANSI-free.
    formatter = DoctorLogFormatter(include_timestamp=True, color_enabled=False)
    file_handler.setFormatter(formatter)
    api_logger.addHandler(file_handler)

    # Console handler for terminal output (user requested visibility)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = DoctorLogFormatter(
        include_timestamp=False,
        color_enabled=stream_supports_color(sys.stdout),
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    api_logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate console output)
    api_logger.propagate = False

    return api_logger

# Initialize logger
logger = setup_api_logger()
_startup_print(f"API logger initialized: {os.path.join(log_dir, 'api_operations.log')}")

admin_guard_warning = get_admin_guard_startup_warning()
if admin_guard_warning:
    logger.warning(admin_guard_warning)


# --- 5. Log System Information (Hardware Snapshot) ---
def log_system_info() -> None:
    """Log system and hardware information at startup."""
    emit_doctor_banner(stream=sys.stdout)
    _startup_print(f"{'='*20} SYSTEM SNAPSHOT {'='*20}")
    _startup_print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    _startup_print(f"Python: {sys.version.split()[0]}")
    
    try:
        import torch
        _startup_print(f"PyTorch: {torch.__version__}")
        _startup_print(f"CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            _startup_print(f"CUDA Version: {torch.version.cuda}")
            device_count = torch.cuda.device_count()
            _startup_print(f"GPU Count: {device_count}")
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                _startup_print(f"  GPU {i}: {props.name} (VRAM: {props.total_memory / 1024**3:.2f} GB)")
    except ImportError:
        _startup_print("PyTorch: Not Installed (or not found in this env)")
    
    # Log ComfyUI Arguments if available
    _startup_print(f"Args: {sys.argv}")
    _startup_print(f"{'='*57}\n")

log_system_info()


# --- 6. API Registration ---
try:
    import server
    import aiohttp
    from aiohttp import web

    from .api_routes import register_api_routes

    register_api_routes({**globals(), "server": server, "aiohttp": aiohttp, "web": web})
except ImportError:
    _startup_print("Server module not found (running in standalone mode?)", "WARNING")
except Exception as e:
    _startup_print(f"Failed to register API: {e}", "WARNING")


# Web directory for frontend assets (required by ComfyUI)
WEB_DIRECTORY = "./web"

def _read_pyproject_value(pattern: str, fallback: str = "") -> str:
    try:
        pyproject_path = Path(__file__).resolve().with_name("pyproject.toml")
        text = pyproject_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(pattern, text)
        if m:
            value = (m.group(1) or "").strip()
            return value or fallback
    except Exception:
        pass
    return fallback


# Metadata for "About" / tooling integrations (best-effort, no hard dependency).
# Many ComfyUI/Manager UIs will display version + repo link when available.
__version__ = _read_pyproject_value(r'(?m)^version\s*=\s*["\\\']([^"\\\']+)["\\\']', fallback="unknown")
__repository__ = _read_pyproject_value(r'(?m)^Repository\s*=\s*["\\\']([^"\\\']+)["\\\']', fallback="https://github.com/rookiestar28/ComfyUI-Doctor")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY", "__version__", "__repository__"]
