"""Chat R12 token-budget activation (executed through the real route handler).

``api_chat`` builds the R12 budget configuration and applies it before the prompt is built. These
tests pin that the budget runs for remote chat (and for local chat when opted in), reports its
metadata without a failure warning, trims an oversized context along the configured ladder before
prompt construction, never trims the latest user message or the error summary, keeps outbound
sanitization, and is disabled by the ``r12_enabled_remote`` switch.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness  # noqa: E402

OPENAI_BASE = "https://api.openai.com/v1"
OLLAMA_BASE = "http://127.0.0.1:11434"
REQUEST_KEY = "SYNTHETIC-REQUEST-KEY"
TARGET = "30"
ERROR_SUMMARY = "RuntimeError: budget probe failure in sampler"
LATEST_USER = "Why did the sampler fail this time?"
# Small nodes keep the prompt's workflow section (about 2,000 characters) complete and deterministic;
# a long traceback (trimmed only by the last ladder step) keeps the context over the remote hard
# limit, so the ladder must run through the minimal workflow prune (upstream depth 1).
UNTRIMMED_SECTION = [27, 28, 29, 30]
MINIMAL_PRUNE = [29, 30]
FULL_LADDER = ["prune_workflow_std", "prune_workflow_agg", "prune_workflow_min", "drop_system_info", "truncate_traceback"]
FAILURE_MARKERS = ("R12 Budget application failed", "r12_budget_failed")


def _workflow(nodes: int = 40, text: int = 200) -> Dict[str, Any]:
    workflow: Dict[str, Any] = {}
    for index in range(1, nodes + 1):
        inputs: Dict[str, Any] = {"text": f"node-{index}-" + "x" * text}
        if index > 1:
            inputs["prev"] = [str(index - 1), 0]
        workflow[str(index)] = {"class_type": f"BudgetProbe{index:04d}", "inputs": inputs}
    return workflow


def _traceback(frames: int = 400) -> str:
    lines = "\n".join(f'  File "frame_{index}.py", line {index}, in step_{index}' for index in range(frames))
    return f"Traceback (most recent call last):\n{lines}\n{ERROR_SUMMARY}"


def _oversized_context(**extra: Any) -> Dict[str, Any]:
    return {
        "error": ERROR_SUMMARY,
        "traceback": _traceback(),
        "node_context": {"node_id": TARGET},
        "workflow": _workflow(),
        **extra,
    }


def _system_prompt(outbound: Dict[str, Any]) -> str:
    return next(m["content"] for m in outbound["messages"] if m.get("role") == "system")


def _section(outbound: Dict[str, Any], title: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(title)}\n(.*?)(?=^## |\Z)", _system_prompt(outbound))
    assert match, f"prompt section {title!r} missing"
    return match.group(1)


def _workflow_section_ids(outbound: Dict[str, Any]) -> List[int]:
    return sorted({int(found) for found in re.findall(r"BudgetProbe(\d{4})", _section(outbound, "Workflow Context"))})


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    def failures(self) -> List[str]:
        return [m for m in self.messages if any(marker in m for marker in FAILURE_MARKERS)]


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture
def config(harness):
    return harness.module("config").CONFIG


@pytest.fixture
def chat(harness, monkeypatch):
    # tiktoken is optional and not a dependency: pin the fallback estimator for exact sizing.
    monkeypatch.setattr(harness.module("services.token_estimator"), "TIKTOKEN_AVAILABLE", False)
    records = _Records()
    api_logger = logging.getLogger("ComfyUI-Doctor-API")  # attach inside the harness (it swaps handlers)
    api_logger.addHandler(records)

    def run(
        *,
        stream: bool = False,
        base_url: str = OPENAI_BASE,
        error_context: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, str]]] = None,
    ):
        harness.captured.clear()
        body: Dict[str, Any] = {
            "base_url": base_url,
            "model": "budget-test",
            "stream": stream,
            "messages": messages or [{"role": "user", "content": LATEST_USER}],
            "error_context": error_context if error_context is not None else {"error": ERROR_SUMMARY},
        }
        if base_url == OPENAI_BASE:
            body["api_key"] = REQUEST_KEY
        response = harness.request("POST", "/doctor/chat", json=body)
        assert response.status == 200, response.text
        assert len(harness.captured) == 1
        if stream:
            events = [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]
            meta = next((event["data"] for event in events if event.get("type") == "usage_metadata"), None)
        else:
            meta = response.json().get("metadata")
        return meta, harness.captured[0].json

    run.records = records  # type: ignore[attr-defined]
    try:
        yield run
    finally:
        api_logger.removeHandler(records)


@pytest.mark.parametrize("stream", [False, True], ids=["json", "sse"])
def test_remote_chat_reports_budget_metadata_without_failure_warning(chat, stream):
    meta, _ = chat(stream=stream)

    assert meta, "expected R12 budget metadata"
    assert meta["token_budget"]["enabled"] is True
    assert meta["token_budget"]["provider_type"] == "remote"
    assert meta["token_budget"]["estimator_method"] == "fallback"
    assert meta["trim"]["steps"] == []
    assert chat.records.failures() == []


@pytest.mark.parametrize("as_text", [False, True], ids=["dict-workflow", "json-string-workflow"])
def test_oversized_context_is_trimmed_before_the_prompt_is_built(chat, as_text):
    context = _oversized_context()
    if as_text:
        context["workflow"] = json.dumps(context["workflow"])

    meta, outbound = chat(error_context=context)

    assert meta and meta["pruning"]["applied"] is True
    assert [step.split("(")[0] for step in meta["trim"]["steps"]] == FULL_LADDER
    assert meta["token_budget"]["estimated_tokens_initial"] > meta["token_budget"]["hard_max_tokens"]
    assert meta["token_budget"]["estimated_tokens_final"] <= meta["token_budget"]["hard_max_tokens"]
    assert meta["pruning"]["kept_nodes"] == ["29", "30"]
    # The prompt is built from the trimmed context (untrimmed, the section shows nodes 27-30).
    assert _workflow_section_ids(outbound) == MINIMAL_PRUNE
    assert "frame_200.py" not in _system_prompt(outbound)
    assert chat.records.failures() == []


def test_trimming_never_removes_the_latest_user_message_or_error_summary(chat):
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": LATEST_USER},
    ]

    meta, outbound = chat(error_context=_oversized_context(), messages=history)

    assert meta and meta["trim"]["degraded"] is True
    assert [step.split("(")[0] for step in meta["trim"]["steps"]][-1] == "truncate_traceback"
    assert outbound["messages"][1:] == history
    assert ERROR_SUMMARY in _section(outbound, "Error Summary")


def test_budgeted_context_is_still_sanitized(chat):
    error = r"RuntimeError: cannot open C:\Users\alice\ComfyUI\models\x.safetensors"
    # The final traceback line survives truncation and feeds the prompt's error sections.
    traceback = _traceback().replace(ERROR_SUMMARY, error)

    meta, outbound = chat(error_context=_oversized_context(error=error, traceback=traceback))

    assert meta and meta["pruning"]["applied"] is True
    prompt = _system_prompt(outbound)
    assert "alice" not in prompt
    assert "<USER_PATH>" in prompt


def test_remote_switch_off_disables_the_budget(chat, config, monkeypatch):
    monkeypatch.setattr(config, "r12_enabled_remote", False)

    meta, outbound = chat(error_context=_oversized_context())

    assert not meta
    assert _workflow_section_ids(outbound) == UNTRIMMED_SECTION
    assert chat.records.failures() == []


def test_local_chat_is_budgeted_only_when_opted_in(chat, config, monkeypatch):
    meta, _ = chat(base_url=OLLAMA_BASE)
    assert not meta
    assert chat.records.failures() == []

    monkeypatch.setattr(config, "r12_enabled_local", True)
    meta, _ = chat(base_url=OLLAMA_BASE)
    assert meta, "expected R12 budget metadata for opted-in local chat"
    assert meta["token_budget"]["provider_type"] == "local"
    assert meta["token_budget"]["soft_max_tokens"] == config.r12_soft_max_tokens_local
    assert meta["trim"]["final_policy"] == "local_soft"
    assert chat.records.failures() == []
