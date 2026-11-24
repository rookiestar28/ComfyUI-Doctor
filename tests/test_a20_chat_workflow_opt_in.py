"""The workflow the sidebar sends when the user opts in is sanitized like every other outbound text.

With "Send the workflow with chat questions" on, the sidebar adds the serialized graph (a JSON string) to
``error_context.workflow``. The graph holds prompts, file names and custom-node settings, so a secret in
ANY node, not only the failed one, must be gone from the provider-bound request in every privacy mode a
remote provider can use (``none`` is downgraded to ``basic`` for a non-local destination). With the
setting off the sidebar sends no ``workflow`` key and nothing of the graph reaches the provider.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness, ProviderReply  # noqa: E402

OPENAI_BASE = "https://api.openai.com/v1"
I18N_DIR = Path(__file__).resolve().parents[1] / "i18n_data"
LANGUAGES = ("en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko")
SETTING_STRINGS = ("include_workflow_context_label", "include_workflow_context_hint")
SECRET = "sk-a20SyntheticGraphSecret0123456789abcdefABCDEF"
EMAIL = "a20.synthetic.person@example.com"
BYSTANDER_MARK = "A20-BYSTANDER-CLASS"
ERROR = {
    "error": "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB",
    "traceback": (
        "Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n"
        "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
    ),
    "node_context": {"node_id": "3"},
}


def _graph() -> Dict[str, Any]:
    """The shape ``graph.serialize()`` produces: the failed node is benign, the secret sits in another node."""
    return {
        "nodes": [
            {"id": 3, "type": "KSampler", "inputs": [{"name": "model", "type": "MODEL", "link": 1}],
             "widgets_values": [5, "fixed", 20, 8, "euler", "normal", 1]},
            {"id": 1, "type": "CheckpointLoaderSimple", "inputs": [], "widgets_values": ["m.safetensors"]},
            {"id": 5, "type": BYSTANDER_MARK, "inputs": [],
             "widgets_values": [f"contact {EMAIL} using key {SECRET}"]},
        ],
        "links": [[1, 1, 0, 3, 0, "MODEL"]],
    }


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture(autouse=True)
def _reset_capture(harness):
    harness.captured.clear()
    harness.provider_reply = ProviderReply()
    session_manager = sys.modules[f"{harness.package_name}.session_manager"]
    session_manager.SessionManager._core_limiter = None
    yield


def _chat(harness: DoctorRouteHarness, error_context: Dict[str, Any], **extra: Any):
    body: Dict[str, Any] = {
        "base_url": OPENAI_BASE,
        "api_key": "SYNTHETIC-REQUEST-KEY",
        "model": "gpt-test",
        "stream": False,
        "messages": [{"role": "user", "content": "Why did this fail?"}],
        "error_context": copy.deepcopy(error_context),
    }
    body.update(extra)
    return harness.request("POST", "/doctor/chat", json=body)


def _wire(harness: DoctorRouteHarness) -> str:
    assert len(harness.captured) == 1, [(c.method, c.url) for c in harness.captured]
    assert harness.captured[0].json is not None
    return json.dumps(harness.captured[0].json, ensure_ascii=False)


@pytest.mark.parametrize("privacy_mode", ["basic", "strict", "none"])
def test_a_secret_in_any_node_of_the_opted_in_workflow_never_reaches_a_remote_provider(harness, privacy_mode):
    context = dict(ERROR, workflow=json.dumps(_graph()))

    response = _chat(harness, context, privacy_mode=privacy_mode)

    assert response.status == 200, response.text
    wire = _wire(harness)
    # Positive control: the graph really is in the request, so the absence below is not vacuous.
    assert BYSTANDER_MARK in wire
    assert SECRET not in wire
    assert SECRET[:20] not in wire
    assert EMAIL not in wire


def test_the_secret_is_also_removed_when_the_workflow_arrives_as_a_parsed_object(harness):
    context = dict(ERROR, workflow=_graph())

    response = _chat(harness, context, privacy_mode="basic")

    assert response.status == 200, response.text
    wire = _wire(harness)
    assert BYSTANDER_MARK in wire
    assert SECRET not in wire and EMAIL not in wire


def test_without_the_workflow_key_nothing_of_the_graph_reaches_the_provider(harness):
    # What the sidebar sends while the setting is off (the default).
    response = _chat(harness, dict(ERROR), privacy_mode="basic")

    assert response.status == 200, response.text
    wire = _wire(harness)
    assert BYSTANDER_MARK not in wire
    assert "Workflow (simplified)" not in wire
    assert SECRET not in wire


# ------------------------------------------------------------------ the settings-tab strings
def _ui_text(lang: str) -> Dict[str, str]:
    return json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))["ui_text"]


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("key", SETTING_STRINGS)
def test_the_setting_strings_exist_in_every_language_and_are_translated(lang, key):
    value = _ui_text(lang).get(key)

    assert isinstance(value, str) and value.strip(), (lang, key)
    if lang != "en":
        assert value != _ui_text("en")[key], f"{lang}.{key} is an untranslated copy of the English text"


def test_the_hint_tells_the_user_what_is_sent_and_that_the_default_is_off():
    english = _ui_text("en")["include_workflow_context_hint"]

    for word in ("workflow", "AI provider", "privacy mode", "Off by default"):
        assert word in english, word
