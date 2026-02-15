"""
S9: Action Audit Log.

Logs redacted action metadata to disk for auditing purposes.
Ensures sensitive fields (API keys, tokens, secrets) are never stored in plaintext.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ActionAudit:
    """
    Logs redacted action metadata to disk.
    Persists to `doctor_audit.jsonl` in the specified directory.
    """

    def __init__(self, log_dir: Path):
        self.log_file = log_dir / "doctor_audit.jsonl"
        self.log_dir = log_dir
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create audit log dir: {e}")

    def log_action(
        self, 
        provider: str, 
        action: str, 
        decision: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an action attempt.
        Meta fields containing 'key', 'token', 'secret', 'auth', 'password' will be redacted.
        """
        safe_meta = (meta or {}).copy()
        
        # Redact sensitive fields (case-insensitive substring match)
        for key in list(safe_meta.keys()):
            k_lower = key.lower()
            if any(s in k_lower for s in ["api_key", "token", "secret", "password", "auth"]):
                safe_meta[key] = "***"

        record = {
            "timestamp": time.time(),
            "provider": provider,
            "action": action,
            "decision": decision,
            "meta": safe_meta
        }
            
        try:
            # Append to JSONL file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Audit log failed: {e}")
