"""Chat error-context collection across workflow shapes (executed through the real route handler).

The sidebar can send a workflow either as the host's serialized graph (``{"nodes": [...], "links":
[...]}`` with ``inputs`` as a list of slot dicts) or as an API-format prompt (``{"<id>": {"class_type":
..., "inputs": {...}}}``), as a dict or as a JSON string, and the string may arrive cut short. None of
those shapes may turn the chat into HTTP 500, and the failed node must be found whenever it is in the
workflow. A chat with an error but without a usable failed node still uses the PromptComposer context.
"""

from __future__ import annotations

import copy
import json
import sys
import types
from typing import Any, Dict, Optional

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness, ProviderReply  # noqa: E402

OPENAI_BASE = "https://api.openai.com/v1"
SECRET = "sk-r71SyntheticWidgetSecret0123456789abcdefABCDEF"  # pragma: allowlist secret
ERROR = {
    "error": "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB",
    "traceback": (
        "Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n"
        "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
    ),
}
COMPOSER_MARK = "## Error Summary"
LEGACY_MARK = "**ERROR CONTEXT**:"
FOUND_MARK = "Node Class: KSampler"
COMPOSER_ENV = "## System Environment"
LEGACY_ENV = "=== System Environment ==="


def _ui_workflow(sampler_id: Any) -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "id": sampler_id, "type": "KSampler",
                "inputs": [{"name": "model", "type": "MODEL", "link": 1}],
                "widgets_values": [5, "fixed", 20, 8, "euler", "normal", 1, SECRET],
            },
            {"id": 1, "type": "CheckpointLoaderSimple", "inputs": [], "widgets_values": ["m.safetensors"]},
        ],
        "links": [[1, 1, 0, sampler_id, 0, "MODEL"]],
    }


def _api_workflow(sampler_id: Any) -> Dict[str, Any]:
    return {
        str(sampler_id): {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 5, "note": SECRET}},
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m.safetensors"}},
    }


SHAPES = {
    "ui_string": lambda sid: json.dumps(_ui_workflow(sid)),
    "ui_dict": lambda sid: _ui_workflow(sid),
    "api_dict": lambda sid: _api_workflow(sid),
    "api_string": lambda sid: json.dumps(_api_workflow(sid)),
    "cut_short_string": lambda sid: json.dumps(_ui_workflow(sid))[:90],
    "malformed_string": lambda sid: "{this is not json",
    "absent": lambda sid: None,
}
READABLE = {"ui_string", "ui_dict", "api_dict", "api_string"}

# (id of the sampler inside the workflow, node_context sent by the sidebar, can the node be found?)
NODES = {
    "present": (3, {"node_id": "3"}, True),
    "absent": (3, {"node_id": "99"}, False),
    "no_id": (3, {}, False),
    "opaque_id": ("node-a", {"node_id": "node-a"}, True),
    "lineage_id": (3, {"node_id": "12:3", "display_node": "12:3"}, True),
}


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


@pytest.fixture(autouse=True)
def _reset_capture(harness):
    harness.captured.clear()
    harness.provider_reply = ProviderReply()
    # The matrix sends more requests than the heavy-endpoint limiter allows per minute (30); every case
    # starts with a fresh limiter so a 429 can never masquerade as a shape failure.
    session_manager = sys.modules[f"{harness.package_name}.session_manager"]
    session_manager.SessionManager._core_limiter = None
    yield


def _chat(harness: DoctorRouteHarness, error_context: Dict[str, Any], **extra: Any):
    body: Dict[str, Any] = {
        "base_url": OPENAI_BASE,
        "api_key": "SYNTHETIC-REQUEST-KEY",  # pragma: allowlist secret
        "model": "gpt-test",
        "stream": False,
        "messages": [{"role": "user", "content": "Why did this fail?"}],
        "error_context": copy.deepcopy(error_context),
    }
    body.update(extra)
    return harness.request("POST", "/doctor/chat", json=body)


