from dataclasses import dataclass
import os
from typing import Optional

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
            MAX_HISTORY_ENTRIES=int(os.getenv("DOCTOR_GUARDRAIL_MAX_HISTORY", "1000")),
            MAX_LOG_SIZE_MB=int(os.getenv("DOCTOR_GUARDRAIL_MAX_LOG_SIZE_MB", "10")),
            MAX_JOB_RETENTION_SECONDS=int(os.getenv("DOCTOR_GUARDRAIL_JOB_RETENTION", "86400")),
            RATE_LIMIT_WINDOW_SECONDS=int(os.getenv("DOCTOR_GUARDRAIL_RATE_LIMIT_WINDOW", "60")),
            AGGREGATION_WINDOW_SECONDS=int(os.getenv("DOCTOR_GUARDRAIL_AGGREGATION_WINDOW", "60")),
            PROVIDER_TIMEOUT_SECONDS=int(os.getenv("DOCTOR_GUARDRAIL_PROVIDER_TIMEOUT", "30")),
            PROVIDER_MAX_RETRIES=int(os.getenv("DOCTOR_GUARDRAIL_PROVIDER_RETRIES", "3"))
        )
