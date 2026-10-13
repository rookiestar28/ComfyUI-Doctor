"""Server-held LLM credentials are released only to the approved destination they are bound to.

Executed through the real route handlers (T35 harness) with synthetic keys; captured provider
requests are never sent anywhere. The caller's ``provider`` hint must never choose or widen a
server-held credential.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness  # noqa: E402

LLM_ROUTES = ("/doctor/analyze", "/doctor/chat", "/doctor/verify_key", "/doctor/list_models")
ENVELOPE_ROUTES = ("/doctor/verify_key", "/doctor/list_models")

OPENAI = "https://api.openai.com/v1"
DEEPSEEK = "https://api.deepseek.com/v1"
GATEWAY = "https://gateway.example.test/v1"            # DOCTOR_LLM_ALLOWED_BASE_URLS (connectivity only)
LOOKALIKE = "https://googleapis.com.corp.test/v1"      # operator-approved look-alike host
DEFAULT_GATEWAY = "https://default-gw.example.test/v1"  # DOCTOR_LLM_BASE_URL (default URL + key pair)
OLLAMA = "http://127.0.0.1:11434"
LMSTUDIO = "http://127.0.0.1:1234/v1"

OPENAI_KEY = "SYNTH-OPENAI-ENV-KEY"
DEEPSEEK_KEY = "SYNTH-DEEPSEEK-ENV-KEY"
GEMINI_KEY = "SYNTH-GEMINI-ENV-KEY"
GENERIC_KEY = "SYNTH-GENERIC-ENV-KEY"
REQUEST_KEY = "SYNTH-REQUEST-KEY"
STORE_OPENAI_KEY = "SYNTH-STORE-OPENAI-KEY"
STORE_GENERIC_KEY = "SYNTH-STORE-GENERIC-KEY"

DESTINATIONS = {
    "DOCTOR_LLM_ALLOWED_BASE_URLS": f"{GATEWAY},{LOOKALIKE}",
    "DOCTOR_LLM_BASE_URL": DEFAULT_GATEWAY,
}
ALL_ENV_KEYS = {
    "DOCTOR_OPENAI_API_KEY": OPENAI_KEY,
    "DOCTOR_DEEPSEEK_API_KEY": DEEPSEEK_KEY,
    "DOCTOR_GEMINI_API_KEY": GEMINI_KEY,
    "DOCTOR_LLM_API_KEY": GENERIC_KEY,
}
SYNTHETIC_VALUES = (
    OPENAI_KEY, DEEPSEEK_KEY, GEMINI_KEY, GENERIC_KEY, REQUEST_KEY, STORE_OPENAI_KEY, STORE_GENERIC_KEY,
)


class _FakeStore:
    def __init__(self, secrets: Mapping[str, str]):
        self._secrets = dict(secrets)

    def get_secret(self, provider: str) -> Optional[str]:
        return self._secrets.get(provider)


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _start(env: Mapping[str, str], store: Mapping[str, str]) -> DoctorRouteHarness:
    active = DoctorRouteHarness(env={**DESTINATIONS, **env}).__enter__()
    active.module("session_manager").SessionManager.configure_limits(
        core_rate_limit=100_000, light_rate_limit=100_000
    )
    active.module("services.llm_keys").get_secret_store = lambda: _FakeStore(store)
    return active


@pytest.fixture(scope="module")
def run():
    """Yield a function that executes one LLM route call; harnesses are reused per env/store."""

    current: Dict[str, Any] = {"key": None, "harness": None}

    def _close() -> None:
        if current["harness"] is not None:
            current["harness"].__exit__(None, None, None)
            current.update(key=None, harness=None)

    def _run(path: str, base_url: str, *, env: Mapping[str, str], store: Optional[Mapping[str, str]] = None,
             hint: str = "", api_key: Optional[str] = None) -> Dict[str, Any]:
        key = (tuple(sorted(env.items())), tuple(sorted((store or {}).items())))
        if current["key"] != key:
            _close()
            current.update(key=key, harness=_start(env, store or {}))
        active: DoctorRouteHarness = current["harness"]
        active.captured.clear()
        body: Dict[str, Any] = {"base_url": base_url, "model": "gpt-test", "provider": hint}
        if api_key is not None:
            body["api_key"] = api_key
        if path == "/doctor/analyze":
            body["error"] = "RuntimeError: probe"
        if path == "/doctor/chat":
            body.update({"stream": False, "messages": [{"role": "user", "content": "Why?"}]})
        response = active.request("POST", path, json=body)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        credentials = [
            value
            for captured in active.captured
            for value in (captured.header("Authorization"), captured.header("x-api-key"))
            if value
        ]
        return {
            "status": response.status,
            "error": payload.get("error") if isinstance(payload, dict) else None,
            "outbound": len(active.captured),
            "credentials": credentials,
        }

    yield _run
    _close()


def _leaked(result: Dict[str, Any], *values: str) -> List[str]:
    return [c for c in result["credentials"] if any(v in c for v in values)]


def _assert_withheld(path: str, result: Dict[str, Any]) -> None:
    assert result["error"] == "missing_api_key", result
    assert result["outbound"] == 0, result
    assert result["status"] == (200 if path in ENVELOPE_ROUTES else 401), result


@pytest.mark.parametrize("path", LLM_ROUTES)
def test_hint_cannot_send_another_providers_key_to_an_official_destination(run, path):
    # E1: hint "deepseek" + OpenAI destination must release the OpenAI-bound key, never DeepSeek's.
    result = run(path, OPENAI, env=ALL_ENV_KEYS, hint="deepseek")
    assert _leaked(result, DEEPSEEK_KEY) == []
    assert result["credentials"] and all(OPENAI_KEY in c for c in result["credentials"]), result


@pytest.mark.parametrize("path", LLM_ROUTES)
@pytest.mark.parametrize(("base_url", "hint"), [(OLLAMA, "openai"), (LMSTUDIO, "lmstudio"), (LMSTUDIO, "")])
def test_local_destinations_never_receive_server_held_keys(run, path, base_url, hint):
    # E2: local services stay keyless whatever the hint says.
    result = run(path, base_url, env=ALL_ENV_KEYS, hint=hint)
    assert _leaked(result, *SYNTHETIC_VALUES) == [], result
    assert result["error"] != "missing_api_key", result


@pytest.mark.parametrize("path", LLM_ROUTES)
@pytest.mark.parametrize("hint", ["openai", "", "gemini"])
def test_connectivity_only_operator_entries_receive_no_server_held_key(run, path, hint):
    # E3: DOCTOR_LLM_ALLOWED_BASE_URLS approves connectivity, not the server's credentials.
    result = run(path, GATEWAY, env=ALL_ENV_KEYS, hint=hint)
    assert _leaked(result, *SYNTHETIC_VALUES) == [], result
    _assert_withheld(path, result)


@pytest.mark.parametrize("path", LLM_ROUTES)
def test_operator_lookalike_host_never_receives_a_provider_key(run, path):
    # E4: substring detection used to map googleapis.com.<x> to the Gemini key.
    result = run(path, LOOKALIKE, env={"DOCTOR_GEMINI_API_KEY": GEMINI_KEY})
    assert _leaked(result, GEMINI_KEY) == [], result
    _assert_withheld(path, result)


@pytest.mark.parametrize("path", LLM_ROUTES)
def test_local_hint_cannot_make_an_official_destination_keyless(run, path):
    # E5: hint "ollama" used to flip is_local and send a placeholder to the official provider.
    result = run(path, OPENAI, env={"DOCTOR_DEEPSEEK_API_KEY": DEEPSEEK_KEY}, hint="ollama")
    _assert_withheld(path, result)


@pytest.mark.parametrize("path", LLM_ROUTES)
@pytest.mark.parametrize("hint", ["", "openai"])
def test_default_base_url_entry_receives_only_the_generic_key(run, path, hint):
    result = run(path, DEFAULT_GATEWAY, env=ALL_ENV_KEYS, hint=hint)
    assert result["credentials"] and all(GENERIC_KEY in c for c in result["credentials"]), result
    assert _leaked(result, OPENAI_KEY, DEEPSEEK_KEY, GEMINI_KEY) == []


@pytest.mark.parametrize("path", LLM_ROUTES)
def test_generic_key_still_reaches_official_providers(run, path):
    result = run(path, DEEPSEEK, env={"DOCTOR_LLM_API_KEY": GENERIC_KEY})
    assert result["credentials"] and all(GENERIC_KEY in c for c in result["credentials"]), result


@pytest.mark.parametrize("path", LLM_ROUTES)
def test_request_keys_reach_any_approved_destination(run, path):
    result = run(path, GATEWAY, env=ALL_ENV_KEYS, hint="openai", api_key=REQUEST_KEY)
    assert result["credentials"] and all(REQUEST_KEY in c for c in result["credentials"]), result
    assert _leaked(result, OPENAI_KEY, GENERIC_KEY) == []


@pytest.mark.parametrize("path", LLM_ROUTES)
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (OPENAI, STORE_OPENAI_KEY),
        (DEEPSEEK, STORE_GENERIC_KEY),
        (DEFAULT_GATEWAY, STORE_GENERIC_KEY),
        (GATEWAY, None),
        (OLLAMA, None),
    ],
)
def test_server_store_keys_follow_the_same_binding(run, path, base_url, expected):
    store = {"openai": STORE_OPENAI_KEY, "generic": STORE_GENERIC_KEY}
    result = run(path, base_url, env={}, store=store, hint="openai")
    if expected is None:
        assert _leaked(result, STORE_OPENAI_KEY, STORE_GENERIC_KEY) == [], result
    else:
        assert result["credentials"] and all(expected in c for c in result["credentials"]), result


def test_withheld_credentials_are_not_logged(run):
    handler = _RecordingHandler()
    loggers = [logging.getLogger(), logging.getLogger("ComfyUI-Doctor-API")]
    for logger in loggers:
        logger.addHandler(handler)
    try:
        for path in LLM_ROUTES:
            run(path, GATEWAY, env=ALL_ENV_KEYS, hint="openai")
            run(path, OPENAI, env=ALL_ENV_KEYS, hint="deepseek")
    finally:
        for logger in loggers:
            logger.removeHandler(handler)
    assert handler.messages, "expected route logs"
    assert [m for m in handler.messages if any(v in m for v in SYNTHETIC_VALUES)] == []
