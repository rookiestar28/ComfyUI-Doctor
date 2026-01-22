"""
ComfyUI Doctor - Main Entry Point

This module initializes the smart debugging system on ComfyUI startup.
Features:
- Automatic log capture from startup
- System environment snapshot
- Error analysis with suggestions
- API endpoint for frontend integration

═══════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: Relative Import Warning for Test Maintainers
═══════════════════════════════════════════════════════════════════════════
This module uses RELATIVE IMPORTS (from .logger import ...) which is REQUIRED
for ComfyUI custom node extensions.

DO NOT change to absolute imports (from logger import ...) as this will:
  ❌ Break ComfyUI's module loading system
  ❌ Cause "ModuleNotFoundError" when ComfyUI tries to load this extension

IMPORTANT FOR TESTING:
  - pytest CANNOT directly import this file due to relative imports
  - See tests/conftest.py for the workaround (temporary __init__.py renaming)
  - See pytest.ini for import-mode configuration
  - See .planning/260103-ci_pytest_fix.md for detailed explanation

If pytest fails with "attempted relative import with no known parent package":
  1. Check that pytest.ini has "addopts = --import-mode=importlib"
  2. Check that tests/conftest.py has pytest_configure/unconfigure hooks
  3. Do NOT modify these imports - the issue is in test configuration

Last Modified: 2026-01-03 (Added CI testing compatibility notes)
═══════════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ CRITICAL: DO NOT change these to absolute imports
# These MUST be relative imports for ComfyUI compatibility
# ═══════════════════════════════════════════════════════════════════════════
from .logger import SmartLogger, get_last_analysis, get_analysis_history, clear_analysis_history, get_logger_metrics
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .i18n import set_language, get_language, get_ui_text, SUPPORTED_LANGUAGES, UI_TEXT
from .config import CONFIG
from .session_manager import SessionManager
from .system_info import get_system_environment, format_env_for_llm, canonicalize_system_info
from .sanitizer import PIISanitizer, SanitizationLevel
from .security import is_local_llm_url, validate_ssrf_url, parse_base_url, get_ssrf_metrics
from .outbound import get_outbound_sanitizer, sanitize_outbound_payload
from .llm_client import llm_request_with_retry, RetryConfig, RetryResult
from .services.token_budget import TokenBudgetService, BudgetConfig
from .services.prompt_composer import get_prompt_composer, PromptComposerConfig

# Global R12 Service
TOKEN_BUDGET_SERVICE = TokenBudgetService()


# R7: Apply configurable rate/concurrency limits from CONFIG
SessionManager.configure_limits(
    core_rate_limit=getattr(CONFIG, "llm_core_rate_limit", None),
    light_rate_limit=getattr(CONFIG, "llm_light_rate_limit", None),
    max_concurrent=getattr(CONFIG, "llm_max_concurrent", None),
)


def _close_retry_response(result: RetryResult) -> None:
    resp = getattr(result, "response", None)
    if resp is None:
        return
    try:
        resp.close()
    except Exception:
        pass

# --- LLM Environment Variable Fallbacks ---
# These can be set in system environment to provide default values
DOCTOR_LLM_API_KEY = os.getenv("DOCTOR_LLM_API_KEY")
DOCTOR_LLM_BASE_URL = os.getenv("DOCTOR_LLM_BASE_URL", "https://api.openai.com/v1")
DOCTOR_LLM_MODEL = os.getenv("DOCTOR_LLM_MODEL", "gpt-4o")

# --- Local LLM Service URLs (Environment Variable Support) ---
# Allows cross-platform compatibility (Windows vs WSL2, Docker, etc.)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")



def is_anthropic(base_url: str) -> bool:
    """Check if the base URL is for Anthropic API."""
    info = parse_base_url(base_url)
    hostname = (info.get("hostname") if info else "") or ""
    return hostname.lower().endswith("anthropic.com")

# --- 1. Setup Log Directory (Local to Node) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(current_dir, "logs")

if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        print(f"[ComfyUI-Doctor] Warning: Could not create log directory: {e}")


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
    print(f"\n[ComfyUI-Doctor] 🟢 Upgrading from Prestartup Logger...")
    print(f"[ComfyUI-Doctor] 📄 Using existing log: {log_path}")
else:
    # No prestartup logger - generate new log filename
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"comfyui_debug_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)
    print(f"\n[ComfyUI-Doctor] 🟢 Initializing Smart Debugger...")
    print(f"[ComfyUI-Doctor] 📄 Log file: {log_path}")


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
                    logging.info("[Doctor] Prestartup logger handoff complete")
                except Exception as handoff_error:
                    logging.warning(f"[Doctor] Prestartup logger handoff failed: {handoff_error}")
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

    # Formatter with timestamp and level
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    api_logger.addHandler(file_handler)

    # Console handler for terminal output (user requested visibility)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '[Doctor-API] [%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    api_logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate console output)
    api_logger.propagate = False

    return api_logger

# Initialize logger
logger = setup_api_logger()
print(f"[ComfyUI-Doctor] 📋 API logger initialized: {os.path.join(log_dir, 'api_operations.log')}")


# --- 5. Log System Information (Hardware Snapshot) ---
def log_system_info() -> None:
    """Log system and hardware information at startup."""
    # ASCII Art Banner
    print("\n")
    print("   ██████╗ ██████╗ ███╗   ███╗███████╗██╗   ██╗██╗   ██╗██╗      ██████╗  ██████╗  ██████╗████████╗ ██████╗ ██████╗ ")
    print("  ██╔════╝██╔═══██╗████╗ ████║██╔════╝╚██╗ ██╔╝██║   ██║██║      ██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗")
    print("  ██║     ██║   ██║██╔████╔██║█████╗   ╚████╔╝ ██║   ██║██║█████╗██║  ██║██║   ██║██║        ██║   ██║   ██║██████╔╝")
    print("  ██║     ██║   ██║██║╚██╔╝██║██╔══╝    ╚██╔╝  ██║   ██║██║╚════╝██║  ██║██║   ██║██║        ██║   ██║   ██║██╔══██╗")
    print("  ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║        ██║   ╚██████╔╝██║      ██████╔╝╚██████╔╝╚██████╗   ██║   ╚██████╔╝██║  ██║")
    print("   ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝        ╚═╝    ╚═════╝ ╚═╝      ╚═════╝  ╚═════╝  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝")
    print("\n")
    print(f"{'='*20} SYSTEM SNAPSHOT {'='*20}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python: {sys.version.split()[0]}")
    
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA Version: {torch.version.cuda}")
            device_count = torch.cuda.device_count()
            print(f"GPU Count: {device_count}")
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}: {props.name} (VRAM: {props.total_memory / 1024**3:.2f} GB)")
    except ImportError:
        print("PyTorch: Not Installed (or not found in this env)")
    
    # Log ComfyUI Arguments if available
    print(f"Args: {sys.argv}")
    print(f"{'='*57}\n")

log_system_info()


# --- F7: Parameter Fix Helper Functions ---
def validate_fix_schema(fix_json):
    """
    Validate fix JSON structure for F7 parameter injection.

    Args:
        fix_json: Dictionary containing 'fixes' array

    Returns:
        bool: True if schema is valid, False otherwise
    """
    if "fixes" not in fix_json or not isinstance(fix_json["fixes"], list):
        return False

    required_keys = {"node_id", "widget", "from", "to", "reason"}
    for fix in fix_json["fixes"]:
        if not isinstance(fix, dict):
            return False
        if not required_keys.issubset(fix.keys()):
            return False
        # Basic type check: node_id should be convertible to string
        if not isinstance(fix.get("node_id"), (str, int)):
            return False
    return True


# --- Option B Phase 1: Enhanced Error Context & Multi-Language Templates ---

def collect_error_context(error_data, workflow_data):
    """
    Collect comprehensive error context for LLM analysis (Option B Phase 1).

    Returns enriched error data with:
    - Python stack trace (if available)
    - ComfyUI execution logs (last 50 lines)
    - Failed node details (class, inputs, outputs)
    - Workflow structure (upstream dependencies, missing connections)

    Args:
        error_data: Error information dict (exception_message, exception_type, node_id, traceback)
        workflow_data: Full workflow dict mapping node_id -> node_info

    Returns:
        dict: Enriched context with error details, logs, node info, and workflow structure
    """
    context = {
        "error_message": error_data.get("exception_message", "") if error_data else "",
        "error_type": error_data.get("exception_type", "Unknown") if error_data else "Unknown",
        "traceback": None,
        "execution_logs": [],
        "failed_node": None,
        "workflow_structure": {
            "upstream_nodes": [],
            "missing_connections": []
        }
    }

    if not error_data:
        return context

    # 1. Extract Python traceback (if available)
    if "traceback" in error_data:
        context["traceback"] = error_data["traceback"]

    # 2. Get recent execution logs (R14: Prefer ring buffer for reliability)
    # Ring buffer captures ALL stdout/stderr lines, not just ComfyUI logger output
    try:
        from services.log_ring_buffer import get_ring_buffer
        ring_buffer = get_ring_buffer()
        context["execution_logs"] = ring_buffer.get_recent(50)
    except Exception:
        # Fallback: Try ComfyUI's logger buffer (legacy behavior)
        try:
            comfy_logger = logging.getLogger("comfyui")
            if hasattr(comfy_logger, 'handlers'):
                for handler in comfy_logger.handlers:
                    if hasattr(handler, 'buffer'):
                        context["execution_logs"] = handler.buffer[-50:]
                        break
        except Exception:
            pass  # No logs available

    # 3. Get failed node details
    node_id = error_data.get("node_id")
    if node_id and workflow_data:
        node = workflow_data.get(str(node_id))
        if node:
            context["failed_node"] = {
                "id": node_id,
                "class_type": node.get("class_type"),
                "inputs": node.get("inputs", {}),
                "title": node.get("_meta", {}).get("title", "")
            }

            # 4. Analyze workflow structure around failed node
            # Find upstream nodes (nodes that feed into this one)
            upstream = []
            for input_key, input_value in node.get("inputs", {}).items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    # This is a connection: [source_node_id, output_index]
                    source_node_id = str(input_value[0])
                    if source_node_id in workflow_data:
                        upstream.append({
                            "id": source_node_id,
                            "class_type": workflow_data[source_node_id].get("class_type"),
                            "connection": input_key
                        })

            context["workflow_structure"]["upstream_nodes"] = upstream

            # 5. Check for missing required connections
            # This requires ComfyUI's node definition API
            try:
                from nodes import NODE_CLASS_MAPPINGS
                node_class = NODE_CLASS_MAPPINGS.get(node.get("class_type"))
                if node_class and hasattr(node_class, "INPUT_TYPES"):
                    required_inputs = node_class.INPUT_TYPES().get("required", {})
                    for req_input in required_inputs.keys():
                        if req_input not in node.get("inputs", {}):
                            context["workflow_structure"]["missing_connections"].append({
                                "input": req_input,
                                "type": str(required_inputs[req_input])
                            })
            except Exception:
                pass

    return context


# Multi-language error analysis prompt templates (Option B Phase 1)
# System prompts are written in English with explicit language directives
ERROR_ANALYSIS_TEMPLATES = {
    "en": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: English

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "zh_TW": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: 繁體中文

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "zh_CN": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: 简体中文

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "ja": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: 日本語

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "de": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: Deutsch

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "fr": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: Français

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "it": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: Italiano

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "es": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: Español

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    },

    "ko": {
        "system_instruction": """You are analyzing a ComfyUI workflow execution error.

