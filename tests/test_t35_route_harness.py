"""Characterization tests for the executable route-handler harness.

These tests execute the real PromptServer handlers registered by the real ``__init__.py``. They
pin currently-correct behavior so that later fixes can reproduce and pin handler-level defects; a
test here fails if the harness stops executing real handlers (for example if routes were only
inspected as source text).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import (  # noqa: E402
    PROJECT_ROOT,
    DoctorRouteHarness,
    EgressBlocked,
    ProviderReply,
)

REQUEST_KEY = "SYNTHETIC-REQUEST-KEY"
OPENAI_BASE = "https://api.openai.com/v1"
OLLAMA_BASE = "http://127.0.0.1:11434"
ERROR_CONTEXT = {"error": "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"}


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture(autouse=True)
def _reset_capture(request):
    if "harness" in request.fixturenames:
        active = request.getfixturevalue("harness")
        active.captured.clear()
        active.provider_reply = ProviderReply()
    yield


def _openapi_operations():
    spec = json.loads((PROJECT_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    return sorted(
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "delete", "patch"}
    )


def test_registered_routes_come_from_real_entrypoint_and_match_openapi(harness):
    operations = harness.registered_operations
    assert len(operations) == 34
    assert operations == _openapi_operations()
    assert harness.package_name.startswith("doctor_hostload_")


def test_list_models_rejects_private_base_url_before_any_outbound_call(harness):
    response = harness.request("POST", "/doctor/list_models", json={"base_url": "http://10.0.0.5/v1"})

    assert response.status == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "destination_not_allowed"
    assert body["models"] == []
    assert harness.captured == []


def test_secrets_status_requires_configured_admin_token(harness):
    with harness.patched_env(DOCTOR_ADMIN_TOKEN="SYNTHETIC-ADMIN-TOKEN", DOCTOR_REQUIRE_ADMIN_TOKEN="1"):
        denied = harness.request("GET", "/doctor/secrets/status")
        allowed = harness.request(
            "GET", "/doctor/secrets/status", headers={"X-Doctor-Admin-Token": "SYNTHETIC-ADMIN-TOKEN"}
        )

    assert denied.status == 401
    assert denied.json()["error"] == "unauthorized"
    assert allowed.status == 200
    assert allowed.json()["success"] is True


def test_analyze_executes_handler_and_captures_provider_request(harness):
    response = harness.request(
        "POST",
        "/doctor/analyze",
        json={"error": "RuntimeError: probe", "base_url": OPENAI_BASE, "api_key": REQUEST_KEY, "model": "gpt-test"},
    )

    assert response.status == 200
    assert response.json() == {"analysis": "harness-ok"}
    assert len(harness.captured) == 1
    sent = harness.captured[0]
    assert (sent.method, sent.url) == ("POST", f"{OPENAI_BASE}/chat/completions")
    assert "authorization" in sent.header_names()
    assert sent.header("Authorization") == f"Bearer {REQUEST_KEY}"
    assert sent.json is not None and sent.json["model"] == "gpt-test"


def test_chat_non_stream_with_error_context_reaches_local_ollama_adapter(harness):
    response = harness.request(
        "POST",
        "/doctor/chat",
        json={
            "base_url": OLLAMA_BASE,
            "model": "llama-test",
            "stream": False,
            "messages": [{"role": "user", "content": "Why did this fail?"}],
            "error_context": ERROR_CONTEXT,
        },
    )

    assert response.status == 200
    assert response.json()["content"] == "harness-ok"
    assert [(c.method, c.url) for c in harness.captured] == [("POST", f"{OLLAMA_BASE}/api/chat")]
    assert harness.captured[0].json["model"] == "llama-test"


def test_chat_stream_relays_provider_deltas_as_sse(harness):
    response = harness.request(
        "POST",
        "/doctor/chat",
        json={
            "base_url": OPENAI_BASE,
            "api_key": REQUEST_KEY,
            "model": "gpt-test",
            "stream": True,
            "messages": [{"role": "user", "content": "Why did this fail?"}],
            "error_context": ERROR_CONTEXT,
        },
    )

    assert response.status == 200
    events = [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert {"delta": "harness-ok", "done": False} in events
    assert events[-1]["done"] is True
    assert [(c.method, c.url) for c in harness.captured] == [("POST", f"{OPENAI_BASE}/chat/completions")]
    assert harness.captured[0].header("Authorization") == f"Bearer {REQUEST_KEY}"


def test_verify_key_reports_provider_status(harness):
    ok = harness.request("POST", "/doctor/verify_key", json={"base_url": OPENAI_BASE, "api_key": REQUEST_KEY})
    harness.provider_reply = ProviderReply(status=401, json_body={"error": "bad key"})
    rejected = harness.request("POST", "/doctor/verify_key", json={"base_url": OPENAI_BASE, "api_key": REQUEST_KEY})

    assert ok.status == 200 and ok.json()["success"] is True
    assert rejected.status == 200 and rejected.json()["success"] is False
    assert [(c.method, c.url) for c in harness.captured] == [("GET", f"{OPENAI_BASE}/models")] * 2
    assert all(c.header("Authorization") == f"Bearer {REQUEST_KEY}" for c in harness.captured)


def test_egress_guard_refuses_non_loopback_connects_dns_and_local_llm_ports(harness):
    with pytest.raises(EgressBlocked):
        socket.create_connection(("8.8.8.8", 53), timeout=1)
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("example.com", 80)
    with pytest.raises(EgressBlocked):
        socket.create_connection(("127.0.0.1", 11434), timeout=1)
    assert socket.getaddrinfo("api.openai.com", 443)[0][4][0] == "8.8.4.4"
    assert "dns:example.com" in harness.guard.blocked


def test_harness_writes_doctor_data_only_under_its_temp_root(harness):
    data_dir = Path(harness.module("services.doctor_paths").get_doctor_data_dir())
    assert harness.data_root is not None
    assert data_dir.resolve().is_relative_to(harness.data_root.resolve())
