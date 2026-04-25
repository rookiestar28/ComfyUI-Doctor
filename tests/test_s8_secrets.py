"""
S8: Unit tests for secret_store, llm_keys, and admin_guard.
"""

import json
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# SecretStore
# ---------------------------------------------------------------------------
from services.secret_store import SecretStore


class TestSecretStore:
    """Test file-based SecretStore."""

    def _make_store(self, tmp_path):
        return SecretStore(filepath=str(tmp_path / "secrets.json"))

    def test_set_and_get(self, tmp_path):
        store = self._make_store(tmp_path)
        store.set_secret("openai", "sk-test123")
        assert store.get_secret("openai") == "sk-test123"

    def test_get_missing_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.get_secret("nonexistent") is None

    def test_clear_secret(self, tmp_path):
        store = self._make_store(tmp_path)
        store.set_secret("openai", "sk-test")
        assert store.clear_secret("openai") is True
        assert store.get_secret("openai") is None

    def test_clear_missing_returns_false(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.clear_secret("nonexistent") is False

    def test_clear_all(self, tmp_path):
        store = self._make_store(tmp_path)
        store.set_secret("openai", "a")
        store.set_secret("anthropic", "b")
        store.clear_all()
        assert store.get_secret("openai") is None
        assert store.get_secret("anthropic") is None

    def test_persistence_across_instances(self, tmp_path):
        fp = str(tmp_path / "secrets.json")
        store1 = SecretStore(filepath=fp)
        store1.set_secret("deepseek", "sk-ds")
        store2 = SecretStore(filepath=fp)
        assert store2.get_secret("deepseek") == "sk-ds"

    def test_get_status_never_leaks_values(self, tmp_path):
        store = self._make_store(tmp_path)
        store.set_secret("openai", "sk-secret-value")
        status = store.get_status()
        assert "openai" in status
        # Must never contain the actual key value
        assert "sk-secret-value" not in json.dumps(status)

    def test_corrupted_file_recovery(self, tmp_path):
        fp = tmp_path / "secrets.json"
        fp.write_text("NOT-JSON!!!", encoding="utf-8")
        store = SecretStore(filepath=str(fp))
        # Should recover gracefully and start fresh
        assert store.get_secret("openai") is None
        store.set_secret("openai", "recovered")
        assert store.get_secret("openai") == "recovered"

    def test_thread_safety(self, tmp_path):
        store = self._make_store(tmp_path)
        errors = []

        def writer(provider, key):
            try:
                for _ in range(50):
                    store.set_secret(provider, key)
                    store.get_secret(provider)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"p{i}", f"k{i}"))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Thread safety error: {errors}"

    def test_encryption_roundtrip_no_plaintext(self, tmp_path):
        with patch.dict(os.environ, {"DOCTOR_SECRET_STORE_ENCRYPTION_KEY": "unit-test-secret-store-key"}, clear=False):  # pragma: allowlist secret
            store = self._make_store(tmp_path)
            store.set_secret("openai", "sk-sensitive-value")  # pragma: allowlist secret
            raw = Path(store.filepath).read_text(encoding="utf-8")
            assert "sk-sensitive-value" not in raw
            payload = json.loads(raw)
            assert payload.get("_meta", {}).get("encrypted") is True
            assert payload.get("_meta", {}).get("kdf") == "pbkdf2_hmac_sha256"
            assert payload.get("_meta", {}).get("cipher") == "hmac_sha256_xor_stream"
            assert payload.get("_meta", {}).get("mac") == "hmac_sha256"
            assert payload.get("_meta", {}).get("mac_input") == "nonce+ciphertext"
            assert payload.get("_meta", {}).get("construction") == "encrypt_then_mac"
            assert store.get_secret("openai") == "sk-sensitive-value"

    def test_encrypted_payload_with_legacy_metadata_remains_readable(self, tmp_path):
        with patch.dict(os.environ, {"DOCTOR_SECRET_STORE_ENCRYPTION_KEY": "unit-test-secret-store-key"}, clear=False):  # pragma: allowlist secret
            store = self._make_store(tmp_path)
            store.set_secret("openai", "sk-sensitive-value")  # pragma: allowlist secret
            fp = Path(store.filepath)
            payload = json.loads(fp.read_text(encoding="utf-8"))
            meta = payload.get("_meta", {})
            for key in ("cipher", "mac", "mac_input", "construction", "salt_bytes", "nonce_bytes"):
                meta.pop(key, None)
            fp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            assert store.get_secret("openai") == "sk-sensitive-value"

    def test_encryption_required_without_key_blocks_write(self, tmp_path):
        with patch.dict(os.environ, {"DOCTOR_SECRET_STORE_ENCRYPTION_REQUIRED": "1"}, clear=False):
            os.environ.pop("DOCTOR_SECRET_STORE_ENCRYPTION_KEY", None)
            store = self._make_store(tmp_path)
            with pytest.raises(RuntimeError):
                store.set_secret("openai", "sk-test")

    def test_plaintext_load_then_migrate_to_encrypted(self, tmp_path):
        fp = tmp_path / "secrets.json"
        fp.write_text(json.dumps({"openai": "sk-legacy"}, ensure_ascii=False), encoding="utf-8")  # pragma: allowlist secret

        with patch.dict(os.environ, {"DOCTOR_SECRET_STORE_ENCRYPTION_KEY": "unit-test-secret-store-key"}, clear=False):  # pragma: allowlist secret
            store = SecretStore(filepath=str(fp))
            # Backward-compatible read from legacy plaintext file.
            assert store.get_secret("openai") == "sk-legacy"
            # Next write should persist encrypted format.
            store.set_secret("anthropic", "sk-new")
            raw = fp.read_text(encoding="utf-8")
            assert "sk-legacy" not in raw
            assert "sk-new" not in raw
            payload = json.loads(raw)
            assert payload.get("_meta", {}).get("encrypted") is True

    def test_windows_acl_hardening_attempted_once(self, tmp_path):
        with patch("services.secret_store.os.name", "nt"), \
             patch("services.secret_store.shutil.which", return_value="icacls"), \
             patch("services.secret_store.subprocess.run") as mock_run, \
             patch.dict(os.environ, {"USERNAME": "tester", "DOCTOR_SECRET_STORE_WINDOWS_ACL_HARDEN": "1"}, clear=False):
            store = self._make_store(tmp_path)
            store.set_secret("openai", "sk-test")
            first_calls = mock_run.call_count
            assert first_calls >= 2
            store.set_secret("openai", "sk-test-2")
            # ACL hardening should not rerun for every save in one store instance.
            assert mock_run.call_count == first_calls


