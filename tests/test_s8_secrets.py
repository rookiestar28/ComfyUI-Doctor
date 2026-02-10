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
from services.admin_guard import validate_admin_request, is_loopback_request


class TestAdminGuard:
    def _mock_request(self, remote="127.0.0.1", headers=None):
        req = MagicMock()
        req.remote = remote
        req.headers = headers or {}
        return req

    def test_loopback_allowed_without_token(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            req = self._mock_request(remote="127.0.0.1")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is True
            assert code == "ok"

    def test_remote_denied_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
            os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
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
            req = self._mock_request(remote="10.0.0.5")
            allowed, code, msg = validate_admin_request(req)
            assert allowed is True

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
