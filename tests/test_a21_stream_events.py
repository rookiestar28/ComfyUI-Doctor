"""The chat stream's ``fix_suggestion`` event is a documented, pinned wire contract.

After a streamed reply finishes, ``/doctor/chat`` writes one extra Server-Sent Event when the full reply
holds a fenced ``json`` block with a valid ``fixes`` list. The shipped sidebar ignores it (it reads only
``delta``, ``done`` and ``error``), but external stream consumers may rely on it, so it is kept, documented
in ``docs/API_REFERENCE.md`` and ``docs/openapi.json``, and pinned here through the real route handler.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness, ProviderReply  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OPENAI_BASE = "https://api.openai.com/v1"
REQUEST_KEY = "SYNTHETIC-REQUEST-KEY"
FIX = {
    "fixes": [
        {"node_id": "3", "widget": "steps", "from": 50, "to": 20, "reason": "Lower the step count to reduce memory use"}
    ]
}
SECOND_FIX = {
    "fixes": [{"node_id": "5", "widget": "cfg", "from": 12, "to": 7, "reason": "A lower guidance scale is more stable"}]
}


def fenced(payload: Any) -> str:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return "```json\n" + body + "\n```"


def provider_stream(*parts: str) -> Tuple[bytes, ...]:
    chunks = [f"data: {json.dumps({'choices': [{'delta': {'content': part}}]})}\n\n".encode("utf-8") for part in parts]
    chunks.append(b"data: [DONE]\n\n")
    return tuple(chunks)


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture(autouse=True)
def _reset_capture(harness):
    harness.captured.clear()
    harness.provider_reply = ProviderReply()
    yield


def chat(harness: DoctorRouteHarness, *parts: str, stream: bool = True, **overrides: Any):
    harness.provider_reply = ProviderReply(stream_chunks=provider_stream(*parts))
    body: Dict[str, Any] = {
        "base_url": OPENAI_BASE,
        "api_key": REQUEST_KEY,
        "model": "gpt-test",
        "stream": stream,
        "messages": [{"role": "user", "content": "Why did this fail?"}],
    }
    body.update(copy.deepcopy(overrides))
    return harness.request("POST", "/doctor/chat", json=body)


def sse_events(text: str) -> List[Dict[str, Any]]:
    return [json.loads(line[len("data: "):]) for line in text.splitlines() if line.startswith("data: ")]


def fix_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [event for event in events if event.get("type") == "fix_suggestion"]


# ------------------------------------------------------------------ the event itself
def test_a_valid_fix_block_adds_one_fix_suggestion_event_after_done(harness):
    reply = "The sampler ran out of memory.\n" + fenced(FIX)
    response = chat(harness, reply[:20], reply[20:])

    assert response.status == 200, response.text
    events = sse_events(response.text)
    fixes = fix_events(events)
    assert fixes == [{"type": "fix_suggestion", "data": FIX}]
    assert set(fixes[0]) == {"type", "data"}
    done_index = max(i for i, event in enumerate(events) if event.get("done") is True)
    assert events.index(fixes[0]) > done_index
    assert events[-1] == fixes[0]
    deltas = [event["delta"] for event in events if event.get("done") is False]
    assert "".join(deltas) == reply


def test_only_the_first_fix_block_is_used(harness):
    response = chat(harness, "First:\n" + fenced(FIX) + "\nSecond:\n" + fenced(SECOND_FIX))

    assert fix_events(sse_events(response.text)) == [{"type": "fix_suggestion", "data": FIX}]


@pytest.mark.parametrize(
    "reply",
    [
        "No structured fix here.",
        fenced({"advice": "no fixes key"}),
        fenced('{"fixes": [oops]}'),
        fenced({"fixes": "not a list"}),
        fenced({"fixes": [{"node_id": "3", "widget": "steps", "from": 50, "to": 20}]}),
        fenced({"fixes": ["not a dict"]}),
    ],
    ids=["no block", "no fixes key", "invalid json", "fixes not a list", "missing reason key", "entry not an object"],
)
def test_no_event_without_a_valid_fix_block(harness, reply):
    response = chat(harness, reply)

    assert response.status == 200, response.text
    events = sse_events(response.text)
    assert fix_events(events) == []
    assert events[-1] == {"delta": "", "done": True}


def test_a_non_streaming_reply_carries_no_fix_suggestion_event(harness):
    harness.provider_reply = ProviderReply(json_body={"choices": [{"message": {"content": fenced(FIX)}}]})
    response = harness.request(
        "POST",
        "/doctor/chat",
        json={
            "base_url": OPENAI_BASE,
            "api_key": REQUEST_KEY,
            "model": "gpt-test",
            "stream": False,
            "messages": [{"role": "user", "content": "Why did this fail?"}],
        },
    )

    assert response.status == 200, response.text
    assert "fix_suggestion" not in response.text
    assert response.json()["content"] == fenced(FIX)


# ------------------------------------------------------------------ the documentation contract
def test_the_event_is_documented_in_the_api_reference():
    text = (ROOT / "docs" / "API_REFERENCE.md").read_text(encoding="utf-8")

    assert "### Chat stream events" in text
    section = text.split("### Chat stream events", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    for needle in ('"delta"', '"done": true', '"error"', '"code"', "fix_suggestion", '"fixes"', "after the `done` event"):
        assert needle in section, needle
    for key in ("node_id", "widget", "from", "to", "reason"):
        assert f"`{key}`" in section, key


def test_the_event_is_documented_in_the_openapi_stream_description():
    spec = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    stream = spec["paths"]["/doctor/chat"]["post"]["responses"]["200"]["content"]["text/event-stream"]
    description = stream["schema"]["description"]

    for needle in ("delta", "done", "error", "fix_suggestion", "fixes"):
        assert needle in description, needle
