from dataclasses import dataclass
import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default

@dataclass
class GuardrailConfig:
    """
    R17: Centralized configuration for runtime guardrails.
    Precedence: ENV > ComfyUI Settings (Future) > Defaults
    """
    # History & Persistence
    MAX_HISTORY_ENTRIES: int = 1000
    MAX_LOG_SIZE_MB: int = 10
    
    MAX_JOB_RETENTION_SECONDS: int = 86400  # 24h
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    AGGREGATION_WINDOW_SECONDS: int = 60
    
    # Provider Safety
    PROVIDER_TIMEOUT_SECONDS: int = 30
    PROVIDER_MAX_RETRIES: int = 3
    
    @classmethod
    def load(cls) -> "GuardrailConfig":
        """Load configuration from environment variables with defaults."""
        return cls(
            MAX_HISTORY_ENTRIES=_env_int("DOCTOR_GUARDRAIL_MAX_HISTORY", 1000),
            MAX_LOG_SIZE_MB=_env_int("DOCTOR_GUARDRAIL_MAX_LOG_SIZE_MB", 10),
            MAX_JOB_RETENTION_SECONDS=_env_int("DOCTOR_GUARDRAIL_JOB_RETENTION", 86400),
            RATE_LIMIT_WINDOW_SECONDS=_env_int("DOCTOR_GUARDRAIL_RATE_LIMIT_WINDOW", 60),
            AGGREGATION_WINDOW_SECONDS=_env_int("DOCTOR_GUARDRAIL_AGGREGATION_WINDOW", 60),
            PROVIDER_TIMEOUT_SECONDS=_env_int("DOCTOR_GUARDRAIL_PROVIDER_TIMEOUT", 30),
            PROVIDER_MAX_RETRIES=_env_int("DOCTOR_GUARDRAIL_PROVIDER_RETRIES", 3),
        )
