"""Secret-store key-state fail-closed behavior.

An encrypted store that cannot be authenticated with the configured key (key missing or wrong) must
never be renamed, overwritten or downgraded: reads return nothing, mutators raise
``SecretStoreLockedError``, and the file bytes and directory listing stay unchanged, so restoring the
original key recovers every secret. Structural corruption still rotates aside; plaintext stores,
migration to encryption and correct-key operations are unchanged.

Each test collects its observations into one dict so a failure shows the complete picture.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, Optional
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import services.secret_store as secret_store_module  # noqa: E402
from services.secret_store import SecretStore  # noqa: E402

KEY_A = "s28-synthetic-store-key-a"  # pragma: allowlist secret
KEY_B = "s28-synthetic-store-key-b"  # pragma: allowlist secret
ORIGINAL = "S28-SYNTHETIC-ORIGINAL-VALUE"  # pragma: allowlist secret
ORIGINAL_GENERIC = "S28-SYNTHETIC-GENERIC-VALUE"  # pragma: allowlist secret
NEW_VALUE = "S28-SYNTHETIC-NEW-VALUE"  # pragma: allowlist secret
LOCKED = "raised SecretStoreLockedError"


@contextlib.contextmanager
def _key_env(key: Optional[str], *, required: bool = False) -> Iterator[None]:
    with patch.dict(
        os.environ,
        {"DOCTOR_SECRET_STORE_WINDOWS_ACL_HARDEN": "0", "DOCTOR_SECRET_STORE_WARN_INSECURE": "0"},
    ):
        os.environ.pop("DOCTOR_SECRET_STORE_ENCRYPTION_KEY", None)
        os.environ.pop("DOCTOR_SECRET_STORE_ENCRYPTION_REQUIRED", None)
        if key:
            os.environ["DOCTOR_SECRET_STORE_ENCRYPTION_KEY"] = key
        if required:
            os.environ["DOCTOR_SECRET_STORE_ENCRYPTION_REQUIRED"] = "1"
        yield


def _encrypted_store(directory: Path) -> Path:
    path = directory / "secrets.json"
    with _key_env(KEY_A):
        store = SecretStore(filepath=str(path))
        store.set_secret("openai", ORIGINAL)
        store.set_secret("generic", ORIGINAL_GENERIC)
    return path


def _snapshot(directory: Path) -> Dict[str, str]:
    return {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in sorted(directory.iterdir())}


def _format(path: Path) -> str:
    if not path.exists():
        return "missing"
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("_meta") if isinstance(payload, dict) else None
    return "encrypted" if isinstance(meta, dict) and meta.get("encrypted") else "plaintext"


def _attempt(operation: Callable[[], object]) -> str:
    try:
        result = operation()
    except Exception as exc:  # noqa: BLE001 - the exception type is the observation
        return f"raised {type(exc).__name__}"
    return f"returned {result!r}"


def _state(store: SecretStore) -> Optional[str]:
    get_state = getattr(store, "get_state", None)
    return get_state() if callable(get_state) else None


def _read_with_key(path: Path, key: str) -> Optional[str]:
    with _key_env(key):
        return SecretStore(filepath=str(path)).get_secret("openai")


def _locked_observations(path: Path, key: Optional[str]) -> Dict[str, object]:
    with _key_env(key):
        store = SecretStore(filepath=str(path))
        observed: Dict[str, object] = {
            "state": _state(store),
            "read": store.get_secret("openai"),
            "configured": sorted(p for p, s in store.get_status().items() if s["configured"]),
            "set_secret": _attempt(lambda: store.set_secret("openai", NEW_VALUE)),
            "clear_secret": _attempt(lambda: store.clear_secret("openai")),
            "clear_all": _attempt(store.clear_all),
            "format_after": _format(path),
        }
    return observed


def test_missing_key_locks_the_encrypted_store_without_rewriting_it(tmp_path):
    path = _encrypted_store(tmp_path)
    before = _snapshot(tmp_path)

    observed = _locked_observations(path, key=None)
    observed["files"] = _snapshot(tmp_path)
    observed["readable_with_original_key"] = _read_with_key(path, KEY_A)

    assert observed == {
        "state": "locked_key_required",
        "read": None,
        "configured": [],
        "set_secret": LOCKED,
        "clear_secret": LOCKED,
        "clear_all": LOCKED,
        "format_after": "encrypted",
        "files": before,
        "readable_with_original_key": ORIGINAL,
    }


def test_wrong_key_locks_the_encrypted_store_without_rotation(tmp_path):
    path = _encrypted_store(tmp_path)
    before = _snapshot(tmp_path)

    observed = _locked_observations(path, key=KEY_B)
    observed["files"] = _snapshot(tmp_path)
    observed["readable_with_original_key"] = _read_with_key(path, KEY_A)

    assert observed == {
        "state": "locked_key_mismatch",
        "read": None,
        "configured": [],
        "set_secret": LOCKED,
        "clear_secret": LOCKED,
        "clear_all": LOCKED,
        "format_after": "encrypted",
        "files": before,
        "readable_with_original_key": ORIGINAL,
    }


def test_wrong_key_reads_alone_never_move_the_store(tmp_path):
    path = _encrypted_store(tmp_path)
    before = _snapshot(tmp_path)

    with _key_env(KEY_B):
        store = SecretStore(filepath=str(path))
        observed = {
            "reads": [store.get_secret("openai"), store.get_secret("generic")],
            "status_configured": [p for p, s in store.get_status().items() if s["configured"]],
        }
    observed["files"] = _snapshot(tmp_path)

    assert observed == {"reads": [None, None], "status_configured": [], "files": before}


def test_locked_state_is_logged_once_without_secret_material(tmp_path, caplog):
    path = _encrypted_store(tmp_path)

    with caplog.at_level(logging.DEBUG, logger=secret_store_module.logger.name):
        with _key_env(KEY_B):
            store = SecretStore(filepath=str(path))
            store.get_secret("openai")
            store.get_secret("generic")

    messages = [record.getMessage() for record in caplog.records]
    locked = [m for m in messages if "locked_key_mismatch" in m]
    assert len(locked) == 1
    assert not [m for m in messages if any(value in m for value in (KEY_A, KEY_B, ORIGINAL, str(tmp_path)))]


def test_structural_corruption_still_rotates_aside(tmp_path):
    path = tmp_path / "secrets.json"
    encrypted = _encrypted_store(tmp_path)
    payload = json.loads(encrypted.read_text(encoding="utf-8"))
    payload["ciphertext_b64"] = "%%% not base64 %%%"
    cases = {"invalid-json": "{not json", "invalid-encoding": json.dumps(payload)}

    observed = {}
    for name, content in cases.items():
        for item in tmp_path.iterdir():
            item.unlink()
        path.write_text(content, encoding="utf-8")
        with _key_env(KEY_A):
            store = SecretStore(filepath=str(path))
            read = store.get_secret("openai")
            state_after = _state(store)
            store.set_secret("openai", NEW_VALUE)
            reread = store.get_secret("openai")
        names = sorted(item.name for item in tmp_path.iterdir())
        observed[name] = {
            "read": read,
            "state_after": state_after,
            "rotated": len([n for n in names if n.startswith("secrets.json.corrupt-")]),
            "reread": reread,
        }

    expected = {"read": None, "state_after": "empty", "rotated": 1, "reread": NEW_VALUE}
    assert observed == {name: expected for name in cases}


def test_plaintext_store_still_migrates_to_encryption_when_a_key_is_set(tmp_path):
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"openai": ORIGINAL}), encoding="utf-8")

    with _key_env(KEY_A):
        store = SecretStore(filepath=str(path))
        observed = {"state": _state(store), "read": store.get_secret("openai")}
        store.set_secret("generic", NEW_VALUE)
        observed["format_after"] = _format(path)
        observed["state_after"] = _state(store)
    observed["readable_with_key"] = _read_with_key(path, KEY_A)

    assert observed == {
        "state": "ok",
        "read": ORIGINAL,
        "format_after": "encrypted",
        "state_after": "ok",
        "readable_with_key": ORIGINAL,
    }


def test_correct_key_and_empty_store_states(tmp_path):
    path = tmp_path / "secrets.json"
    with _key_env(KEY_A):
        store = SecretStore(filepath=str(path))
        observed = {"empty": _state(store)}
        store.set_secret("openai", ORIGINAL)
        observed["after_set"] = _state(store)
        observed["read"] = store.get_secret("openai")
        observed["cleared"] = store.clear_all()
        observed["after_clear"] = _state(store)

    assert observed == {"empty": "empty", "after_set": "ok", "read": ORIGINAL, "cleared": 1, "after_clear": "ok"}


def test_encryption_required_without_key_still_blocks_plaintext_writes(tmp_path):
    path = tmp_path / "secrets.json"
    with _key_env(None, required=True):
        store = SecretStore(filepath=str(path))
        outcome = _attempt(lambda: store.set_secret("openai", NEW_VALUE))

    assert outcome == "raised SecretStoreKeyRequiredError"
    assert not path.exists()
