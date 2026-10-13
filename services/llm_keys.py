"""
LLM API key resolution helpers.

Resolution precedence:
1) request-provided key
2) provider-specific ENV
3) generic ENV
4) server secret store (provider)
5) server secret store (generic)

Server-held credentials (2-5) are bound to approved destinations (see ``resolve_api_key``); the
caller's provider hint never selects or widens them.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, Iterator, Optional, Tuple

from .outbound_policy import (
    ENV_DOCTOR_LLM_BASE_URL,
    KIND_LOCAL,
    KIND_OFFICIAL,
    KIND_OPERATOR,
    Destination,
    canonicalize_base_url,
    get_destination_registry,
)
from .secret_store import get_secret_store

logger = logging.getLogger(__name__)

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
    """Return the provider hint, else the provider of an official/local destination with exactly
    this scheme, host and port ("" otherwise). No substring or suffix host matching."""
    hinted = normalize_provider_id(provider_hint)
    if hinted:
        return hinted

    canonical = canonicalize_base_url(base_url)
    if canonical is None:
        return ""
    for entry in get_destination_registry().entries:
        if entry.kind in (KIND_OFFICIAL, KIND_LOCAL) and (entry.scheme, entry.host, entry.port) == (
            canonical.scheme,
            canonical.host,
            canonical.port,
        ):
            return entry.provider
    return ""


def get_env_api_key(provider: str) -> Optional[str]:
    normalized = normalize_provider_id(provider)
    specific_keys = PROVIDER_ENV_KEYS.get(normalized, ())
    specific = _first_non_empty_env(specific_keys)
    if specific:
        return specific
    return _first_non_empty_env(GENERIC_ENV_KEYS)


def _is_local_destination(destination: Optional[Destination], hint: str) -> bool:
    if destination is None:
        return False
    if destination.provider in LOCAL_PROVIDERS:
        return True
    # A hint may mark an operator destination as a keyless local-style server (it never releases a
    # credential); official provider destinations always require a key.
    return destination.kind != KIND_OFFICIAL and hint in LOCAL_PROVIDERS


def _bound_server_credentials(destination: Optional[Destination]) -> Iterator[Tuple[Optional[str], str]]:
    """Yield (credential, source) candidates bound to the destination, in precedence order.

    CRITICAL: decided from the approved registry entry only. Caller-controlled labels (the request's
    provider hint) must never select or widen server-held credentials: a hint used to send one
    provider's key to another provider, to local services and to connectivity-only gateways.
    """
    if destination is None or destination.provider in LOCAL_PROVIDERS:
        return
    if destination.kind == KIND_OFFICIAL:
        yield _first_non_empty_env(PROVIDER_ENV_KEYS.get(destination.provider, ())), "env"
        yield _first_non_empty_env(GENERIC_ENV_KEYS), "env"
        store = get_secret_store()  # only opened when no environment key applies (as before)
        yield store.get_secret(destination.provider), "server_store"
        yield store.get_secret("generic"), "server_store"
    elif destination.kind == KIND_OPERATOR and destination.source == ENV_DOCTOR_LLM_BASE_URL:
        # The operator's default base URL is paired with the generic (default) key only.
        yield _first_non_empty_env(GENERIC_ENV_KEYS), "env"
        yield get_secret_store().get_secret("generic"), "server_store"


def resolve_api_key(
    *,
    base_url: str,
    provider_hint: Optional[str] = None,
    request_api_key: Optional[str] = None,
    destination: Optional[Destination] = None,
) -> Tuple[str, str, str, bool]:
    """
    Returns: (api_key, source, provider, is_local)
    source: request|env|server_store|none

    ``destination`` is the approved registry entry for the request; when omitted, ``base_url`` is
    matched against the registry. Without an approved destination only a request key is returned.
    """
    if destination is None:
        destination = get_destination_registry().match(base_url)
    hint = normalize_provider_id(provider_hint)
    provider = destination.provider if destination is not None else ""
    is_local = _is_local_destination(destination, hint)

    req_key = (request_api_key or "").strip()
    if req_key:
        return req_key, "request", provider, is_local

    for credential, source in _bound_server_credentials(destination):
        if credential:
            return credential, source, provider, is_local

    if not is_local:
        logger.warning(
            "No LLM credential available for destination %s (server-held keys are bound to official "
            "providers and the DOCTOR_LLM_BASE_URL destination)",
            destination.destination_id if destination is not None else "(not approved)",
        )
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
