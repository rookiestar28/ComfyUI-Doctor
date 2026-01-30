"""
Configuration module for ComfyUI Runtime Diagnostics.
Provides centralized, JSON-overridable configuration.
"""

import os
import json
import tempfile
from dataclasses import dataclass, asdict, field
from typing import Optional, List

def _get_config_path_candidates() -> List[str]:
    """
    Return config.json path candidates in priority order.

    R18: Prefer canonical Doctor data dir for persisted config (Desktop-safe),
    but keep backward-compatible fallback to the legacy extension-root config.json.
    """
    candidates: List[str] = []
    try:
        from services.doctor_paths import get_doctor_data_dir  # local import to avoid import-time coupling
        candidates.append(os.path.join(get_doctor_data_dir(), "config.json"))
    except Exception:
        pass

    # Legacy location (extension root)
    candidates.append(os.path.join(os.path.dirname(__file__), "config.json"))

    # OS temp fallback (last resort; avoids writing under Desktop resources)
    candidates.append(os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor", "config.json"))
    return candidates


def _get_primary_config_path() -> str:
    return _get_config_path_candidates()[0]


@dataclass
class DiagnosticsConfig:
    """Central configuration for the diagnostics system."""
    
    # Logging
    max_log_files: int = 10
    buffer_limit: int = 100
    traceback_timeout_seconds: float = 5.0
    log_queue_maxsize: int = 1000
    
    # History
    # history_size: 0 = unbounded, >0 = max entries
    history_size: int = 0
    # history_size_bytes: Max size in bytes for history file (default 5MB)
    history_size_bytes: int = 5 * 1024 * 1024
    
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

    # R12: Token Budget Management
    r12_enabled_remote: bool = True
    r12_enabled_local: bool = False
    r12_soft_max_tokens_remote: int = 4500
    r12_hard_max_tokens_remote: int = 6000
    r12_soft_max_tokens_local: int = 12000
    r12_hard_max_tokens_local: int = 16000
    r12_policy_profile: str = "remote_strict"  # remote_strict, local_soft
    r12_estimator_fallback_cpt: float = 4.0
    r12_estimator_safety_mult: float = 1.15
    r12_prune_default_depth: int = 3
    r12_prune_default_nodes: int = 40
    r12_overhead_fixed: int = 1000  # Fixed overhead (reserved tokens for structure)
    
    # R14: Error Context Extraction & Prompt Optimization
    r14_use_prompt_composer: bool = True  # Use PromptComposer for unified context formatting
    r14_use_legacy_format: bool = False   # Fallback to legacy format (traceback-first)
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)


def load_config() -> DiagnosticsConfig:
    """
    Load configuration from config.json if it exists,
    otherwise return defaults.
    """
    for config_path in _get_config_path_candidates():
        if os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return DiagnosticsConfig(**data)
            except Exception:
                # Fall back to next candidate on any error
                pass
    return DiagnosticsConfig()


def save_config(config: DiagnosticsConfig) -> bool:
    """Save current configuration to config.json."""
    payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False)
    for config_path in _get_config_path_candidates():
        try:
            dir_path = os.path.dirname(config_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            tmp_path = f"{config_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, config_path)
            return True
        except Exception:
            try:
                tmp_path = f"{config_path}.tmp"
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            continue
    return False


# Global config instance
CONFIG = load_config()
