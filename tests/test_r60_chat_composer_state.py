"""Chat handler composer-state regression tests (executed through the real route handler).

``api_chat`` reads its PromptComposer success flag after every intent branch. These tests pin that
chat without a captured error and ``intent=explain_node`` succeed with exactly one provider request,
that the environment block reaches the outbound system prompt exactly once, and that the working
error-context prompt structures stay unchanged.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness, ProviderReply  # noqa: E402

OPENAI_BASE = "https://api.openai.com/v1"
REQUEST_KEY = "SYNTHETIC-REQUEST-KEY"
ENV_MARKER = "HarnessOS"  # OS string of the harness's synthetic environment snapshot
LEGACY_ENV_HEADER = "=== System Environment ==="
COMPOSER_ENV_HEADER = "## System Environment"
ERROR = {
    "error": "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB",
    "traceback": (
        "Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n"
        "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
    ),
}
ERROR_WITH_WORKFLOW = {
    **ERROR,
    "node_context": {"node_id": "3"},
    "workflow": {"3": {"class_type": "KSampler", "inputs": {}}},
}
ANALYSIS_HEADERS = [
    "**YOUR TASK**: Identify the ROOT CAUSE and suggest fixes that will PREVENT THE CRASH.",
    "**Response Language**: English",
    "**Error Categories**:",
    "**Analysis Steps**:",
    "**Fix Format** (if applicable):",
    "**Remember**: Focus on CRASH PREVENTION, not quality improvement.",
]
# Pre-fix structure snapshots (captured on the unchanged base through this harness).
LEGACY_FALLBACK_HEADERS = ANALYSIS_HEADERS + [
    "**ERROR CONTEXT**:",
    "**ERROR CATEGORY** (auto-detected):",
    LEGACY_ENV_HEADER,
]
COMPOSER_HEADERS = ANALYSIS_HEADERS + [
    "## Error Summary",
    "## Failed Node",
    "## Traceback",
    "## Recent Logs",
    "## Workflow Context",
    COMPOSER_ENV_HEADER,
    "**ERROR CATEGORY** (auto-detected):",
]


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture(autouse=True)
def _reset_capture(harness):
    harness.captured.clear()
    harness.provider_reply = ProviderReply()
    yield


def _chat(harness: DoctorRouteHarness, **overrides: Any):
    body: Dict[str, Any] = {
        "base_url": OPENAI_BASE,
        "api_key": REQUEST_KEY,
        "model": "gpt-test",
        "stream": False,
        "messages": [{"role": "user", "content": "Why did this fail?"}],
    }
    body.update(copy.deepcopy(overrides))
    return harness.request("POST", "/doctor/chat", json=body)


def _system_prompt(harness: DoctorRouteHarness) -> str:
    assert len(harness.captured) == 1, [(c.method, c.url) for c in harness.captured]
    sent = harness.captured[0]
    assert (sent.method, sent.url) == ("POST", f"{OPENAI_BASE}/chat/completions")
    assert sent.json is not None
    first = sent.json["messages"][0]
    assert first["role"] == "system"
    return str(first["content"])


def _headers(prompt: str) -> List[str]:
    return [
        line.strip()
        for line in prompt.splitlines()
        if line.strip().startswith(("**", "## ", "=== ", "### "))
    ]


def _sse_events(text: str) -> List[Dict[str, Any]]:
    return [json.loads(line[len("data: "):]) for line in text.splitlines() if line.startswith("data: ")]


def _assert_single_legacy_env_block(prompt: str) -> None:
    assert prompt.count(LEGACY_ENV_HEADER) == 1
    assert prompt.count(COMPOSER_ENV_HEADER) == 0
    assert prompt.count(ENV_MARKER) == 1


@pytest.mark.parametrize("error_context", [None, {}], ids=["omitted", "empty"])
def test_no_error_non_stream_chat_returns_content_with_one_env_block(harness, error_context):
    overrides = {} if error_context is None else {"error_context": error_context}
    response = _chat(harness, **overrides)

    assert response.status == 200, response.text
    assert response.json()["content"] == "harness-ok"
    prompt = _system_prompt(harness)
    assert prompt.startswith("You are an expert ComfyUI debugger.")
    _assert_single_legacy_env_block(prompt)


def test_no_error_stream_chat_relays_deltas_with_one_env_block(harness):
    response = _chat(harness, stream=True)

    assert response.status == 200, response.text
    events = _sse_events(response.text)
    assert {"delta": "harness-ok", "done": False} in events
    assert events[-1]["done"] is True
    assert not [event for event in events if event.get("error")]
    _assert_single_legacy_env_block(_system_prompt(harness))


def test_explain_node_with_error_context_uses_node_prompt_with_one_env_block(harness):
    response = _chat(
        harness,
        intent="explain_node",
        selected_nodes=[{"id": 3, "type": "KSampler"}],
        error_context=ERROR,
    )

    assert response.status == 200, response.text
    assert response.json()["content"] == "harness-ok"
    prompt = _system_prompt(harness)
    assert prompt.startswith("You are an expert ComfyUI node documentation assistant.")
    assert "**Selected Node(s):**" in prompt
    assert "**ERROR CONTEXT**:" not in prompt
    _assert_single_legacy_env_block(prompt)


def test_error_context_without_workflow_keeps_legacy_fallback_structure(harness):
    response = _chat(harness, error_context=ERROR)

    assert response.status == 200, response.text
    prompt = _system_prompt(harness)
    assert _headers(prompt) == LEGACY_FALLBACK_HEADERS
    _assert_single_legacy_env_block(prompt)


def test_error_context_with_workflow_keeps_composer_structure_without_duplicate_env(harness):
    response = _chat(harness, error_context=ERROR_WITH_WORKFLOW)

    assert response.status == 200, response.text
    prompt = _system_prompt(harness)
    assert _headers(prompt) == COMPOSER_HEADERS
    assert prompt.count(COMPOSER_ENV_HEADER) == 1
    assert prompt.count(LEGACY_ENV_HEADER) == 0
    assert prompt.count(ENV_MARKER) == 1
