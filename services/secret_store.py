"""
Server-side secret storage for ComfyUI-Doctor.

Design:
- Stores provider API keys in a local JSON file under Doctor data dir
- Atomic write (tmp -> replace) to reduce corruption risk
- Best-effort permission hardening on POSIX/Windows
- Optional encryption-at-rest via env key (transparent load/save)
- Encrypted payloads use PBKDF2-HMAC-SHA256 key derivation, HMAC-SHA256
  stream XOR encryption, and encrypt-then-MAC over nonce + ciphertext
- Never returns all raw values in status APIs
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import subprocess
import threading
import sys
from datetime import datetime, timezone
from pathlib import Path, PosixPath, WindowsPath
from typing import Dict, Optional, Tuple

from .doctor_paths import get_doctor_data_dir

logger = logging.getLogger(__name__)


def _is_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class SecretStoreError(RuntimeError):
    """Secret store runtime error."""


class SecretStoreKeyRequiredError(SecretStoreError):
    """Raised when encryption is required but key is missing."""


STATE_OK = "ok"
STATE_EMPTY = "empty"
STATE_LOCKED_KEY_REQUIRED = "locked_key_required"
STATE_LOCKED_KEY_MISMATCH = "locked_key_mismatch"
STATE_CORRUPT = "corrupt"
LOCKED_STATES = frozenset({STATE_LOCKED_KEY_REQUIRED, STATE_LOCKED_KEY_MISMATCH})

STORE_LOCKED_ERROR_CODE = "secret_store_locked"
SECRET_STORE_LOCKED_MESSAGE = (
    "The server secret store is locked: the encrypted store cannot be read with the configured "
    "DOCTOR_SECRET_STORE_ENCRYPTION_KEY. Restore the original key, or move the store file aside to "
    "start a new store."
)


class SecretStoreLockedError(SecretStoreError):
    """The encrypted store cannot be authenticated with the configured key; it is left untouched."""

    def __init__(self, state: str) -> None:
        super().__init__(SECRET_STORE_LOCKED_MESSAGE)
        self.state = state


class _SecretStoreAuthenticationError(SecretStoreError):
    """MAC verification failed: wrong key or tampered ciphertext (indistinguishable)."""


class SecretStore:
    STORE_FILENAME = "secrets.json"
    FORMAT_VERSION = 1
    FORMAT_TYPE = "comfyui-doctor-secret-store"
    ENC_KDF = "pbkdf2_hmac_sha256"
    ENC_CIPHER = "hmac_sha256_xor_stream"
    ENC_MAC = "hmac_sha256"
    ENC_MAC_INPUT = "nonce+ciphertext"
    ENC_CONSTRUCTION = "encrypt_then_mac"
    ENC_ITERATIONS = 200_000
    ENC_SALT_BYTES = 16
    ENC_NONCE_BYTES = 16
    WARNED_INSECURE = False

    def __init__(self, filepath: Optional[str] = None) -> None:
        target_path = filepath or str(Path(get_doctor_data_dir()) / self.STORE_FILENAME)
        # IMPORTANT: choose the path class from the actual host platform, not mocked os.name.
        # Some tests simulate Windows ACL logic on POSIX; pathlib.WindowsPath cannot be instantiated there.
        self._filepath = WindowsPath(target_path) if sys.platform.startswith("win") else PosixPath(target_path)
        self._lock = threading.RLock()
        self._windows_acl_attempted = False
        self._last_state: Optional[str] = None
        self._encryption_key = (os.getenv("DOCTOR_SECRET_STORE_ENCRYPTION_KEY", "") or "").strip()
        self._encryption_required = _is_truthy(os.getenv("DOCTOR_SECRET_STORE_ENCRYPTION_REQUIRED", "0"))
        self._warn_insecure = _is_truthy(os.getenv("DOCTOR_SECRET_STORE_WARN_INSECURE", "1"))

        if self._encryption_required and not self._encryption_key:
            logger.error("SecretStore encryption required but DOCTOR_SECRET_STORE_ENCRYPTION_KEY is missing")
        elif not self._encryption_key and self._warn_insecure and not SecretStore.WARNED_INSECURE:
            logger.warning("SecretStore is running in plaintext mode (set DOCTOR_SECRET_STORE_ENCRYPTION_KEY to enable encryption-at-rest)")
            SecretStore.WARNED_INSECURE = True

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

    def _harden_windows_acl_best_effort(self) -> None:
        if os.name != "nt" or self._windows_acl_attempted:
            return
        if not _is_truthy(os.getenv("DOCTOR_SECRET_STORE_WINDOWS_ACL_HARDEN", "1")):
            return
        self._windows_acl_attempted = True

        # IMPORTANT: ACL hardening is best-effort only. Do not fail writes if icacls is unavailable.
        icacls = shutil.which("icacls")
        if not icacls:
            logger.warning("SecretStore Windows ACL hardening skipped: icacls not found")
            return

        user = (os.getenv("USERNAME", "") or "").strip()
        if not user:
            logger.warning("SecretStore Windows ACL hardening skipped: USERNAME not set")
            return

        try:
            subprocess.run(
                [icacls, str(self._filepath), "/inheritance:r"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [icacls, str(self._filepath), "/grant:r", f"{user}:(R,W)"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning(f"SecretStore Windows ACL hardening failed: {exc}")

    def _harden_permissions_best_effort(self) -> None:
        self._chmod_0600_best_effort()
        self._harden_windows_acl_best_effort()

    def _derive_keys(self, salt: bytes) -> tuple[bytes, bytes]:
        key_material = hashlib.pbkdf2_hmac(
            "sha256",
            self._encryption_key.encode("utf-8", errors="ignore"),
            salt,
            self.ENC_ITERATIONS,
            dklen=64,
        )
        return key_material[:32], key_material[32:]

    @staticmethod
    def _xor_stream_crypt(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < len(data):
            block = hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
            out.extend(block)
            counter += 1
        stream = bytes(out[: len(data)])
        return bytes(a ^ b for a, b in zip(data, stream))

    def _encrypt_payload(self, data: Dict[str, str]) -> Dict[str, object]:
        if not self._encryption_key:
            raise SecretStoreKeyRequiredError("Encryption key is required for encrypted payload")

        plain = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        salt = secrets.token_bytes(self.ENC_SALT_BYTES)
        nonce = secrets.token_bytes(self.ENC_NONCE_BYTES)
        enc_key, mac_key = self._derive_keys(salt)
        ciphertext = self._xor_stream_crypt(plain, enc_key, nonce)
        # CRITICAL: encrypt first, then MAC nonce + ciphertext before writing.
        mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return {
            "_meta": {
                "type": self.FORMAT_TYPE,
                "version": self.FORMAT_VERSION,
                "encrypted": True,
                "kdf": self.ENC_KDF,
                "cipher": self.ENC_CIPHER,
                "mac": self.ENC_MAC,
                "mac_input": self.ENC_MAC_INPUT,
                "construction": self.ENC_CONSTRUCTION,
                "iterations": self.ENC_ITERATIONS,
                "salt_bytes": self.ENC_SALT_BYTES,
                "nonce_bytes": self.ENC_NONCE_BYTES,
            },
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
            "mac_b64": base64.b64encode(mac).decode("ascii"),
        }

    @classmethod
    def _is_encrypted_payload(cls, payload: Dict[str, object]) -> bool:
        meta = payload.get("_meta")
        return (
            isinstance(meta, dict)
            and meta.get("type") == cls.FORMAT_TYPE
            and bool(meta.get("encrypted"))
            and "ciphertext_b64" in payload
        )

    def _decrypt_payload(self, payload: Dict[str, object]) -> Dict[str, str]:
        if not self._encryption_key:
            raise SecretStoreKeyRequiredError("Encrypted secrets file requires DOCTOR_SECRET_STORE_ENCRYPTION_KEY")
        try:
            salt = base64.b64decode(str(payload.get("salt_b64") or "").encode("ascii"))
            nonce = base64.b64decode(str(payload.get("nonce_b64") or "").encode("ascii"))
            ciphertext = base64.b64decode(str(payload.get("ciphertext_b64") or "").encode("ascii"))
            mac = base64.b64decode(str(payload.get("mac_b64") or "").encode("ascii"))
        except Exception as exc:
            raise SecretStoreError(f"Invalid encrypted payload encoding: {exc}") from exc

        enc_key, mac_key = self._derive_keys(salt)
        expected_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise _SecretStoreAuthenticationError("Encrypted payload MAC verification failed")

        plain = self._xor_stream_crypt(ciphertext, enc_key, nonce)
        try:
            decoded = json.loads(plain.decode("utf-8"))
        except Exception as exc:
            raise SecretStoreError(f"Encrypted payload decode failed: {exc}") from exc

        if not isinstance(decoded, dict):
            raise SecretStoreError("Decrypted payload is not a JSON object")

        out: Dict[str, str] = {}
        for key, value in decoded.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized = key.strip().lower()
                if normalized and value.strip():
                    out[normalized] = value
        return out

    def _normalize_plain_payload(self, payload: Dict[str, object]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key, value in payload.items():
            if key == "_meta":
                continue
            if isinstance(key, str) and isinstance(value, str):
                normalized = key.strip().lower()
                if normalized and value.strip():
                    out[normalized] = value
        return out

    def _load_state(self) -> Tuple[str, Dict[str, str]]:
        """Read the store and classify it; callers must hold ``self._lock``."""
        if not self._filepath.exists():
            return self._note_state(STATE_EMPTY), {}

        try:
            payload = json.loads(self._filepath.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("secrets file is not a JSON object")

            if self._is_encrypted_payload(payload):
                data = self._decrypt_payload(payload)
            else:
                data = self._normalize_plain_payload(payload)
            # Note the state only after decryption succeeded; noting "ok" first made every locked
            # read look like a fresh ok -> locked transition and repeat the error log.
            return self._note_state(STATE_OK), data
        # CRITICAL: an encrypted store that cannot be authenticated must never be rotated or
        # rewritten. A missing key let the next write replace it with plaintext; a wrong key (MAC
        # failure) renamed it aside and started a new store under that key; both destroyed secrets.
        except SecretStoreKeyRequiredError:
            return self._note_state(STATE_LOCKED_KEY_REQUIRED), {}
        except _SecretStoreAuthenticationError:
            return self._note_state(STATE_LOCKED_KEY_MISMATCH), {}
        except Exception:
            # Structural corruption (unparseable before authentication): rotate aside, continue clean.
            self._rotate_corrupt_file()
            return self._note_state(STATE_CORRUPT), {}

    def _rotate_corrupt_file(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = self._filepath.with_name(f"{self._filepath.name}.corrupt-{ts}")
        try:
            self._filepath.rename(backup)
        except Exception:
            return
        logger.warning(f"SecretStore file {self._filepath.name} was unreadable and was moved aside as {backup.name}")

    def _note_state(self, state: str) -> str:
        """Log a locked store once per state change (state name and file name only)."""
        if state != self._last_state and state in LOCKED_STATES:
            logger.error(
                f"SecretStore is locked ({state}): reads return nothing and writes are refused. "
                f"Restore the original DOCTOR_SECRET_STORE_ENCRYPTION_KEY, or move {self._filepath.name} "
                "aside to start a new store."
            )
        self._last_state = state
        return state

    def _load_writable(self) -> Dict[str, str]:
        state, data = self._load_state()
        if state in LOCKED_STATES:
            raise SecretStoreLockedError(state)
        return data

    def get_state(self) -> str:
        """Store state: ok, empty, locked_key_required, locked_key_mismatch or corrupt (just rotated)."""
        with self._lock:
            state, _ = self._load_state()
            return state

    def _save_all(self, data: Dict[str, str]) -> None:
        if self._encryption_required and not self._encryption_key:
            raise SecretStoreKeyRequiredError("Encryption required but DOCTOR_SECRET_STORE_ENCRYPTION_KEY is missing")

        self._ensure_parent()
        tmp = self._filepath.with_suffix(self._filepath.suffix + ".tmp")
        payload: Dict[str, object]
        if self._encryption_key:
            payload = self._encrypt_payload(data)
        else:
            payload = data

        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self._filepath))
        self._harden_permissions_best_effort()

    @staticmethod
    def _normalize_provider_id(provider_id: str) -> str:
        return (provider_id or "").strip().lower()

    def get_secret(self, provider_id: str) -> Optional[str]:
        pid = self._normalize_provider_id(provider_id)
        if not pid:
            return None
        with self._lock:
            return self._load_state()[1].get(pid)

    def set_secret(self, provider_id: str, secret: str) -> None:
        pid = self._normalize_provider_id(provider_id)
        value = (secret or "").strip()
        if not pid:
            raise ValueError("provider_id is required")
        if not value:
            raise ValueError("secret must be non-empty")

        with self._lock:
            data = self._load_writable()
            data[pid] = value
            self._save_all(data)

    def clear_secret(self, provider_id: str) -> bool:
        pid = self._normalize_provider_id(provider_id)
        if not pid:
            return False

        with self._lock:
            data = self._load_writable()
            if pid not in data:
                return False
            data.pop(pid, None)
            self._save_all(data)
            return True

    def clear_all(self) -> int:
        with self._lock:
            data = self._load_writable()
            count = len(data)
            self._save_all({})
            return count

    def get_status(self, providers: Optional[list[str]] = None) -> Dict[str, Dict[str, object]]:
        with self._lock:
            _, data = self._load_state()
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