def _sent(harness: DoctorRouteHarness) -> tuple[str, str]:
    assert len(harness.captured) == 1, [(c.method, c.url) for c in harness.captured]
    request_json = harness.captured[0].json
    assert request_json is not None
    return str(request_json["messages"][0]["content"]), json.dumps(request_json, ensure_ascii=False)


def _context(shape: str, node: str) -> tuple[Dict[str, Any], bool]:
    sampler_id, node_context, findable = NODES[node]
    context: Dict[str, Any] = dict(ERROR, node_context=node_context)
    workflow = SHAPES[shape](sampler_id)
    if workflow is not None:
        context["workflow"] = workflow
    return context, findable and shape in READABLE


@pytest.mark.parametrize("node", list(NODES))
@pytest.mark.parametrize("shape", list(SHAPES))
def test_every_workflow_shape_answers_200_with_one_request_and_the_composer_context(harness, shape, node):
    context, found = _context(shape, node)

    response = _chat(harness, context)

    assert response.status == 200, response.text
    prompt, _ = _sent(harness)
    # The composer context is used whether or not a failed node was found.
    assert COMPOSER_MARK in prompt
    assert LEGACY_MARK not in prompt
    assert prompt.count(COMPOSER_ENV) == 1
    assert prompt.count(LEGACY_ENV) == 0
    # The failed-node details appear exactly when the node is in a readable workflow.
    assert (FOUND_MARK in prompt) is found


def test_a_null_node_context_still_uses_the_composer_context(harness):
    response = _chat(harness, dict(ERROR, node_context=None, workflow=SHAPES["api_dict"](3)))

    assert response.status == 200, response.text
    prompt, _ = _sent(harness)
    assert COMPOSER_MARK in prompt
    assert LEGACY_MARK not in prompt
    assert FOUND_MARK not in prompt


@pytest.mark.parametrize("privacy_mode", ["basic", "strict"])
@pytest.mark.parametrize("shape", sorted(READABLE))
def test_a_secret_in_a_failed_node_value_never_reaches_the_provider(harness, shape, privacy_mode):
    context, found = _context(shape, "present")
    assert found

    response = _chat(harness, context, privacy_mode=privacy_mode)

    assert response.status == 200, response.text
    prompt, wire = _sent(harness)
    assert FOUND_MARK in prompt
    assert SECRET not in wire
    assert SECRET[:20] not in wire


@pytest.mark.parametrize("shape", ["ui_string", "api_dict"])
def test_the_legacy_format_switch_still_selects_the_legacy_prompt(harness, shape, monkeypatch):
    # The harness imports the package under a synthetic name, so the route's CONFIG is reached through it.
    config_module = sys.modules[f"{harness.package_name}.config"]
    context, _ = _context(shape, "present")
    monkeypatch.setattr(config_module.CONFIG, "r14_use_prompt_composer", False)

    response = _chat(harness, context)

    assert response.status == 200, response.text
    prompt, _ = _sent(harness)
    assert LEGACY_MARK in prompt
    assert COMPOSER_MARK not in prompt
    assert prompt.count(LEGACY_ENV) == 1


def test_analyze_never_fails_on_a_ui_workflow_that_contains_the_failed_node(harness):
    body = {
        "base_url": OPENAI_BASE,
        "api_key": "SYNTHETIC-REQUEST-KEY",  # pragma: allowlist secret
        "model": "gpt-test",
        "error": ERROR["error"],
        "traceback": ERROR["traceback"],
        "node_context": {"node_id": "3"},
        "workflow": json.dumps(_ui_workflow(3)),
    }

    response = harness.request("POST", "/doctor/analyze", json=body)

    assert response.status == 200, response.text
    assert len(harness.captured) == 1


# ---------------------------------------------------------------- collect_error_context contract
def _collect(harness: DoctorRouteHarness, error_node: str, workflow: Any) -> Dict[str, Any]:
    # The harness imports the package under a synthetic name and blocks plain `services` imports.
    helpers = sys.modules[f"{harness.package_name}.services.prompt_helpers"]
    return helpers.collect_error_context({"exception_message": "boom", "node_id": error_node}, workflow)