# ---------------------------------------------------------------------------
# llm_keys
# ---------------------------------------------------------------------------
from services.llm_keys import detect_provider, resolve_api_key, get_provider_status


class TestDetectProvider:
    def test_openai_url(self):
        assert detect_provider("https://api.openai.com/v1") == "openai"

    def test_anthropic_url(self):
        assert detect_provider("https://api.anthropic.com/v1") == "anthropic"

    def test_deepseek_url(self):
        assert detect_provider("https://api.deepseek.com/v1") == "deepseek"

    def test_ollama_url(self):
        assert detect_provider("http://localhost:11434") == "ollama"

    def test_lmstudio_url(self):
        assert detect_provider("http://127.0.0.1:1234") == "lmstudio"

    def test_provider_hint_takes_precedence(self):
        assert detect_provider("https://api.openai.com/v1", provider_hint="custom") == "custom"

    def test_unknown_url(self):
        assert detect_provider("https://my-proxy.example.com/v1") == ""


class TestResolveApiKey:
    def test_request_key_takes_precedence(self, tmp_path):
        with patch("services.llm_keys.get_secret_store") as mock_store:
            mock_store.return_value = SecretStore(filepath=str(tmp_path / "s.json"))
            key, source, provider, is_local = resolve_api_key(
                base_url="https://api.openai.com/v1",
                request_api_key="sk-request"
            )
            assert key == "sk-request"
            assert source == "request"

    def test_env_fallback(self, tmp_path):
        with patch("services.llm_keys.get_secret_store") as mock_store, \
             patch.dict(os.environ, {"DOCTOR_OPENAI_API_KEY": "sk-env"}, clear=False):
            mock_store.return_value = SecretStore(filepath=str(tmp_path / "s.json"))
            key, source, provider, is_local = resolve_api_key(
                base_url="https://api.openai.com/v1"
            )
            assert key == "sk-env"
            assert source == "env"

    def test_store_fallback(self, tmp_path):
        store = SecretStore(filepath=str(tmp_path / "s.json"))
        store.set_secret("openai", "sk-stored")
        with patch("services.llm_keys.get_secret_store", return_value=store), \
             patch.dict(os.environ, {}, clear=False):
            # Ensure no env vars interfere
            for k in list(os.environ):
                if "DOCTOR_" in k or "OPENAI_API_KEY" in k:
                    os.environ.pop(k, None)
            key, source, provider, is_local = resolve_api_key(
                base_url="https://api.openai.com/v1"
            )
            assert key == "sk-stored"
            assert source == "server_store"

    def test_none_when_no_key(self, tmp_path):
        store = SecretStore(filepath=str(tmp_path / "s.json"))
        with patch("services.llm_keys.get_secret_store", return_value=store), \
             patch.dict(os.environ, {}, clear=False):
            for k in list(os.environ):
                if "DOCTOR_" in k or "OPENAI_API_KEY" in k:
                    os.environ.pop(k, None)
            key, source, provider, is_local = resolve_api_key(
                base_url="https://api.openai.com/v1"
            )
            assert key == ""
            assert source == "none"

    def test_local_provider_detection(self, tmp_path):
        with patch("services.llm_keys.get_secret_store") as mock_store:
            mock_store.return_value = SecretStore(filepath=str(tmp_path / "s.json"))
            _, _, provider, is_local = resolve_api_key(
                base_url="http://localhost:11434",
                request_api_key="dummy"
            )
            assert provider == "ollama"
            assert is_local is True


