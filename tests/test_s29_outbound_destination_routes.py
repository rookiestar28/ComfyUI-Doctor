"""Outbound destination policy through the real LLM route handlers.

Every case executes the PromptServer handlers registered by the real ``__init__.py`` (T35 harness)
with synthetic keys, a fake DNS table and a loopback-only egress guard. A caller can only select an
operator-approved destination; outbound URLs are built from the approved entry, and failures never
reflect upstream bodies, resolved addresses or raw exception text.
"""

from __future__ import annotations

import http.server
import json
import socket
import threading
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness, ProviderReply  # noqa: E402

REQUEST_KEY = "SYNTHETIC-REQUEST-KEY"
SERVER_KEY = "SYNTHETIC-SERVER-OPENAI-KEY"
UPSTREAM_MARKER = "SYNTHETIC-UPSTREAM-BODY-7f3a"
LLM_ROUTES = ("/doctor/analyze", "/doctor/chat", "/doctor/verify_key", "/doctor/list_models")

# Intake gaps G1-G5 plus parser-differential forms; none may reach the network or DNS.
REJECTED_BASE_URLS = [
    pytest.param("https://api.openai.com/v1/files?", id="G1-path-query-on-provider-host"),
    pytest.param("https://public.probe.test/any/path#", id="G2-arbitrary-public-host"),
    pytest.param("http://100.100.100.200/latest/meta-data?", id="G3-cgnat-metadata"),
    pytest.param("http://127.0.0.1:11434/api/pull?", id="G4-local-llm-path-control"),
    pytest.param("http://intranet.probe.test/v1", id="G5-internal-name"),
    pytest.param("https://user@api.openai.com/v1", id="userinfo"),
    pytest.param("https://api.openai.com:8443/v1", id="alternate-port"),
    pytest.param("http://api.openai.com/v1", id="scheme-change"),
    pytest.param("https://api.openai.com/v1#frag", id="fragment"),
    pytest.param("https://api.openai.com\\@public.probe.test/v1", id="backslash-authority"),
    pytest.param("https://api.openai.com%2f@public.probe.test/v1", id="encoded-authority"),
    pytest.param("https://api.openai.com/v1 ", id="trailing-whitespace"),
    pytest.param("https://api.openai.com/v1/../v2", id="dot-segment"),
    pytest.param("http://0.0.0.0:11434", id="unspecified-host"),
    pytest.param("http://2130706433:1234/v1", id="numeric-host"),
    pytest.param("ftp://api.openai.com/v1", id="non-http-scheme"),
    pytest.param("", id="empty"),
]