def test_a_ui_format_failed_node_exposes_its_connections_and_upstream_nodes(harness):
    workflow = _ui_workflow(3)
    original = copy.deepcopy(workflow)

    context = _collect(harness, "3", workflow)

    assert context["failed_node"]["class_type"] == "KSampler"
    assert context["failed_node"]["inputs"] == {"model": ["1", 0]}
    assert context["workflow_structure"]["upstream_nodes"] == [
        {"id": "1", "class_type": "CheckpointLoaderSimple", "connection": "model"}
    ]
    assert workflow == original
    # Widget values are not part of the collected details, so a secret in one cannot leak through them.
    assert SECRET not in json.dumps(context["failed_node"])


def test_malformed_ui_slots_and_link_rows_never_raise(harness):
    workflow = _ui_workflow(3)
    workflow["nodes"][0]["inputs"] = [
        None, "x", {"name": 7, "link": 1}, {"name": "skip", "link": None}, {"name": "gone", "link": 99},
        {"name": "model", "link": 1},
    ]
    workflow["links"] = [None, [1], "row", [2, 1, 0, 3, 0, "MODEL"], [1, 1, 0, 3, 0, "MODEL"]]

    context = _collect(harness, "3", workflow)

    assert context["failed_node"]["inputs"] == {"model": ["1", 0]}


@pytest.mark.parametrize("nodes_value", [None, "x", 7, {"a": 1}])
def test_a_non_list_nodes_member_is_read_as_an_api_format_prompt_without_raising(harness, nodes_value):
    context = _collect(harness, "3", {"nodes": nodes_value, "3": {"class_type": "KSampler", "inputs": {}}})

    assert context["failed_node"]["class_type"] == "KSampler"


def test_the_exact_execution_id_wins_over_its_local_segment(harness):
    workflow = {
        "12:3": {"class_type": "SubgraphSampler", "inputs": {}},
        "3": {"class_type": "RootSampler", "inputs": {}},
    }

    assert _collect(harness, "12:3", workflow)["failed_node"]["class_type"] == "SubgraphSampler"
    # Without an exact match the local segment is used, as before.
    assert _collect(harness, "99:3", workflow)["failed_node"]["class_type"] == "RootSampler"


def test_a_malformed_meta_block_or_title_never_raises(harness):
    workflow = {"3": {"class_type": "KSampler", "inputs": {}, "_meta": "not-a-dict", "title": 7}}

    assert _collect(harness, "3", workflow)["failed_node"]["title"] == ""


@pytest.mark.parametrize("workflow", [None, [], "text", 5, {}, {"nodes": []}])
def test_a_workflow_without_nodes_yields_no_failed_node(harness, workflow):
    assert _collect(harness, "3", workflow)["failed_node"] is None


def test_missing_connections_are_reported_for_api_format_nodes_only(harness, monkeypatch):
    class FakeSampler:
        @staticmethod
        def INPUT_TYPES():
            return {"required": {"model": ("MODEL",), "seed": ("INT",)}}

    fake_nodes = types.ModuleType("nodes")
    fake_nodes.NODE_CLASS_MAPPINGS = {"KSampler": FakeSampler}
    monkeypatch.setitem(sys.modules, f"{harness.package_name}.nodes", fake_nodes)

    api = _collect(harness, "3", {"3": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}}})
    ui = _collect(harness, "3", dict(_ui_workflow(3), nodes=[{"id": 3, "class_type": "KSampler", "type": "KSampler",
                                                      "inputs": [{"name": "model", "link": 1}]}]))

    assert [item["input"] for item in api["workflow_structure"]["missing_connections"]] == ["seed"]
    # A UI-format slot list omits widgets such as the seed; reporting them as missing would mislead.
    assert ui["workflow_structure"]["missing_connections"] == []