class TestGetProviderStatus:
    def test_returns_all_providers(self, tmp_path):
        store = SecretStore(filepath=str(tmp_path / "s.json"))
        with patch("services.llm_keys.get_secret_store", return_value=store):
            status = get_provider_status()
            expected = {"openai", "anthropic", "deepseek", "groq", "gemini", "xai", "openrouter", "generic"}
            assert set(status.keys()) == expected

    def test_env_source_detected(self, tmp_path):
        store = SecretStore(filepath=str(tmp_path / "s.json"))
        with patch("services.llm_keys.get_secret_store", return_value=store), \
             patch.dict(os.environ, {"DOCTOR_OPENAI_API_KEY": "sk-env"}, clear=False):
            status = get_provider_status()
            assert status["openai"]["source"] == "env"
            assert status["openai"]["configured"] is True

    def test_store_source_detected(self, tmp_path):
        store = SecretStore(filepath=str(tmp_path / "s.json"))
        store.set_secret("anthropic", "sk-stored")
        with patch("services.llm_keys.get_secret_store", return_value=store), \
             patch.dict(os.environ, {}, clear=False):
            for k in list(os.environ):
                if "DOCTOR_ANTHROPIC" in k or "ANTHROPIC_API_KEY" in k:
                    os.environ.pop(k, None)
            status = get_provider_status()
            assert status["anthropic"]["source"] == "server_store"


# ---------------------------------------------------------------------------
# admin_guard
# ---------------------------------------------------------------------------
from services.admin_guard import get_admin_guard_startup_warning, is_loopback_request, validate_admin_request


