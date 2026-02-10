"""
Server-side secret storage for ComfyUI-Doctor.

Design:
- Stores provider API keys in a local JSON file under Doctor data dir
- Atomic write (tmp -> replace) to reduce corruption risk
- Best-effort permission hardening on POSIX (0600)
- Never returns all raw values in status APIs
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .doctor_paths import get_doctor_data_dir


class SecretStore:
    STORE_FILENAME = "secrets.json"

    def __init__(self, filepath: Optional[str] = None) -> None:
        target_path = filepath or str(Path(get_doctor_data_dir()) / self.STORE_FILENAME)
        self._filepath = Path(target_path)
        self._lock = threading.RLock()

    @property
    def filepath(self) -> str:
        return str(self._filepath)

    def _ensure_parent(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)

    def _chmod_0600_best_effort(self) -> None:
        if os.name == "posix":
            try:
                os.chmod(self._filepath, 0o600)
            except Exception:
                pass

    def _load_all(self) -> Dict[str, str]:
        if not self._filepath.exists():
            return {}

        try:
            payload = json.loads(self._filepath.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("secrets file is not a JSON object")

            out: Dict[str, str] = {}
            for key, value in payload.items():
                if isinstance(key, str) and isinstance(value, str):
                    normalized = key.strip().lower()
                    if normalized and value.strip():
                        out[normalized] = value
            return out
        except Exception:
            # Corruption recovery: rotate aside and continue clean.
            try:
                ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                backup = self._filepath.with_name(f"{self._filepath.name}.corrupt-{ts}")
                self._filepath.rename(backup)
            except Exception:
                pass
            return {}

    def _save_all(self, data: Dict[str, str]) -> None:
        self._ensure_parent()
        tmp = self._filepath.with_suffix(self._filepath.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self._filepath))
        self._chmod_0600_best_effort()

    @staticmethod
    def _normalize_provider_id(provider_id: str) -> str:
        return (provider_id or "").strip().lower()

    def get_secret(self, provider_id: str) -> Optional[str]:
        pid = self._normalize_provider_id(provider_id)
        if not pid:
            return None
        with self._lock:
            return self._load_all().get(pid)

    def set_secret(self, provider_id: str, secret: str) -> None:
        pid = self._normalize_provider_id(provider_id)
        value = (secret or "").strip()
        if not pid:
            raise ValueError("provider_id is required")
        if not value:
            raise ValueError("secret must be non-empty")

        with self._lock:
            data = self._load_all()
            data[pid] = value
            self._save_all(data)

    def clear_secret(self, provider_id: str) -> bool:
        pid = self._normalize_provider_id(provider_id)
        if not pid:
            return False

        with self._lock:
            data = self._load_all()
            if pid not in data:
                return False
            data.pop(pid, None)
            self._save_all(data)
            return True

    def clear_all(self) -> int:
        with self._lock:
            data = self._load_all()
            count = len(data)
            self._save_all({})
            return count

    def get_status(self, providers: Optional[list[str]] = None) -> Dict[str, Dict[str, object]]:
        with self._lock:
            data = self._load_all()
            provider_list = providers or sorted(set(list(data.keys()) + ["generic"]))
            status: Dict[str, Dict[str, object]] = {}
            for provider in provider_list:
                pid = self._normalize_provider_id(provider)
                has_value = bool(data.get(pid))
                status[pid] = {
                    "configured": has_value,
                    "source": "server_store" if has_value else "none",
                }
            return status


_secret_store: Optional[SecretStore] = None


def get_secret_store() -> SecretStore:
    global _secret_store
    if _secret_store is None:
        _secret_store = SecretStore()
    return _secret_store

