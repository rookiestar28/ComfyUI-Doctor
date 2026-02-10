"""
LLM API key resolution helpers.

Resolution precedence:
1) request-provided key
2) provider-specific ENV
3) generic ENV
4) server secret store (provider)
5) server secret store (generic)
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional, Tuple

from .secret_store import get_secret_store

try:
    from ..security import is_local_llm_url, parse_base_url
except Exception:
    from security import is_local_llm_url, parse_base_url


LOCAL_PROVIDERS = {"ollama", "lmstudio"}

PROVIDER_ENV_KEYS: Dict[str, tuple[str, ...]] = {
    "openai": ("DOCTOR_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "anthropic": ("DOCTOR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "deepseek": ("DOCTOR_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
    "groq": ("DOCTOR_GROQ_API_KEY", "GROQ_API_KEY"),
    "gemini": ("DOCTOR_GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "xai": ("DOCTOR_XAI_API_KEY", "XAI_API_KEY"),
    "openrouter": ("DOCTOR_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
}

GENERIC_ENV_KEYS: tuple[str, ...] = (
    "DOCTOR_LLM_API_KEY",
)


def _first_non_empty_env(candidates: Iterable[str]) -> Optional[str]:
    for key in candidates:
        value = os.getenv(key, "")
        if value and value.strip():
            return value.strip()
    return None


def normalize_provider_id(provider: Optional[str]) -> str:
    return (provider or "").strip().lower()


def detect_provider(base_url: str, provider_hint: Optional[str] = None) -> str:
    hinted = normalize_provider_id(provider_hint)
    if hinted:
        return hinted

    info = parse_base_url(base_url or "")
    if not info:
        return ""

    host = (info.get("hostname") or "").lower()
    port = info.get("port")

    if port == 11434 and host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return "ollama"
    if port == 1234 and host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return "lmstudio"
    if host.endswith("api.openai.com"):
        return "openai"
    if host.endswith("api.anthropic.com"):
        return "anthropic"
    if host.endswith("api.deepseek.com"):
        return "deepseek"
    if host.endswith("api.groq.com"):
        return "groq"
    if host.endswith("openrouter.ai"):
        return "openrouter"
    if host.endswith("api.x.ai"):
        return "xai"
    if "googleapis.com" in host:
        return "gemini"
    return ""


def get_env_api_key(provider: str) -> Optional[str]:
    normalized = normalize_provider_id(provider)
    specific_keys = PROVIDER_ENV_KEYS.get(normalized, ())
    specific = _first_non_empty_env(specific_keys)
    if specific:
        return specific
    return _first_non_empty_env(GENERIC_ENV_KEYS)


def resolve_api_key(
    *,
    base_url: str,
    provider_hint: Optional[str] = None,
    request_api_key: Optional[str] = None,
) -> Tuple[str, str, str, bool]:
    """
    Returns: (api_key, source, provider, is_local_provider)
    source: request|env|server_store|none
    """
    provider = detect_provider(base_url=base_url, provider_hint=provider_hint)
    is_local = is_local_llm_url(base_url) or provider in LOCAL_PROVIDERS

    req_key = (request_api_key or "").strip()
    if req_key:
        return req_key, "request", provider, is_local

    env_key = get_env_api_key(provider)
    if env_key:
        return env_key, "env", provider, is_local

    store = get_secret_store()
    if provider:
        store_key = store.get_secret(provider)
        if store_key:
            return store_key, "server_store", provider, is_local

    generic_key = store.get_secret("generic")
    if generic_key:
        return generic_key, "server_store", provider, is_local

    return "", "none", provider, is_local


def get_provider_status() -> Dict[str, Dict[str, object]]:
    """
    Returns provider status map for UI:
    configured/source with precedence env > server_store > none.
    """
    providers = ["openai", "anthropic", "deepseek", "groq", "gemini", "xai", "openrouter", "generic"]
    store = get_secret_store()
    output: Dict[str, Dict[str, object]] = {}

    for provider in providers:
        env_key = get_env_api_key(provider)
        if env_key:
            output[provider] = {"configured": True, "source": "env"}
            continue
        store_key = store.get_secret(provider)
        if store_key:
            output[provider] = {"configured": True, "source": "server_store"}
            continue
        output[provider] = {"configured": False, "source": "none"}

    return output