class TestAdminGuard:
    def _mock_request(self, remote="127.0.0.1", headers=None):
        req = MagicMock()
        req.remote = remote
        req.headers = headers or {}
        return req

    def test_loopback_allowed_without_token(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            os.environ.pop("DOCTOR_REQUIRE_ADMIN_TOKEN", None)
            req = self._mock_request(remote="127.0.0.1")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is True
            assert code == "ok"

    def test_loopback_denied_when_token_required_without_configured_token(self):
        with patch.dict(os.environ, {"DOCTOR_REQUIRE_ADMIN_TOKEN": "1"}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            req = self._mock_request(remote="127.0.0.1")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is False
            assert code == "unauthorized"
            assert "DOCTOR_ADMIN_TOKEN" in msg

    def test_remote_denied_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
            os.environ.pop("DOCTOR_REQUIRE_ADMIN_TOKEN", None)
            req = self._mock_request(remote="192.168.1.100")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is False
            assert code == "remote_admin_denied"

    def test_token_auth_success(self):
        with patch.dict(os.environ, {"DOCTOR_ADMIN_TOKEN": "my-secret-token"}, clear=False):
            req = self._mock_request(
                remote="192.168.1.100",
                headers={"X-Doctor-Admin-Token": "my-secret-token"}
            )
            allowed, code, msg = validate_admin_request(req)
            assert allowed is True

    def test_token_auth_failure(self):
        with patch.dict(os.environ, {"DOCTOR_ADMIN_TOKEN": "correct"}, clear=False):
            req = self._mock_request(
                remote="127.0.0.1",
                headers={"X-Doctor-Admin-Token": "wrong"}
            )
            allowed, code, msg = validate_admin_request(req)
            assert allowed is False
            assert code == "unauthorized"

    def test_remote_allowed_with_opt_in(self):
        with patch.dict(os.environ, {"DOCTOR_ALLOW_REMOTE_ADMIN": "1"}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            os.environ.pop("DOCTOR_REQUIRE_ADMIN_TOKEN", None)
            req = self._mock_request(remote="10.0.0.5")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is True

    def test_remote_opt_in_denied_when_token_required_without_configured_token(self):
        with patch.dict(
            os.environ,
            {"DOCTOR_ALLOW_REMOTE_ADMIN": "1", "DOCTOR_REQUIRE_ADMIN_TOKEN": "1"},
            clear=False,
        ):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            req = self._mock_request(remote="10.0.0.5")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is False
            assert code == "unauthorized"

    def test_startup_warning_describes_loopback_convenience_mode(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            os.environ.pop("DOCTOR_REQUIRE_ADMIN_TOKEN", None)
            warning = get_admin_guard_startup_warning()
            assert "loopback convenience mode is active" in warning
            assert "Any local process" in warning

    def test_startup_warning_describes_fail_closed_missing_token(self):
        with patch.dict(os.environ, {"DOCTOR_REQUIRE_ADMIN_TOKEN": "1"}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            warning = get_admin_guard_startup_warning()
            assert "fail closed" in warning
            assert "DOCTOR_ADMIN_TOKEN is not configured" in warning

    def test_startup_warning_empty_when_token_configured(self):
        with patch.dict(os.environ, {"DOCTOR_ADMIN_TOKEN": "configured"}, clear=False):
            assert get_admin_guard_startup_warning() == ""

    def test_payload_admin_token(self):
        with patch.dict(os.environ, {"DOCTOR_ADMIN_TOKEN": "body-tok"}, clear=False):
            req = self._mock_request(remote="10.0.0.1", headers={})
            allowed, code, msg = validate_admin_request(req, payload={"admin_token": "body-tok"})
            assert allowed is True

    def test_is_loopback_ipv6(self):
        req = self._mock_request(remote="::1")
        assert is_loopback_request(req) is True

    def test_is_not_loopback(self):
        req = self._mock_request(remote="8.8.8.8")
        assert is_loopback_request(req) is False
