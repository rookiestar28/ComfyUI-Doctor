"""Unit contracts of server-held LLM credential binding (exact detection, registry-bound release)."""

from __future__ import annotations

from typing import Mapping, Optional

import pytest

pytest.importorskip("aiohttp")

OPENAI = "https://api.openai.com/v1"
OPENAI_KEY = "SYNTH-OPENAI-ENV-KEY"
GENERIC_KEY = "SYNTH-GENERIC-ENV-KEY"
STORE_GENERIC_KEY = "SYNTH-STORE-GENERIC-KEY"


class _FakeStore:
    def __init__(self, secrets: Mapping[str, str]):
        self._secrets = dict(secrets)

    def get_secret(self, provider: str) -> Optional[str]:
        return self._secrets.get(provider)

@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api.openai.com/v1", "openai"),
        ("https://API.OpenAI.com./v1", "openai"),
        ("https://api.anthropic.com", "anthropic"),
        ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini"),
        ("http://localhost:11434", "ollama"),
        ("http://127.0.0.1:1234", "lmstudio"),
        ("https://xapi.openai.com/v1", ""),
        ("https://api.openai.com.evil.test/v1", ""),
        ("https://googleapis.com.corp.test/v1", ""),
        ("https://storage.googleapis.com/v1", ""),
        ("https://evilopenrouter.ai/api/v1", ""),
        ("https://xapi.x.ai/v1", ""),
        ("https://api.openai.com:8443/v1", ""),
        ("http://api.openai.com/v1", ""),
        ("http://0.0.0.0:11434", ""),
        ("not a url", ""),
    ],
)
def test_detect_provider_uses_exact_hosts(base_url, expected):
    from services.llm_keys import detect_provider

    assert detect_provider(base_url) == expected


def test_resolve_api_key_without_an_approved_destination_releases_no_server_key(monkeypatch):
    from services import llm_keys

    monkeypatch.setenv("DOCTOR_OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("DOCTOR_LLM_API_KEY", GENERIC_KEY)
    monkeypatch.setattr(llm_keys, "get_secret_store", lambda: _FakeStore({"generic": STORE_GENERIC_KEY}))
    key, source, _provider, is_local = llm_keys.resolve_api_key(
        base_url="https://unapproved.example.test/v1", provider_hint="openai"
    )
    assert (key, source, is_local) == ("", "none", False)
    key, source, _provider, _ = llm_keys.resolve_api_key(base_url=OPENAI, provider_hint="deepseek")
    assert (key, source) == (OPENAI_KEY, "env")
