"""
Configuration module for ComfyUI Runtime Diagnostics.
Provides centralized, JSON-overridable configuration.
"""

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class DiagnosticsConfig:
    """Central configuration for the diagnostics system."""
    
    # Logging
    max_log_files: int = 10
    buffer_limit: int = 100
    traceback_timeout_seconds: float = 5.0
    
    # History
    history_size: int = 20
    
    # i18n
    default_language: str = "zh_TW"
    
    # Features
    enable_web_panel: bool = True
    enable_api: bool = True
    
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
