"""
Configuration module for ComfyUI Runtime Diagnostics.
Provides centralized, JSON-overridable configuration.
"""

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Optional, List


@dataclass
class DiagnosticsConfig:
    """Central configuration for the diagnostics system."""
    
    # Logging
    max_log_files: int = 10
    buffer_limit: int = 100
    traceback_timeout_seconds: float = 5.0
    log_queue_maxsize: int = 1000
    
    # History
    history_size: int = 20
    
    # i18n
    default_language: str = "zh_TW"
    
    # Features
    enable_web_panel: bool = True
    enable_api: bool = True

    # Plugins (P0 hardening)
    enable_community_plugins: bool = False
    plugin_allowlist: List[str] = field(default_factory=list)
    plugin_blocklist: List[str] = field(default_factory=list)
    plugin_max_file_size_bytes: int = 262144  # 256 KiB
    plugin_max_scan_files: int = 50
    plugin_reject_symlinks: bool = True
    plugin_signature_required: bool = False
    plugin_signature_key: str = ""
    plugin_signature_alg: str = "hmac-sha256"
    
    # Telemetry (S3)
    telemetry_enabled: bool = False  # Opt-in: disabled by default
    
    # R7: Rate limiting
    llm_core_rate_limit: int = 30     # req/min for analyze, chat
    llm_light_rate_limit: int = 10    # req/min for verify_key, list_models
    llm_max_concurrent: int = 3       # max simultaneous LLM requests
    
    # R6: Retry configuration
    llm_max_retries: int = 2
    llm_request_timeout: float = 60.0   # per-attempt timeout (seconds)
    llm_total_timeout: float = 180.0    # total operation timeout (seconds)
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)


def load_config() -> DiagnosticsConfig:
    """
    Load configuration from config.json if it exists,
    otherwise return defaults.
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
                return DiagnosticsConfig(**data)
        except Exception:
            pass  # Fall back to defaults on any error
    return DiagnosticsConfig()


def save_config(config: DiagnosticsConfig) -> bool:
    """Save current configuration to config.json."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


# Global config instance
CONFIG = load_config()