def _body(path: str, base_url: Any, **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {"base_url": base_url, "api_key": REQUEST_KEY, "model": "gpt-test"}
    if path == "/doctor/analyze":
        body["error"] = "RuntimeError: probe"
    if path == "/doctor/chat":
        body.update({"stream": False, "messages": [{"role": "user", "content": "Why?"}]})
    body.update(extra)
    return body


def _error_code(response) -> Optional[str]:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload.get("error") if isinstance(payload, dict) else None


def _unlimited(active: DoctorRouteHarness) -> DoctorRouteHarness:
    # The R7 limiters (10 req/min on verify_key/list_models) are not under test here.
    active.module("session_manager").SessionManager.configure_limits(
        core_rate_limit=100_000, light_rate_limit=100_000
    )
    return active


@pytest.fixture(scope="module")
def harness() -> Iterator[DoctorRouteHarness]:
    with DoctorRouteHarness() as active:
        yield _unlimited(active)


@pytest.fixture(autouse=True)
def _reset(request):
    if "harness" in request.fixturenames:
        active = request.getfixturevalue("harness")
        active.captured.clear()
        active.guard.lookups.clear()
        active.provider_reply = ProviderReply()
    yield


@pytest.mark.parametrize("path", LLM_ROUTES)
@pytest.mark.parametrize("base_url", REJECTED_BASE_URLS)
def test_unapproved_destination_is_rejected_without_outbound_call_or_dns(harness, path, base_url):
    response = harness.request("POST", path, json=_body(path, base_url))

    assert _error_code(response) == "destination_not_allowed", response.text
    assert response.status == (403 if path in ("/doctor/analyze", "/doctor/chat") else 200)
    assert harness.captured == []
    assert harness.guard.lookups == []
    # The fixed message never echoes the caller URL (no oracle, no reflection).
    if base_url:
        assert str(base_url).strip() not in response.text


@pytest.mark.parametrize(
    "base_url, expected_models_url",
    [
        ("https://api.openai.com/v1", "https://api.openai.com/v1/models"),
        ("https://api.openai.com", "https://api.openai.com/v1/models"),
        ("HTTPS://API.OPENAI.COM./v1/", "https://api.openai.com/v1/models"),
        ("https://api.anthropic.com", "https://api.anthropic.com/v1/models"),
        ("https://api.anthropic.com/v1", "https://api.anthropic.com/v1/models"),
        ("https://api.deepseek.com/v1", "https://api.deepseek.com/v1/models"),
        ("https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1/models"),
        ("https://generativelanguage.googleapis.com/v1beta/openai", "https://generativelanguage.googleapis.com/v1beta/openai/models"),
        ("https://api.x.ai/v1", "https://api.x.ai/v1/models"),
        ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1/models"),
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434/api/tags"),
        ("http://localhost:11434/v1", "http://localhost:11434/api/tags"),
        ("http://localhost:1234/v1", "http://localhost:1234/v1/models"),
        ("http://127.0.0.1:1234", "http://127.0.0.1:1234/v1/models"),
    ],
)
def test_builtin_destinations_build_outbound_url_from_the_canonical_entry(harness, base_url, expected_models_url):
    response = harness.request("POST", "/doctor/list_models", json=_body("/doctor/list_models", base_url))

    assert response.status == 200, response.text
    assert response.json()["success"] is True, response.text
    assert [(c.method, c.url) for c in harness.captured] == [("GET", expected_models_url)]


def test_default_chat_flow_reaches_official_provider_once(harness):
    response = harness.request("POST", "/doctor/chat", json=_body("/doctor/chat", "https://api.openai.com/v1"))

    assert response.status == 200, response.text
    assert response.json()["content"] == "harness-ok"
    assert [(c.method, c.url) for c in harness.captured] == [("POST", "https://api.openai.com/v1/chat/completions")]


def test_analyze_and_stream_chat_reach_local_ollama_with_fixed_suffix(harness):
    analyze = harness.request("POST", "/doctor/analyze", json=_body("/doctor/analyze", "http://127.0.0.1:11434"))
    stream = harness.request(
        "POST", "/doctor/chat", json=_body("/doctor/chat", "http://localhost:11434", stream=True)
    )

    assert analyze.status == 200, analyze.text
    assert stream.status == 200, stream.text
    assert [(c.method, c.url) for c in harness.captured] == [
        ("POST", "http://127.0.0.1:11434/api/chat"),
        ("POST", "http://localhost:11434/api/chat"),
    ]


@pytest.mark.parametrize(
    "path, reply",
    [
        ("/doctor/verify_key", ProviderReply(status=401, json_body={"error": UPSTREAM_MARKER})),
        ("/doctor/list_models", ProviderReply(status=500, json_body={"error": UPSTREAM_MARKER})),
        ("/doctor/analyze", ProviderReply(status=500, json_body={"error": UPSTREAM_MARKER})),
        ("/doctor/chat", ProviderReply(status=400, json_body={"error": UPSTREAM_MARKER})),
    ],
)
def test_upstream_error_bodies_are_never_reflected(harness, path, reply):
    harness.provider_reply = reply
    response = harness.request("POST", path, json=_body(path, "https://api.openai.com/v1"))

    assert len(harness.captured) == 1
    payload = response.json()
    assert payload.get("success") is not True
    assert UPSTREAM_MARKER not in response.text
    assert str(reply.status) in json.dumps(payload)


def test_stream_chat_upstream_error_is_not_reflected(harness):
    harness.provider_reply = ProviderReply(status=400, json_body={"error": UPSTREAM_MARKER})
    response = harness.request(
        "POST", "/doctor/chat", json=_body("/doctor/chat", "https://api.openai.com/v1", stream=True)
    )

    assert response.status == 200
    assert UPSTREAM_MARKER not in response.text
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events and events[-1]["done"] is True and events[-1].get("error")


def test_operator_environment_entries_are_approved_exactly():
    env = {
        "OLLAMA_BASE_URL": "http://192.168.1.50:11434",
        "LMSTUDIO_BASE_URL": "http://lmstudio.lan.test:1234/v1",
        "DOCTOR_LLM_BASE_URL": "https://gateway.example.test/v1",
        "DOCTOR_LLM_ALLOWED_BASE_URLS": "https://azure.example.test/openai/v1, http://10.0.0.7:8080/v1",
    }
    cases: List[Tuple[str, str]] = [
        ("http://192.168.1.50:11434", "http://192.168.1.50:11434/api/tags"),
        ("http://lmstudio.lan.test:1234/v1", "http://lmstudio.lan.test:1234/v1/models"),
        ("https://gateway.example.test/v1", "https://gateway.example.test/v1/models"),
        ("https://azure.example.test/openai/v1", "https://azure.example.test/openai/v1/models"),
        ("http://10.0.0.7:8080/v1", "http://10.0.0.7:8080/v1/models"),
    ]
    with DoctorRouteHarness(env=env) as active:
        _unlimited(active)
        for base_url, expected in cases:
            active.captured.clear()
            response = active.request("POST", "/doctor/list_models", json=_body("/doctor/list_models", base_url))
            assert response.json()["success"] is True, (base_url, response.text)
            assert [(c.method, c.url) for c in active.captured] == [("GET", expected)]

        # Exact match only: a different path or port on an approved operator host is refused.
        for base_url in ("https://gateway.example.test/v2", "http://10.0.0.7:8081/v1", "http://10.0.0.7:8080"):
            active.captured.clear()
            response = active.request("POST", "/doctor/verify_key", json=_body("/doctor/verify_key", base_url))
            assert _error_code(response) == "destination_not_allowed", base_url
            assert active.captured == []


def test_no_route_or_request_field_can_change_the_registry(harness):
    registry = harness.module("services.outbound_policy").get_destination_registry()
    before = registry.snapshot()
    tampering = {
        "base_url": "https://public.probe.test/v1",
        "allowed_base_urls": "https://public.probe.test/v1",
        "DOCTOR_LLM_ALLOWED_BASE_URLS": "https://public.probe.test/v1",
        "destination": {"host": "public.probe.test"},
        "settings": {"Doctor.LLM.BaseUrl": "https://public.probe.test/v1"},
    }
    for method, path in harness.registered_operations:
        concrete = path.replace("{job_id}", "job-1").replace("{provider_id}", "openai")
        harness.request(method, concrete, json=tampering if method == "POST" else None)

    assert harness.module("services.outbound_policy").get_destination_registry().snapshot() == before
    assert harness.module("services.outbound_policy").get_destination_registry() is registry
    response = harness.request("POST", "/doctor/list_models", json=_body("/doctor/list_models", "https://public.probe.test/v1"))
    assert _error_code(response) == "destination_not_allowed"


class _CaptureServer:
    """Threaded loopback HTTP server that records every request it receives."""

    def __init__(self) -> None:
        hits: List[Dict[str, str]] = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server API
                hits.append({"path": self.path, "authorization": self.headers.get("Authorization", "")})
                body = b'{"data": [{"id": "internal-only"}]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                return None

        self.hits = hits
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_CaptureServer":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()


def _verify_with_real_session(active: DoctorRouteHarness, base_url: str) -> Tuple[int, str]:
    session_manager = active.module("session_manager").SessionManager

    async def scenario(client):
        try:
            response = await client.post("/doctor/verify_key", json=_body("/doctor/verify_key", base_url))
            return response.status, await response.text()
        finally:
            await session_manager.close()
            session_manager.reset()

    return active.run(scenario)


def test_dns_rebinding_never_reaches_loopback_with_the_real_session():
    with _CaptureServer() as capture:
        host = "rebind.s29.test"
        base_url = f"http://{host}:{capture.port}/v1"
        env = {"DOCTOR_LLM_ALLOWED_BASE_URLS": base_url, "OPENAI_API_KEY": SERVER_KEY}
        # First answer public (pre-flight check), every later answer loopback (connect time).
        sequences = {host: [("8.8.4.4",), ("127.0.0.1",)]}
        with DoctorRouteHarness(env=env, dns_sequences=sequences, real_session=True) as active:
            status, text = _verify_with_real_session(active, base_url)

    assert capture.hits == []
    assert "internal-only" not in text
    assert "127.0.0.1" not in text
    assert status == 200 and json.loads(text)["success"] is False


def test_connect_time_loopback_answer_for_operator_name_is_a_policy_refusal():
    with _CaptureServer() as capture:
        host = "loopback-alias.s29.test"
        base_url = f"http://{host}:{capture.port}/v1"
        env = {"DOCTOR_LLM_ALLOWED_BASE_URLS": base_url, "OPENAI_API_KEY": SERVER_KEY}
        with DoctorRouteHarness(env=env, dns_table={host: ("127.0.0.1",)}, real_session=True) as active:
            status, text = _verify_with_real_session(active, base_url)

    assert capture.hits == []
    assert status == 200
    assert json.loads(text)["error"] == "destination_not_allowed"
    assert "127.0.0.1" not in text


def test_connection_failure_message_is_fixed():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()
    base_url = f"http://127.0.0.1:{closed_port}/v1"
    env = {"DOCTOR_LLM_ALLOWED_BASE_URLS": base_url}
    with DoctorRouteHarness(env=env, real_session=True) as active:
        status, text = _verify_with_real_session(active, base_url)

    payload = json.loads(text)
    assert status == 200 and payload["success"] is False
    assert payload["error"] == "connection_error"
    assert str(closed_port) not in text
    assert "127.0.0.1" not in text