**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.

**Response Language**: 한국어

**Error Categories**:
1. **Connection Errors**: Missing required inputs, disconnected nodes
2. **Model Missing**: .safetensors, .ckpt files not found in local directories
3. **Validation Errors**: Parameter value not in allowed list
4. **Type Errors**: Wrong data type passed to node (e.g., tensor vs image)
5. **Execution Errors**: Python exceptions during generation

**Analysis Steps**:
1. Categorize the error (which category above?)
2. Identify the root cause (why did it happen?)
3. Suggest ONE-CLICK fixes (node_id, widget, value changes)
4. Provide reasoning (why will this fix work?)

**Fix Format** (if applicable):
```json
{
  "fixes": [
    {
      "node_id": "42",
      "widget": "scheduler",
      "from": "Normal",
      "to": "normal",
      "reason": "Scheduler parameter is case-sensitive. 'Normal' → 'normal'"
    }
  ]
}
```

**Remember**: Focus on CRASH PREVENTION, not quality improvement."""
    }
}


def get_error_analysis_prompt(user_language: str) -> str:
    """
    Get error analysis system prompt in English with language directive.

    This follows the Option B design principle:
    - System prompts written in English (for LLM consistency)
    - Explicit language directive for responses
    - Maintains prompt quality across all languages

    Args:
        user_language: User's preferred language (en/zh_TW/zh_CN/ja/de/fr/it/es/ko)

    Returns:
        System prompt in English with explicit language directive
    """
    template = ERROR_ANALYSIS_TEMPLATES.get(user_language, ERROR_ANALYSIS_TEMPLATES["en"])
    return template["system_instruction"]


def parse_language_code(accept_language: str) -> str:
    """
    Parse Accept-Language header to extract primary language code.

    Examples:
        "zh-TW,zh;q=0.9,en;q=0.8" → "zh_TW"
        "en-US,en;q=0.9" → "en"
        "ja" → "ja"

    Args:
        accept_language: HTTP Accept-Language header value

    Returns:
        Normalized language code (e.g., "zh_TW", "en", "ja")
    """
    if not accept_language:
        return "en"

    # Extract first language code (before comma)
    primary_lang = accept_language.split(',')[0].strip()

    # Normalize separators: "zh-TW" → "zh_TW"
    normalized = primary_lang.replace('-', '_')

    # Map to supported languages
    supported_map = {
        "zh_TW": "zh_TW",
        "zh_CN": "zh_CN",
        "zh_HK": "zh_TW",  # Fallback: Hong Kong → Traditional Chinese
        "zh": "zh_CN",      # Fallback: Generic Chinese → Simplified
        "ja": "ja",
        "de": "de",
        "fr": "fr",
        "it": "it",
        "es": "es",
        "ko": "ko",
        "en": "en"
    }

    # Try exact match first
    if normalized in supported_map:
        return supported_map[normalized]

    # Try base language (e.g., "en_US" → "en")
    base_lang = normalized.split('_')[0]
    if base_lang in supported_map:
        return supported_map[base_lang]

    # Default to English
    return "en"


# --- Option B Phase 2: Error Categorization ---

def categorize_error(error_data):
    """
    Classify error type using keyword matching (Option B Phase 2).

    This helps the LLM focus on the right fix strategy by pre-categorizing
    errors into one of 5 common types.

    Args:
        error_data: Error information (can be dict, string, or any object with str() representation)

    Returns:
        dict: {
            "category": str (connection_error|model_missing|validation_error|type_error|execution_error),
            "confidence": float (0.0-1.0),
            "keywords_matched": list[str],
            "suggested_approach": str
        }
    """
    # Convert error_data to searchable string
    if isinstance(error_data, dict):
        error_text = json.dumps(error_data).lower()
    else:
        error_text = str(error_data).lower()

    # Define keyword patterns for each error category
    # Inspired by ComfyUI-Copilot's debug_agent.py pattern matching
    patterns = {
        "connection_error": {
            "keywords": [
                "missing input", "required input", "not connected",
                "connection", "disconnected", "input is required",
                "missing required", "no input provided"
            ],
            "weight": 1.0,
            "approach": "Check node connections. Ensure all required inputs are connected to upstream nodes."
        },
        "model_missing": {
            "keywords": [
                ".safetensors", ".ckpt", ".pth", ".pt", ".bin",
                "model not found", "file not found", "no such file",
                "checkpoint", "filenotfounderror", "path does not exist"
            ],
            "weight": 1.0,
            "approach": "Check model files in your models directory. Verify the model name matches an existing file."
        },
        "validation_error": {
            "keywords": [
                "value not in list", "invalid value", "not found in list",
                "invalid parameter", "value error", "not a valid",
                "must be one of", "not in allowed values", "invalid choice"
            ],
            "weight": 0.9,
            "approach": "Use fuzzy matching to find the correct parameter value from available options."
        },
        "type_error": {
            "keywords": [
                "type mismatch", "expected", "but received",
                "cannot convert", "dtype", "typeerror",
                "incompatible type", "wrong type", "type error"
            ],
            "weight": 0.8,
            "approach": "Check data type conversions. May need a conversion node (e.g., ImageToTensor)."
        }
    }

    # Count keyword matches for each category
    matches = {}
    for category, config in patterns.items():
        matched_keywords = [kw for kw in config["keywords"] if kw in error_text]
        count = len(matched_keywords)

        if count > 0:
            # Calculate confidence: (matches / total_keywords) * weight
            # Cap at 1.0 to prevent over-confidence
            confidence = min(count / len(config["keywords"]) * config["weight"], 1.0)

            matches[category] = {
                "count": count,
                "confidence": confidence,
                "matched_keywords": matched_keywords,
                "approach": config["approach"]
            }

    # Return category with highest confidence
    if matches:
        best_category, best_match = max(matches.items(), key=lambda x: x[1]["confidence"])
        return {
            "category": best_category,
            "confidence": best_match["confidence"],
            "keywords_matched": best_match["matched_keywords"],
            "suggested_approach": best_match["approach"]
        }
    else:
        # Default: Generic execution error
        return {
            "category": "execution_error",
            "confidence": 0.5,
            "keywords_matched": [],
            "suggested_approach": "General error analysis needed. Check Python stack trace for details."
        }


# --- 6. API Registration ---
try:
    import server
    import aiohttp
    from aiohttp import web

    @server.PromptServer.instance.routes.get("/debugger/last_analysis")
    async def api_get_last_analysis(request):
        """
        API endpoint to get the last error analysis.
        
        Returns:
            JSON with status, log_path, last error details, and suggestion.
        """
        analysis = get_last_analysis()
        return web.json_response({
            "status": "running",
            "log_path": log_path,
            "language": get_language(),
            "supported_languages": SUPPORTED_LANGUAGES,
            "last_error": analysis.get("error"),
            "suggestion": analysis.get("suggestion"),
            "timestamp": analysis.get("timestamp"),
            "node_context": analysis.get("node_context"),
            "analysis_metadata": analysis.get("analysis_metadata"),
            "matched_pattern_id": analysis.get("matched_pattern_id"),
            "pattern_category": analysis.get("pattern_category"),
            "pattern_priority": analysis.get("pattern_priority"),
            "resolution_status": analysis.get("resolution_status"),
        })
    
    @server.PromptServer.instance.routes.post("/debugger/set_language")
    async def api_set_language(request):
        """
        API endpoint to change the suggestion language.

        Body: {"language": "zh_TW"}
        """
        try:
            data = await request.json()
            if "language" in data:
                set_language(data["language"])
                return web.json_response({"success": True, "language": data["language"]})
            return web.json_response({"success": False, "message": "Missing language parameter"}, status=400)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/ui_text")
    async def api_get_ui_text(request):
        """
        API endpoint to get all UI text translations for current language.

        Query params (optional): ?lang=zh_TW
        """
        try:
            lang = request.query.get("lang", get_language())
            ui_text = UI_TEXT.get(lang, UI_TEXT["en"])

            def _get_doctor_meta() -> dict:
                # Best-effort metadata for UI display (no extra deps).
                meta = {
                    "name": "ComfyUI-Doctor",
                    "version": "unknown",
                    "repository": "https://github.com/rookiestar28/ComfyUI-Doctor",
                }
                try:
                    import importlib.metadata as _metadata  # py3.8+

                    # Distribution name may differ depending on install method.
                    for dist_name in ("ComfyUI-Doctor", "comfyui-doctor"):
                        try:
                            meta["version"] = _metadata.version(dist_name)
                            break
                        except Exception:
                            pass
                except Exception:
                    pass

                # Fallback: parse local pyproject.toml (repo install via ComfyUI-Manager).
                if meta["version"] in ("unknown", "", None):
                    try:
                        from pathlib import Path
                        import re

                        pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"
                        if pyproject_path.exists():
                            content = pyproject_path.read_text(encoding="utf-8", errors="ignore")
                            m = re.search(r'(?m)^version\\s*=\\s*"([^"]+)"\\s*$', content)
                            if m:
                                meta["version"] = m.group(1).strip()
                            m_repo = re.search(
                                r'(?ms)^\\[project\\.urls\\].*?^Repository\\s*=\\s*"([^"]+)"\\s*$',
                                content,
                            )
                            if m_repo:
                                meta["repository"] = m_repo.group(1).strip()
                    except Exception:
                        pass
                return meta

            return web.json_response({
                "language": lang,
                "text": ui_text,
                "meta": _get_doctor_meta(),
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/analyze")
    async def api_analyze_error(request):
        """
        API endpoint to analyze error with LLM.
        Payload: { "error": str, "node_context": dict, "api_key": str, "base_url": str, "model": str, "language": str }
        
        Security: API key is transmitted but never logged or persisted.
        """
        try:
            data = await request.json()
            error_text = data.get("error")
            node_context = data.get("node_context", {})
            workflow = data.get("workflow")  # F3: Workflow context from frontend
            api_key = data.get("api_key")
            base_url = data.get("base_url", "https://api.openai.com/v1")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")
            privacy_mode = data.get("privacy_mode", "basic")  # S6: PII sanitization level

            logger.info(f"Analyze API called - error_length={len(error_text) if error_text else 0}, has_workflow={bool(workflow)}, model={model}, privacy={privacy_mode}")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return web.json_response({"error": f"Invalid Base URL: {ssrf_error}"}, status=400)

            # Validate required parameters
            # Check if this is a local LLM (doesn't require API key)
            is_local = is_local_llm_url(base_url)
            
            # Only require API key for non-local LLMs
            if not api_key and not is_local:
                return web.json_response({"error": "Missing API Key"}, status=401)

            if not error_text:
                return web.json_response({"error": "No error text provided"}, status=400)

            # S6: PII Sanitization - Remove sensitive info before sending to LLM
            sanitizer, downgraded = get_outbound_sanitizer(base_url, privacy_mode)
            if downgraded:
                logger.warning("privacy_mode=none is only allowed for verified local providers; using basic")

            # Sanitize error text
            sanitization_result = sanitizer.sanitize(error_text)
            error_text = sanitization_result.sanitized_text

            # Log sanitization metadata (for audit)
            if sanitization_result.pii_found:
                logger.info(f"PII sanitized: {sanitization_result.replacements}")

            # Sanitize node context (paths, custom_node_path)
            if node_context:
                node_context = sanitizer.sanitize_dict(node_context, keys_to_sanitize=[])

            # Truncate error text to prevent token overflow (roughly 8000 chars ≈ 2000 tokens)
            MAX_ERROR_LENGTH = 8000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n\n[... truncated ...]"

            # R8: Smart workflow truncation (preserves error-related nodes)
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                error_node_id = node_context.get("id") if node_context else None
                workflow, truncation_meta = truncate_workflow_smart(workflow, error_node_id, max_chars=4000)
                if truncation_meta.get("truncation_method") != "none":
                    logger.info(f"Workflow truncated: {truncation_meta}")

            # Construct Prompt - Enhanced for ComfyUI debugging
            system_prompt = (
                "You are an expert ComfyUI debugger and Python specialist. "
                "ComfyUI is a node-based Stable Diffusion workflow editor where users connect nodes "
                "(e.g., 'KSampler', 'VAEDecode', 'CheckpointLoaderSimple', 'CLIPTextEncode') to build image generation pipelines.\n\n"
                "Common ComfyUI error categories:\n"
                "- **OOM (Out of Memory)**: Reduce batch_size, lower resolution, use --lowvram or --cpu flags\n"
                "- **Missing Models**: Check if model file exists in ComfyUI/models/ folder, verify filename spelling\n"
                "- **Type Mismatch**: Ensure connected nodes have compatible data types (MODEL, CLIP, VAE, LATENT, IMAGE)\n"
                "- **CUDA/cuDNN Errors**: Often driver version issues, try updating GPU drivers or PyTorch\n"
                "- **Shape Mismatch**: Usually caused by incompatible image sizes or LoRA/model combinations\n"
                "- **Module Not Found**: Missing Python dependencies, run 'pip install <module>' in ComfyUI environment\n\n"
                "Analyze the error and provide:\n"
                "1. **Root Cause** (1-2 sentences, be specific)\n"
                "2. **Solution Steps** (numbered list, actionable commands if applicable)\n"
                "3. **Prevention Tips** (optional, if the error is common)\n\n"
                f"Respond in {language}. Be concise but thorough."
            )
            
            # R14: Use PromptComposer for unified context formatting
            if CONFIG.r14_use_prompt_composer:
                try:
                    from services.context_extractor import extract_error_summary
                    
                    # Extract error summary for summary-first ordering
                    error_summary_obj = extract_error_summary(error_text)
                    error_summary_str = error_summary_obj.to_string() if error_summary_obj else error_text[:200]
                    
                    # Build llm_context compatible with PromptComposer
                    llm_context = {
                        "error_summary": error_summary_str,
                        "node_info": node_context if node_context else {},
                        "traceback": error_text,
                        "execution_logs": [],  # Not available in analyze endpoint
                        "workflow_subset": workflow,
                        "system_info": {}  # Will be added below
                    }
                    
                    # R15: Add canonicalized system environment
                    try:
                        env_info = get_system_environment()
                        llm_context["system_info"] = canonicalize_system_info(
                            env_info, 
                            error_text=error_text,
                            privacy_mode=privacy_mode
                        )
                    except Exception:
                        pass
                    
                    composer_config = PromptComposerConfig(use_legacy_format=CONFIG.r14_use_legacy_format)
                    prompt_composer = get_prompt_composer()
                    user_prompt = prompt_composer.compose(llm_context, composer_config)
                    
                    logger.info("[R14] PromptComposer used for /doctor/analyze")
                except Exception as r14_err:
                    logger.warning(f"[R14] PromptComposer failed in /doctor/analyze, falling back to legacy: {r14_err}")
                    # Fall through to legacy format
                    user_prompt = None
            else:
                user_prompt = None
            
            # Legacy format (fallback or when R14 disabled)
            if user_prompt is None:
                user_prompt = f"Error:\n{error_text}\n\n"
                if node_context:
                    user_prompt += f"Node Context: {json.dumps(node_context, indent=2)}\n\n"

                # F3: Include workflow context if available
                if workflow:
                    user_prompt += f"Workflow Structure (simplified):\n{workflow}\n\n"

                # F10: Include system environment context for better debugging
                try:
                    env_info = get_system_environment()
                    env_text = format_env_for_llm(env_info, max_packages=30)
                    user_prompt += f"{env_text}\n\n"
                except Exception as env_err:
                    # Don't fail the entire analysis if env collection fails
                    logger.warning(f"Failed to collect environment info: {env_err}")
                    user_prompt += "[System environment info unavailable]\n\n"
            
            # Normalize Base URL
            base_url = base_url.rstrip("/")

            base_info = parse_base_url(base_url)
            hostname = (base_info.get("hostname") if base_info else "") or ""
            is_local = is_local_llm_url(base_url)

            # Determine API type
            is_ollama = is_local and base_info and base_info.get("port") == 11434
            is_anthropic_api = is_anthropic(base_url)

            # Prepare headers and payload based on API type
            if is_anthropic_api:
                # Anthropic API uses different format
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                url = f"{base_url}/v1/messages"
                # Anthropic doesn't support system message in messages array
                payload = {
                    "model": model,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 4096
                }
            elif is_ollama:
                # Ollama uses /api/chat endpoint (remove /v1 if present)
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/chat"
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
            else:
                # OpenAI-compatible APIs
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                # Auto-append /v1 if missing and looks like a standard provider
                if not base_url.endswith("/v1") and hostname.lower().endswith(("openai.com", "deepseek.com")):
                    base_url += "/v1"
                url = f"{base_url}/chat/completions"
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.5
                }

            # R7: Rate limit check (core limiter for heavy endpoint)
            if not SessionManager.get_core_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/analyze")
                return web.json_response(
                    {"error": "Rate limit exceeded. Please wait before retrying."},
                    status=429
                )
            
            # R7: Concurrency limit (prevent connection pool exhaustion)
            async with SessionManager.get_concurrency_limiter():
                session = await SessionManager.get_session()
                payload = sanitize_outbound_payload(payload, sanitizer)
                
                # R6: Request with retry logic
                retry_config = RetryConfig(
                    max_retries=CONFIG.llm_max_retries,
                    request_timeout_seconds=CONFIG.llm_request_timeout,
                    total_timeout_seconds=CONFIG.llm_total_timeout,
                    retry_on_5xx=False,  # Conservative for non-streaming
                )
                result = await llm_request_with_retry(
                    session, "POST", url,
                    json=payload, headers=headers,
                    config=retry_config,
                )
                
                if not result.success:
                    _close_retry_response(result)
                    error_msg = result.error or "Unknown error"
                    logger.error(f"LLM request failed after {result.attempts} attempts: {error_msg}")
                    return web.json_response(
                        {"error": f"LLM Error: {error_msg}"},
                        status=503
                    )
                
                async with result.response as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        # Truncate error message for readability
                        if len(error_msg) > 500:
                            error_msg = error_msg[:500] + "..."
                        return web.json_response(
                            {"error": f"LLM Provider Error ({response.status}): {error_msg}"},
                            status=response.status
                        )

                    # Safely parse JSON response
                    try:
                        resp_data = await response.json()
                        # Handle Anthropic, Ollama, and OpenAI response formats
                        if is_anthropic_api:
                            # Anthropic format: {"content": [{"text": "..."}]}
                            content = resp_data.get('content', [{}])[0].get('text', '')
                        elif is_ollama:
                            content = resp_data.get('message', {}).get('content', '')
                        else:
                            content = resp_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        if not content:
                            return web.json_response({"error": "Empty response from LLM"}, status=502)
                        logger.info(f"Analysis successful, response length={len(content)}, attempts={result.attempts}")
                        return web.json_response({"analysis": content})
                    except (json.JSONDecodeError, KeyError, IndexError) as parse_err:
                        return web.json_response(
                            {"error": f"Failed to parse LLM response: {str(parse_err)}"}, 
                            status=502
                        )

        except aiohttp.ClientError as e:
            # Network-level errors (timeout, connection refused, etc.)
            logger.error(f"LLM Network Error: {str(e)}")
            return web.json_response({"error": f"Network Error: {str(e)}"}, status=503)
        except Exception as e:
            logger.error(f"LLM Analysis Failed: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/chat")
    async def api_chat(request):
        """
        API endpoint for multi-turn chat with LLM (SSE streaming).
        
        Payload: {
            "messages": [{"role": "user|assistant", "content": "..."}],
            "error_context": {"error": "...", "node_context": {...}, "workflow": "..."},
            "api_key": str,
            "base_url": str,
            "model": str,
            "language": str,
            "stream": bool (default: true)
        }
        
        Response (SSE):
            data: {"delta": "token", "done": false}
            data: {"delta": "", "done": true}
        """
        try:
            data = await request.json()
            messages = data.get("messages", [])
            error_context = data.get("error_context", {})
            api_key = data.get("api_key", "")
            base_url = data.get("base_url", "https://api.openai.com/v1")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")
            stream = data.get("stream", True)
            intent = data.get("intent", "chat")  # New: intent parameter
            selected_nodes = data.get("selected_nodes", [])  # New: node selection context
            privacy_mode = data.get("privacy_mode", "basic")  # S6: PII sanitization level

            logger.info(f"Chat API called - model={model}, intent={intent}, messages={len(messages)}, stream={stream}, privacy={privacy_mode}")
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return web.json_response({"error": f"Invalid Base URL: {ssrf_error}"}, status=400)

            # Validate
            is_local = is_local_llm_url(base_url)
            if not api_key and not is_local:
                return web.json_response({"error": "Missing API Key"}, status=401)
            
            if not messages:
                return web.json_response({"error": "No messages provided"}, status=400)

            # R12: Smart Token Budget
            # Apply budget metrics and trimming BEFORE sanitization and prompt construction
            # This ensures we operate on the raw context keys
            # Supports both remote (strict) and local (opt-in soft) modes
            r12_meta = {}
            r12_should_apply = (CONFIG.r12_enabled_remote and not is_local) or (CONFIG.r12_enabled_local and is_local)
            
            if r12_should_apply:
                try:
                    from .services.token_estimator import EstimatorConfig
                    
                    # Select appropriate limits and policy based on provider type
                    if is_local:
                        # Local mode: use local limits with local_soft policy
                        soft_max = CONFIG.r12_soft_max_tokens_local
                        hard_max = CONFIG.r12_hard_max_tokens_local
                        policy = "local_soft"
                    else:
                        # Remote mode: use remote limits with configured policy
                        soft_max = CONFIG.r12_soft_max_tokens_remote
                        hard_max = CONFIG.r12_hard_max_tokens_remote
                        policy = CONFIG.r12_policy_profile
                    
                    budget_config = BudgetConfig(
                        enabled_remote=CONFIG.r12_enabled_remote,
                        enabled_local=CONFIG.r12_enabled_local,
                        soft_max_tokens=soft_max,
                        hard_max_tokens=hard_max,
                        trimming_policy=policy,
                        estimator_config=EstimatorConfig(
                            chars_per_token=CONFIG.r12_estimator_fallback_cpt,
                            safety_multiplier=CONFIG.r12_estimator_safety_mult
                        ),
                        prune_default_depth=CONFIG.r12_prune_default_depth,
                        prune_default_nodes=CONFIG.r12_prune_default_nodes,
                        overhead_fixed=CONFIG.r12_overhead_fixed
                    )
                    
                    # Create context wrapper
                    budget_context = {
                        "messages": messages,
                        "error_context": error_context
                    }
                    
                    # Apply
                    budgeted_context, r12_meta = TOKEN_BUDGET_SERVICE.apply_token_budget(
                        budget_context,
                        is_remote_provider=not is_local,
                        config=budget_config
                    )
                    
                    # Update local refs with trimmed versions
                    if "messages" in budgeted_context:
                        messages = budgeted_context["messages"]
                    if "error_context" in budgeted_context:
                        error_context = budgeted_context["error_context"]
                except Exception as r12_err:
                    logger.warning(f"R12 Budget application failed, proceeding with original payload: {r12_err}")

            # S6: PII Sanitization - Remove sensitive info before sending to LLM
            sanitizer, downgraded = get_outbound_sanitizer(base_url, privacy_mode)
            if downgraded:
                logger.warning("privacy_mode=none is only allowed for verified local providers; using basic")

            # Build system prompt with error context
            # R14: Support both "error" and "last_error" keys for compatibility
            error_text = error_context.get("error") or error_context.get("last_error", "")
            node_context = error_context.get("node_context", {})
            workflow = error_context.get("workflow", "")

            # Sanitize error context
            if error_text:
                error_text = sanitizer.sanitize(error_text).sanitized_text
            if node_context:
                node_context = sanitizer.sanitize_dict(node_context, keys_to_sanitize=[])

            # Sanitize user messages (only user role, not assistant responses)
            for msg in messages:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    msg["content"] = sanitizer.sanitize(msg["content"]).sanitized_text

            # Truncate to prevent token overflow
            MAX_ERROR_LENGTH = 4000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n[... truncated ...]"
            
            # R8: Smart workflow truncation
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                workflow, _ = truncate_workflow_smart(workflow, max_chars=2000)
            
            # Option B Phase 1: Parse workflow data for enhanced error context
            workflow_data = None
            if workflow:
                try:
                    # If workflow is a JSON string, parse it
                    if isinstance(workflow, str):
                        workflow_data = json.loads(workflow)
                    elif isinstance(workflow, dict):
                        workflow_data = workflow
                except json.JSONDecodeError:
                    logger.warning("Failed to parse workflow JSON for enhanced context")

            # Option B Phase 1: Collect enhanced error context
            # R14: Support both "error" and "last_error" keys
            enriched_context = None
            canonical_error = error_context.get("error") or error_context.get("last_error")
            if error_context and canonical_error:
                # Build error_data dict from error_context
                error_data = {
                    "exception_message": canonical_error,
                    "exception_type": error_context.get("error_type", "Unknown"),
                    "node_id": node_context.get("node_id") if node_context else None,
                    "traceback": error_context.get("traceback")
                }
                enriched_context = collect_error_context(error_data, workflow_data)

            error_category = None
            if error_context and canonical_error:
                # Categorize using the full error_context dict for better keyword matching
                error_category = categorize_error(error_context)
                logger.info(f"Error categorized as: {error_category['category']} (confidence: {error_category['confidence']:.0%})")

            # Option B Phase 1: Detect user's preferred language from request headers or data
            user_lang_code = language  # Default to language parameter
            if not user_lang_code or user_lang_code not in ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"]:
                # Try to parse from Accept-Language header if available
                accept_lang = request.headers.get("Accept-Language", "en")
                user_lang_code = parse_language_code(accept_lang)

            # Intent-aware system prompt
            if intent == "explain_node":
                # Node explanation mode - use simple prompt
                system_prompt = (
                    "You are an expert ComfyUI node documentation assistant. ComfyUI is a node-based Stable Diffusion workflow editor.\n\n"
                    "Your task is to explain how specific nodes work, their inputs/outputs, and best practices for using them.\n"
                    "Be concise, clear, and provide practical examples when relevant.\n"
                    f"Respond in {language}.\n\n"
                )
                if selected_nodes:
                    system_prompt += f"**Selected Node(s):** {json.dumps(selected_nodes)}\n\n"
            else:
                # Option B Phase 1: Error analysis mode - use enhanced multi-language template
                if enriched_context and enriched_context.get("error_message"):
                    # Use enhanced error analysis template with language directive
                    system_prompt = get_error_analysis_prompt(user_lang_code)

                    # R14: Use PromptComposer for unified context formatting
                    r14_composer_succeeded = False  # Track success for fallback logic
                    if CONFIG.r14_use_prompt_composer:
                        try:
                            r14_composer_succeeded = True  # Assume success until exception
                            # Build llm_context compatible with PromptComposer
                            from services.context_extractor import extract_error_summary
                            
                            # Extract error summary for summary-first ordering
                            traceback_text = str(enriched_context.get('traceback', ''))
                            error_summary_obj = extract_error_summary(traceback_text)
                            error_summary_str = error_summary_obj.to_string() if error_summary_obj else enriched_context['error_message']
                            
                            llm_context = {
                                "error_summary": error_summary_str,
                                "node_info": {
                                    "node_id": enriched_context.get('failed_node', {}).get('id'),
                                    "node_name": enriched_context.get('failed_node', {}).get('title'),
                                    "node_class": enriched_context.get('failed_node', {}).get('class_type'),
                                },
                                "traceback": traceback_text,
                                "execution_logs": enriched_context.get('execution_logs', []),
                                "workflow_subset": enriched_context.get('workflow_structure'),
                                "system_info": {}  # R15: Added below
                            }
                            
                            # R15: Add canonicalized system environment to llm_context
                            try:
                                _env_info = get_system_environment()
                                llm_context["system_info"] = canonicalize_system_info(
                                    _env_info, 
                                    error_text=traceback_text,
                                    privacy_mode=privacy_mode
                                )
                            except Exception:
                                pass
                            
                            composer_config = PromptComposerConfig(use_legacy_format=CONFIG.r14_use_legacy_format)
                            prompt_composer = get_prompt_composer()
                            context_block = prompt_composer.compose(llm_context, composer_config)
                            
                            system_prompt += f"\n\n{context_block}"
                            
                            # Add error category if available
                            if error_category:
                                system_prompt += f"\n\n**ERROR CATEGORY** (auto-detected):\n"
                                system_prompt += f"Category: {error_category['category']}\n"
                                system_prompt += f"Confidence: {error_category['confidence']:.0%}\n"
                                system_prompt += f"Suggested Approach: {error_category['suggested_approach']}\n"
                            
                            logger.info("[R14/R15] PromptComposer used for context formatting with canonical system_info")
                        except Exception as r14_err:
                            logger.warning(f"[R14] PromptComposer failed, falling back to legacy: {r14_err}")
                            # R14: Use local flag, NOT global CONFIG mutation
                            r14_composer_succeeded = False
                    else:
                        r14_composer_succeeded = False
                    
                    # Legacy format (fallback or when R14 disabled)
                    if not r14_composer_succeeded:
                        # Add enriched error context (legacy format)
                        system_prompt += f"\n\n**ERROR CONTEXT**:\n"
                        system_prompt += f"Error Type: {enriched_context['error_type']}\n"
                        system_prompt += f"Error Message: {enriched_context['error_message']}\n"

                        # Option B Phase 2: Add error category with suggested approach
                        if error_category:
                            system_prompt += f"\n**ERROR CATEGORY** (auto-detected):\n"
                            system_prompt += f"Category: {error_category['category']}\n"
                            system_prompt += f"Confidence: {error_category['confidence']:.0%}\n"
                            system_prompt += f"Suggested Approach: {error_category['suggested_approach']}\n"
                            if error_category['keywords_matched']:
                                matched_kw_str = ', '.join(error_category['keywords_matched'][:5])  # Limit to 5
                                system_prompt += f"Matched Keywords: {matched_kw_str}\n"

                        if enriched_context.get('traceback'):
                            # Truncate traceback to prevent token overflow
                            traceback_text = str(enriched_context['traceback'])
                            if len(traceback_text) > 2000:
                                traceback_text = traceback_text[:2000] + "\n[... truncated ...]"
                            system_prompt += f"\nPython Stack Trace:\n```\n{traceback_text}\n```\n"

                        if enriched_context.get('failed_node'):
                            node = enriched_context['failed_node']
                            system_prompt += f"\nFailed Node: {node['class_type']} (ID: {node['id']})\n"
                            if node.get('title'):
                                system_prompt += f"Node Title: {node['title']}\n"
                            system_prompt += f"Node Inputs: {json.dumps(node['inputs'], indent=2)}\n"

                        if enriched_context['workflow_structure'].get('upstream_nodes'):
                            upstream_nodes = enriched_context['workflow_structure']['upstream_nodes']
                            system_prompt += f"\nUpstream Nodes: {len(upstream_nodes)} connected\n"
                            for up in upstream_nodes[:5]:  # Limit to 5 to prevent token overflow
                                system_prompt += f"  - {up['class_type']} → {up['connection']}\n"

                        if enriched_context['workflow_structure'].get('missing_connections'):
                            system_prompt += f"\n⚠️ Missing Required Connections:\n"
                            for missing in enriched_context['workflow_structure']['missing_connections']:
                                system_prompt += f"  - {missing['input']} (type: {missing['type']})\n"
                else:
                    # Fallback to simple chat/debug prompt
                    system_prompt = (
                        "You are an expert ComfyUI debugger. ComfyUI is a node-based Stable Diffusion workflow editor.\n\n"
                        "You are helping the user debug an error. Be concise, helpful, and provide actionable solutions.\n"
                        f"Respond in {language}.\n\n"
                    )

                    if error_text:
                        system_prompt += f"**Current Error:**\n```\n{error_text}\n```\n\n"

                    if node_context:
                        system_prompt += f"**Node Context:** {json.dumps(node_context)}\n\n"

                    if workflow:
                        system_prompt += f"**Workflow (simplified):** {workflow}\n\n"

            # F10/R15: Include system environment context
            # R15: Only append legacy format if PromptComposer was NOT used (avoid duplicate env)
            if not r14_composer_succeeded:
                try:
                    env_info = get_system_environment()
                    env_text = format_env_for_llm(env_info, max_packages=20)
                    system_prompt += f"\n{env_text}\n\n"
                except Exception as env_err:
                    logger.warning(f"Failed to collect environment info for chat: {env_err}")

            # Prepare request
            base_url = base_url.rstrip("/")

            base_info = parse_base_url(base_url)
            hostname = (base_info.get("hostname") if base_info else "") or ""
            is_local = is_local_llm_url(base_url)

            # Determine API type
            is_ollama = is_local and base_info and base_info.get("port") == 11434
            is_anthropic_api = is_anthropic(base_url)

            # Limit conversation history to prevent token overflow
            MAX_HISTORY = 10
            recent_messages = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages

            if is_anthropic_api:
                # Anthropic uses different format
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                url = f"{base_url}/v1/messages"
                payload = {
                    "model": model,
                    "system": system_prompt,
                    "messages": recent_messages,
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "stream": stream
                }
            elif is_ollama:
                # Ollama uses /api/chat endpoint (remove /v1 if present)
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/chat"
                headers = {
                    "Content-Type": "application/json"
                }
                api_messages = [{"role": "system", "content": system_prompt}]
                api_messages.extend(recent_messages)
                payload = {
                    "model": model,
                    "messages": api_messages,
                    "temperature": 0.7,
                    "stream": stream
                }
            else:
                # OpenAI-compatible: auto-append /v1 if needed
                if not base_url.endswith("/v1") and hostname.lower().endswith(("openai.com", "deepseek.com")):
                    base_url += "/v1"
                url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                api_messages = [{"role": "system", "content": system_prompt}]
                api_messages.extend(recent_messages)
                payload = {
                    "model": model,
                    "messages": api_messages,
                    "temperature": 0.7,
                    "stream": stream
                }

            logger.info(f"Connecting to LLM: {url}")
            
            # R7: Rate limit check (core limiter for heavy endpoint)
            if not SessionManager.get_core_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/chat")
                return web.json_response(
                    {"error": "Rate limit exceeded. Please wait before retrying."},
                    status=429
                )
            
            # R7: Concurrency limit (prevent connection pool exhaustion)
            async with SessionManager.get_concurrency_limiter():
                if not stream:
                    # Non-streaming fallback with retry
                    session = await SessionManager.get_session()
                    payload = sanitize_outbound_payload(payload, sanitizer)
                    
                    # R6: Request with retry logic
                    retry_config = RetryConfig(
                        max_retries=CONFIG.llm_max_retries,
                        request_timeout_seconds=CONFIG.llm_request_timeout,
                        total_timeout_seconds=CONFIG.llm_total_timeout,
                        retry_on_5xx=False,
                    )
                    result = await llm_request_with_retry(
                        session, "POST", url,
                        json=payload, headers=headers,
                        config=retry_config,
                    )
                    
                    if not result.success:
                        _close_retry_response(result)
                        error_msg = result.error or "Unknown error"
                        logger.error(f"LLM non-stream failed after {result.attempts} attempts: {error_msg}")
                        return web.json_response({"error": f"LLM Error: {error_msg}"}, status=503)
                    
                    async with result.response as response:
                        if response.status != 200:
                            error_msg = await response.text()
                            logger.error(f"LLM non-stream error: {error_msg[:200]}")
                            return web.json_response({"error": f"LLM Error: {error_msg[:500]}"}, status=response.status)
                        
                        resp_data = await response.json()
                        # Handle Anthropic, Ollama, and OpenAI response formats
                        if is_anthropic_api:
                            content = resp_data.get('content', [{}])[0].get('text', '')
                        elif is_ollama:
                            content = resp_data.get('message', {}).get('content', '')
                        else:
                            content = resp_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.info(f"LLM response received (non-stream), length={len(content)}, attempts={result.attempts}")
                        return web.json_response({"content": content, "done": True, "metadata": r12_meta})

                # SSE Streaming response
                logger.info("Starting SSE stream...")
                response = web.StreamResponse(
                    status=200,
                    reason='OK',
                    headers={
                        'Content-Type': 'text/event-stream',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'X-Accel-Buffering': 'no',
                    }
                )
                await response.prepare(request)
                
                # Send R12 metadata as early SSE event if available
                if r12_meta:
                    meta_event = json.dumps({"type": "usage_metadata", "data": r12_meta})
                    await response.write(f"data: {meta_event}\n\n".encode('utf-8'))
                
                try:
                    session = await SessionManager.get_session()
                    payload = sanitize_outbound_payload(payload, sanitizer)
                    
                    # R6: Pre-stream retry (only retry before streaming starts)
                    # Once streaming begins, we cannot retry
                    retry_config = RetryConfig(
                        max_retries=CONFIG.llm_max_retries,
                        request_timeout_seconds=CONFIG.llm_request_timeout,
                        total_timeout_seconds=CONFIG.llm_total_timeout,
                        retry_on_5xx=False,
                    )
                    result = await llm_request_with_retry(
                        session, "POST", url,
                        json=payload, headers=headers,
                        config=retry_config,
                        is_streaming=True,
                    )
                    
                    if not result.success or result.response is None:
                        _close_retry_response(result)
                        error_msg = result.error or "Unknown error"
                        logger.error(f"LLM stream connection failed after {result.attempts} attempts: {error_msg}")
                        error_data = json.dumps({"error": f"LLM Error: {error_msg}", "done": True})
                        await response.write(f"data: {error_data}\n\n".encode('utf-8'))
                        return response
                    
                    # Note: From here on, NO RETRY - streaming has begun
                    async with result.response as llm_response:
                        if llm_response.status != 200:
                            error_msg = await llm_response.text()
                            logger.error(f"LLM stream error: {error_msg[:200]}")
                            error_data = json.dumps({"error": f"LLM Error: {error_msg[:200]}", "done": True})
                            await response.write(f"data: {error_data}\n\n".encode('utf-8'))
                            return response
                    
                        # Stream chunks with newline buffering to handle partial lines
                        buffer = ""
                        stream_done = False
                        # F7: Accumulate full content for fix detection
                        full_content = ""
                        async for chunk in llm_response.content.iter_chunked(1024):
                            buffer += chunk.decode('utf-8', errors='ignore')

                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                if not line:
                                    continue

                                # Handle different streaming formats
                                if is_anthropic_api:
                                    # Anthropic uses SSE format with different event types
                                    if not line.startswith('data:'):
                                        # Skip event: type lines
                                        continue

                                    payload_str = line[5:].strip()
                                    if not payload_str:
                                        continue

                                    try:
                                        chunk_json = json.loads(payload_str)
                                        event_type = chunk_json.get('type', '')

                                        if event_type == 'message_stop':
                                            done_data = json.dumps({"delta": "", "done": True})
                                            await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                            stream_done = True
                                            break
                                        elif event_type == 'content_block_delta':
                                            delta = chunk_json.get('delta', {}).get('text', '')
                                            if delta:
                                                full_content += delta  # F7: Accumulate
                                                chunk_data = json.dumps({"delta": delta, "done": False})
                                                await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                    except json.JSONDecodeError:
                                        continue
                                elif is_ollama:
                                    # Ollama uses newline-delimited JSON (not SSE)
                                    try:
                                        chunk_json = json.loads(line)
                                        # Check if stream is done
                                        if chunk_json.get('done', False):
                                            done_data = json.dumps({"delta": "", "done": True})
                                            await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                            stream_done = True
                                            break
                                        # Extract content delta
                                        delta = chunk_json.get('message', {}).get('content', '')
                                        if delta:
                                            full_content += delta  # F7: Accumulate
                                            chunk_data = json.dumps({"delta": delta, "done": False})
                                            await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                    except json.JSONDecodeError:
                                        continue
                                else:
                                    # OpenAI uses SSE format
                                    if not line.startswith('data:'):
                                        continue

                                    payload_str = line[5:].strip()
                                    if payload_str == '[DONE]':
                                        done_data = json.dumps({"delta": "", "done": True})
                                        await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                        stream_done = True
                                        break

                                    if not payload_str:
                                        continue

                                    try:
                                        chunk_json = json.loads(payload_str)
                                        delta = chunk_json.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                        if delta:
                                            full_content += delta  # F7: Accumulate
                                            chunk_data = json.dumps({"delta": delta, "done": False})
                                            await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                    except json.JSONDecodeError:
                                        continue

                            if stream_done:
                                break
                    
                    # Process any remaining buffered line if stream ended without newline
                    if not stream_done and buffer.strip():
                        line = buffer.strip()
                        if is_ollama:
                            # Ollama newline-delimited JSON
                            try:
                                chunk_json = json.loads(line)
                                if chunk_json.get('done', False):
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                else:
                                    delta = chunk_json.get('message', {}).get('content', '')
                                    if delta:
                                        chunk_data = json.dumps({"delta": delta, "done": False})
                                        await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                            except json.JSONDecodeError:
                                pass
                        else:
                            # OpenAI SSE format
                            if line.startswith('data:'):
                                payload_str = line[5:].strip()
                                if payload_str == '[DONE]':
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                else:
                                    try:
                                        chunk_json = json.loads(payload_str)
                                        delta = chunk_json.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                        if delta:
                                            full_content += delta  # F7: Accumulate
                                            chunk_data = json.dumps({"delta": delta, "done": False})
                                            await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                    except json.JSONDecodeError:
                                        pass

                    # F7: Detect and send fix suggestions after stream completes
                    if full_content:
                        import re
                        FIX_PATTERN = re.compile(r'```json\s*(\{[^`]*?"fixes"[^`]*?\})\s*```', re.DOTALL)
                        fix_match = FIX_PATTERN.search(full_content)

                        if fix_match:
                            try:
                                fix_json = json.loads(fix_match.group(1))
                                if validate_fix_schema(fix_json):
                                    # Send as separate SSE event
                                    fix_data = json.dumps({
                                        "type": "fix_suggestion",
                                        "data": fix_json
                                    })
                                    await response.write(f"data: {fix_data}\n\n".encode('utf-8'))
                            except json.JSONDecodeError:
                                pass  # Invalid JSON, ignore

                except Exception as stream_err:
                    error_data = json.dumps({"error": str(stream_err), "done": True})
                    await response.write(f"data: {error_data}\n\n".encode('utf-8'))
            
            return response
            
        except aiohttp.ClientError as e:
            print(f"[ComfyUI-Doctor] Chat Network Error: {e}")
            return web.json_response({"error": f"Network Error: {str(e)}"}, status=503)
        except Exception as e:
            print(f"[ComfyUI-Doctor] Chat Failed: {e}")
            return web.json_response({"error": str(e)}, status=500)
        
    @server.PromptServer.instance.routes.get("/debugger/history")
    async def api_get_history(request):
        """
        API endpoint to get error analysis history.
        
        Returns:
            JSON with history list (most recent first).
        """
        return web.json_response({
            "history": get_analysis_history(),
            "count": len(get_analysis_history()),
        })

    @server.PromptServer.instance.routes.post("/debugger/clear_history")
    async def api_clear_history(request):
        """
        API endpoint to clear error analysis history.
        
        Returns:
            JSON with success status.
        """
        try:
            success = clear_analysis_history()
            return web.json_response({"success": success})
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/provider_defaults")
    async def api_get_provider_defaults(request):
        """
        API endpoint to get default URLs for LLM providers.
        Supports environment variable overrides for cross-platform compatibility.

        Returns:
            JSON with provider default URLs.
        """
        return web.json_response({
            "ollama": OLLAMA_BASE_URL,
            "lmstudio": LMSTUDIO_BASE_URL,
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "deepseek": "https://api.deepseek.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
            "xai": "https://api.x.ai/v1",
            "openrouter": "https://openrouter.ai/api/v1"
        })

    @server.PromptServer.instance.routes.post("/doctor/verify_key")
    async def api_verify_key(request):
        """
        API endpoint to verify LLM API key validity.
        Tests by calling the /models endpoint.
        
        Payload: { "base_url": str, "api_key": str }
        Returns: { "success": bool, "message": str, "is_local": bool }
        """
        try:
            data = await request.json()
            base_url = data.get("base_url", DOCTOR_LLM_BASE_URL)
            api_key = data.get("api_key", "")
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in verify_key: {ssrf_error}")
                return web.json_response({
                    "success": False,
                    "message": f"Invalid Base URL: {ssrf_error}",
                    "is_local": False
                })

            # Check if this is a local LLM
            is_local = is_local_llm_url(base_url)
            
            # Local LLMs may not require API key
            if not api_key and not is_local:
                return web.json_response({
                    "success": False,
                    "message": "No API key provided",
                    "is_local": False
                })
            
            # Normalize base URL
            base_url = base_url.rstrip("/")
            
            # Use placeholder for local LLMs without key
            if is_local and not api_key:
                api_key = "local-llm"
            
            # Prepare request
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{base_url}/models"
            
            # R7: Rate limit check (light limiter for quick requests)
            if not SessionManager.get_light_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/verify_key")
                return web.json_response({
                    "success": False,
                    "message": "Rate limit exceeded. Please wait before retrying.",
                    "is_local": is_local
                })
            
            session = await SessionManager.get_session()
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if response.status == 200:
                    msg = "API key is valid" if not is_local else "Local LLM connection successful"
                    logger.info(f"API key verification successful - base_url={base_url}, is_local={is_local}")
                    return web.json_response({
                        "success": True,
                        "message": msg,
                        "is_local": is_local
                    })
                else:
                    error_text = await response.text()
                    if len(error_text) > 200:
                        error_text = error_text[:200] + "..."
                    logger.warning(f"API key verification failed - status={response.status}, base_url={base_url}")
                    return web.json_response({
                        "success": False,
                        "message": f"Verification failed ({response.status}): {error_text}",
                        "is_local": is_local
                    })
                        
        except aiohttp.ClientError as e:
            return web.json_response({
                "success": False,
                "message": f"Connection error: {str(e)}",
                "is_local": is_local_llm_url(data.get("base_url", "")) if 'data' in locals() else False
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "message": f"Error: {str(e)}",
                "is_local": False
            })

    @server.PromptServer.instance.routes.post("/doctor/list_models")
    async def api_list_models(request):
        """
        API endpoint to list available LLM models.
        
        Payload: { "base_url": str, "api_key": str }
        Returns: { "success": bool, "models": list[{name, id}], "message": str }
        """
        try:
            data = await request.json()
            base_url = data.get("base_url", DOCTOR_LLM_BASE_URL)
            api_key = data.get("api_key", "")
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in list_models: {ssrf_error}")
                return web.json_response({
                    "success": False,
                    "models": [],
                    "message": f"Invalid Base URL: {ssrf_error}"
                })

            is_local = is_local_llm_url(base_url)
            
            if not api_key and not is_local:
                return web.json_response({
                    "success": False,
                    "models": [],
                    "message": "No API key provided"
                })
            
            base_url = base_url.rstrip("/")
            base_info = parse_base_url(base_url)
            if is_local and not api_key:
                api_key = "local-llm"

            # Determine if this is Ollama or OpenAI-compatible API
            is_ollama = is_local and base_info and base_info.get("port") == 11434

            if is_ollama:
                # Ollama uses /api/tags endpoint (remove /v1 if present)
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/tags"
            else:
                url = f"{base_url}/models"

            headers = {"Authorization": f"Bearer {api_key}"}
            
            # R7: Rate limit check (light limiter for quick requests)
            if not SessionManager.get_light_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/list_models")
                return web.json_response({
                    "success": False,
                    "models": [],
                    "message": "Rate limit exceeded. Please wait before retrying."
                })
            
            session = await SessionManager.get_session()
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if response.status != 200:
                    return web.json_response({
                        "success": False,
                        "models": [],
                        "message": f"Failed to fetch models ({response.status})"
                    })
                
                try:
                    result = await response.json()
                    models = []
                    
                    # Handle OpenAI-style response
                    if "data" in result:
                        for m in result["data"]:
                            model_id = m.get("id", "")
                            models.append({
                                "id": model_id,
                                "name": model_id
                            })
                    # Handle Ollama-style response
                    elif "models" in result:
                        for m in result["models"]:
                            model_name = m.get("name", m.get("model", ""))
                            models.append({
                                "id": model_name,
                                "name": model_name
                            })

                    logger.info(f"Retrieved {len(models)} models from {url}")
                    return web.json_response({
                        "success": True,
                        "models": models,
                        "message": f"Found {len(models)} models"
                    })
                    
                except (json.JSONDecodeError, KeyError) as e:
                    return web.json_response({
                        "success": False,
                        "models": [],
                        "message": f"Failed to parse model list: {str(e)}"
                    })
                        
        except aiohttp.ClientError as e:
            return web.json_response({
                "success": False,
                "models": [],
                "message": f"Connection error: {str(e)}"
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "models": [],
                "message": f"Error: {str(e)}"
            })
    
    # ---- F4: Statistics Dashboard API Endpoints ----
    
    @server.PromptServer.instance.routes.get("/doctor/statistics")
    async def api_get_statistics(request):
        """
        API endpoint to get error statistics for dashboard.
        
        Query params: ?time_range_days=30 (default: 30)
        
        Returns: {
            "success": bool,
            "statistics": {
                "total_errors": int,
                "pattern_frequency": {pattern_id: count},
                "category_breakdown": {category: count},
                "top_patterns": [{pattern_id, count, category}],
                "resolution_rate": {resolved, unresolved, ignored},
                "trend": {last_24h, last_7d, last_30d}
            }
        }
        """
        try:
            from .statistics import StatisticsCalculator
            
            time_range_days = int(request.query.get("time_range_days", 30))
            
            # Get history from SmartLogger
            history = get_analysis_history()
            
            # Calculate statistics
            statistics = StatisticsCalculator.calculate(history, time_range_days)
            
            logger.info(f"Statistics calculated: total_errors={statistics['total_errors']}, time_range={time_range_days}d")
            
            return web.json_response({
                "success": True,
                "statistics": statistics
            })
        except Exception as e:
            logger.error(f"Statistics API error: {str(e)}")
            return web.json_response({
                "success": False,
                "error": str(e),
                "statistics": {
                    "total_errors": 0,
                    "pattern_frequency": {},
                    "category_breakdown": {},
                    "top_patterns": [],
                    "resolution_rate": {"resolved": 0, "unresolved": 0, "ignored": 0},
                    "trend": {"last_24h": 0, "last_7d": 0, "last_30d": 0}
                }
            })
    
    @server.PromptServer.instance.routes.post("/doctor/statistics/reset")
    async def api_reset_statistics(request):
        """
        API endpoint to reset statistics (clears all error history).
        
        Returns: {"success": bool, "message": str}
        """
        try:
            success = clear_analysis_history()
            if success:
                logger.info("Statistics reset (history cleared)")
                return web.json_response({"success": True, "message": "Statistics reset successfully"})
            else:
                return web.json_response({"success": False, "message": "Failed to clear history"}, status=500)
        except Exception as e:
            logger.error(f"Statistics reset API error: {str(e)}")
            return web.json_response({"success": False, "message": str(e)}, status=500)
    
    @server.PromptServer.instance.routes.post("/doctor/mark_resolved")
    async def api_mark_error_resolved(request):
        """
        API endpoint to mark an error as resolved/unresolved/ignored.
        
        Body: {
            "timestamp": "2026-01-04T12:00:00",
            "status": "resolved"|"unresolved"|"ignored"
        }
        
        Returns: {"success": bool, "message": str}
        """
        try:
            data = await request.json()
            timestamp = data.get("timestamp")
            status = data.get("status", "resolved")
            
            if not timestamp:
                return web.json_response({"success": False, "message": "Missing timestamp"}, status=400)
            
            if status not in ["resolved", "unresolved", "ignored"]:
                return web.json_response({"success": False, "message": "Invalid status"}, status=400)
            
            from .logger import update_resolution_status

            if update_resolution_status(timestamp, status):
                logger.info(f"Error marked as {status}: {timestamp}")
                return web.json_response({"success": True, "message": f"Error marked as {status}"})

            return web.json_response({"success": False, "message": "Timestamp not found"}, status=404)
                
        except Exception as e:
            logger.error(f"Mark resolved API error: {str(e)}")
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/health")
    async def api_health(request):
        """
        Health endpoint for internal diagnostics.
        Returns logger queue stats, SSRF counters, and last analysis state.
        """
        try:
            last_analysis = get_last_analysis()
            analysis_meta = last_analysis.get("analysis_metadata") or {}
            payload = {
                "logger": get_logger_metrics(),
                "ssrf": get_ssrf_metrics(),
                "last_analysis": {
                    "timestamp": last_analysis.get("timestamp"),
                    "pipeline_status": analysis_meta.get("pipeline_status"),
                },
            }
            return web.json_response({"success": True, "health": payload})
        except Exception as e:
            logger.error(f"Health API error: {str(e)}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # ---- S3: Telemetry API Endpoints ----
    from telemetry import get_telemetry_store
    
    # Initialize telemetry with config setting
    _telemetry_store = get_telemetry_store()
    _telemetry_store.enabled = CONFIG.telemetry_enabled

    @server.PromptServer.instance.routes.get("/doctor/telemetry/status")
    async def api_telemetry_status(request):
        """
        Get telemetry status and buffer stats.
        Returns: {"success": bool, "enabled": bool, "stats": {...}}
        """
        try:
            store = get_telemetry_store()
            stats = store.get_stats()
            return web.json_response({
                "success": True,
                "enabled": store.enabled,
                "stats": stats,
                "upload_destination": None,  # Phase 1-3: local only
            })
        except Exception as e:
            logger.error(f"Telemetry status API error: {str(e)}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/telemetry/buffer")
    async def api_telemetry_buffer(request):
        """
        Get buffered telemetry events.
        Returns: {"success": bool, "events": [...]}
        """
        try:
            store = get_telemetry_store()
            events = store.get_buffer()
            return web.json_response({
                "success": True,
                "events": events,
                "count": len(events),
            })
        except Exception as e:
            logger.error(f"Telemetry buffer API error: {str(e)}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/track")
    async def api_telemetry_track(request):
        """
        Record a telemetry event.
        Body: {"category": str, "action": str, "label"?: str, "value"?: int}
        Returns: {"success": bool, "message": str}
        """
        try:
            # Security: Same-origin check (reject cross-origin requests)
            origin = request.headers.get("Origin", "")
            host = request.headers.get("Host", "")
            if origin:
                # Extract host from origin (e.g., "http://localhost:8188" -> "localhost:8188")
                from urllib.parse import urlparse
                origin_host = urlparse(origin).netloc
                if origin_host and host and origin_host != host:
                    return web.Response(status=403, text="Cross-origin request rejected")
            
            # Security: Check Content-Type
            content_type = request.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                return web.Response(status=400, text="Content-Type must be application/json")
            
            # Security: Payload size limit (1KB)
            content_length = request.content_length or 0
            if content_length > 1024:
                return web.Response(status=413, text="Payload too large")
            
            # Parse JSON
            try:
                data = await request.json()
            except Exception:
                return web.Response(status=400, text="Invalid JSON")
            
            # Security: Reject unexpected fields
            allowed_fields = {"category", "action", "label", "value"}
            if set(data.keys()) - allowed_fields:
                return web.Response(status=400, text="Unexpected fields")
            
            # Track event
            store = get_telemetry_store()
            success, message = store.track(data)
            
            return web.json_response({"success": success, "message": message})
        except Exception as e:
            logger.error(f"Telemetry track API error: {str(e)}")
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/clear")
    async def api_telemetry_clear(request):
        """
        Clear all buffered telemetry events.
        Returns: {"success": bool, "message": str}
        """
        try:
            store = get_telemetry_store()
            store.clear()
            return web.json_response({"success": True, "message": "Buffer cleared"})
        except Exception as e:
            logger.error(f"Telemetry clear API error: {str(e)}")
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/telemetry/export")
    async def api_telemetry_export(request):
        """
        Export telemetry buffer as downloadable JSON file.
        Returns: JSON file download
        """
        try:
            store = get_telemetry_store()
            json_data = store.export_json()
            
            return web.Response(
                body=json_data,
                content_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=telemetry_export.json"
                }
            )
        except Exception as e:
            logger.error(f"Telemetry export API error: {str(e)}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/toggle")
    async def api_telemetry_toggle(request):
        """
        Toggle telemetry enabled/disabled state.
        Body: {"enabled": bool}
        Returns: {"success": bool, "enabled": bool}
        """
        try:
            data = await request.json()
            enabled = data.get("enabled", False)
            
            store = get_telemetry_store()
            store.enabled = bool(enabled)
            
            return web.json_response({
                "success": True,
                "enabled": store.enabled,
                "message": "Telemetry enabled" if store.enabled else "Telemetry disabled"
            })
        except Exception as e:
            logger.error(f"Telemetry toggle API error: {str(e)}")
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/plugins")
    async def api_plugins(request):
        """
        Plugin trust report (scan-only).
        Returns the trust classification for each discovered community plugin without importing code.
        """
        try:
            from pathlib import Path
            from .pipeline.plugins import scan_plugins
            from config import CONFIG

            plugin_dir = Path(__file__).resolve().parent / "pipeline" / "plugins" / "community"
            report = scan_plugins(plugin_dir)

            def sanitize_manifest(manifest):
                if not isinstance(manifest, dict):
                    return None
                keys = [
                    "id",
                    "name",
                    "version",
                    "author",
                    "min_doctor_version",
                    "signature_alg",
                ]
                out = {k: manifest.get(k) for k in keys if k in manifest}
                if "signature" in manifest:
                    out["has_signature"] = bool(manifest.get("signature"))
                return out

            plugins = []
            trust_counts = {}
            for entry in report:
                trust = entry.get("trust")
                trust_counts[trust] = trust_counts.get(trust, 0) + 1
                plugins.append(
                    {
                        "file": getattr(entry.get("file"), "name", str(entry.get("file"))),
                        "plugin_id": entry.get("plugin_id"),
                        "trust": trust,
                        "reason": entry.get("reason"),
                        "manifest": sanitize_manifest(entry.get("manifest")),
                    }
                )

            payload = {
                "config": {
                    "enabled": bool(getattr(CONFIG, "enable_community_plugins", False)),
                    "allowlist_count": len(getattr(CONFIG, "plugin_allowlist", []) or []),
                    "blocklist_count": len(getattr(CONFIG, "plugin_blocklist", []) or []),
                    "signature_required": bool(getattr(CONFIG, "plugin_signature_required", False)),
                    "signature_alg": getattr(CONFIG, "plugin_signature_alg", "hmac-sha256"),
                    "signature_key_configured": bool(getattr(CONFIG, "plugin_signature_key", "") or ""),
                },
                "trust_counts": trust_counts,
                "plugins": plugins,
            }
            return web.json_response({"success": True, "plugins": payload})
        except Exception as e:
            logger.error(f"Plugins API error: {str(e)}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
        
    print("[ComfyUI-Doctor] 🌐 API Hooks registered:")
    print("  - GET  /debugger/last_analysis")
    print("  - GET  /debugger/history")
    print("  - POST /debugger/set_language")
    print("  - POST /debugger/clear_history")
    print("  - POST /doctor/analyze")
    print("  - POST /doctor/chat (SSE streaming)")
    print("  - POST /doctor/verify_key")
    print("  - POST /doctor/list_models")
    print("  - GET  /doctor/statistics (F4)")
    print("  - POST /doctor/mark_resolved (F4)")
    print("  - GET  /doctor/health")
    print("  - GET  /doctor/plugins")
    print("  - GET  /doctor/telemetry/status (S3)")
    print("  - GET  /doctor/telemetry/buffer (S3)")
    print("  - POST /doctor/telemetry/track (S3)")
    print("  - POST /doctor/telemetry/clear (S3)")
    print("  - GET  /doctor/telemetry/export (S3)")
    print("  - POST /doctor/telemetry/toggle (S3)")
    print("\n")
    print("💬 Questions? Updates? Suggestions and Contributions are welcome!")
    print("⭐ Give us a Star on GitHub - it's always good for the Doctor's health! 💝")
    print("   https://github.com/rookiestar28/ComfyUI-Doctor")
    print("\n")

except ImportError:
    print("[ComfyUI-Doctor] ⚠️ Server module not found (Running in standalone mode?)")
except Exception as e:
    print(f"[ComfyUI-Doctor] ⚠️ Failed to register API: {e}")


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
__version__ = _read_pyproject_value(r'(?m)^version\\s*=\\s*["\\\']([^"\\\']+)["\\\']', fallback="unknown")
__repository__ = _read_pyproject_value(r'(?m)^Repository\\s*=\\s*["\\\']([^"\\\']+)["\\\']', fallback="https://github.com/rookiestar28/ComfyUI-Doctor")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY", "__version__", "__repository__"]
