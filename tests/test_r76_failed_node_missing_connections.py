"""The failed node's missing required inputs come from the host's node registry, not from this package's own.

``collect_error_context`` used ``from ..nodes import NODE_CLASS_MAPPINGS``. The relative import succeeds and
names this package's own one-node ``nodes.py``, so the lookup of every real node class returned ``None`` and
``workflow_structure.missing_connections`` stayed empty whatever the workflow was; the fallback to the host's
``nodes`` only ran after an ``ImportError`` that never happens. The registry now comes from
``known_nodes.host_node_registry()``: the host's already-loaded ``NODE_CLASS_MAPPINGS``, trusted only when it
carries the core anchor names. Nothing is imported to find it.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any, Dict

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness  # noqa: E402

ANCHORS = ("KSampler", "CheckpointLoaderSimple", "VAEDecode", "CLIPTextEncode")


class FakeSampler:
    @staticmethod
    def INPUT_TYPES():
        return {"required": {"model": ("MODEL",), "seed": ("INT", {"default": 0})}}


class ExplodingSampler:
    @staticmethod
    def INPUT_TYPES():
        raise RuntimeError("host code failed")


def host_like(**extra: Any) -> Dict[str, Any]:
    registry = {name: object for name in ANCHORS}
    registry["KSampler"] = FakeSampler
    registry.update(extra)
    return registry


def install(monkeypatch, name: str, mapping: Any) -> None:
    module = types.ModuleType(name)
    module.NODE_CLASS_MAPPINGS = mapping
    monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture(scope="module")
def harness():
    with DoctorRouteHarness() as active:
        yield active


def collect(harness, workflow: Any, node_id: str = "3") -> Dict[str, Any]:
    helpers = sys.modules[f"{harness.package_name}.services.prompt_helpers"]
    return helpers.collect_error_context({"exception_message": "boom", "node_id": node_id}, workflow)


def missing(context: Dict[str, Any]):
    return context["workflow_structure"]["missing_connections"]


API = {"3": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}}}
UI = {"nodes": [{"id": 3, "type": "KSampler", "class_type": "KSampler", "inputs": [{"name": "model", "link": 1}]}], "links": []}


def test_missing_required_inputs_are_reported_from_the_host_registry(harness, monkeypatch):
    install(monkeypatch, "nodes", host_like())

    context = collect(harness, API)

    assert missing(context) == [{"input": "seed", "type": str(("INT", {"default": 0}))}]
    assert context["failed_node"]["class_type"] == "KSampler"


def test_a_fully_connected_node_reports_nothing(harness, monkeypatch):
    install(monkeypatch, "nodes", host_like())
    workflow = {"3": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 5}}}

    assert missing(collect(harness, workflow)) == []


def test_the_packages_own_nodes_module_is_never_the_registry(harness, monkeypatch):
    # The old lookup read `<package>.nodes`; a host-like mapping placed there must be ignored.
    install(monkeypatch, f"{harness.package_name}.nodes", host_like())
    monkeypatch.delitem(sys.modules, "nodes", raising=False)

    assert missing(collect(harness, API)) == []


def test_a_nodes_module_without_the_host_anchors_is_not_trusted(harness, monkeypatch):
    # The package's own `nodes.py` (one debug node) is importable as `nodes` in tests and standalone runs.
    install(monkeypatch, "nodes", {"KSampler": FakeSampler})

    assert missing(collect(harness, API)) == []


def test_without_any_host_registry_the_result_is_the_empty_list(harness, monkeypatch):
    monkeypatch.delitem(sys.modules, "nodes", raising=False)

    context = collect(harness, API)

    assert missing(context) == []
    assert context["failed_node"]["class_type"] == "KSampler"
    assert "nodes" not in sys.modules, "finding the registry must not import a module"


def test_a_ui_format_node_reports_nothing_even_with_a_registry(harness, monkeypatch):
    install(monkeypatch, "nodes", host_like())

    assert missing(collect(harness, UI)) == []


def test_a_node_class_the_registry_does_not_know_reports_nothing(harness, monkeypatch):
    install(monkeypatch, "nodes", host_like())
    workflow = {"3": {"class_type": "SomeCustomNode", "inputs": {}}}

    context = collect(harness, workflow)

    assert missing(context) == []
    assert context["failed_node"]["class_type"] == "SomeCustomNode"


@pytest.mark.parametrize("class_type", [["KSampler"], {"a": 1}, 5, None], ids=repr)
def test_an_odd_class_type_never_breaks_the_context(harness, monkeypatch, class_type):
    install(monkeypatch, "nodes", host_like())
    workflow = {"3": {"class_type": class_type, "inputs": {}}}

    context = collect(harness, workflow)

    assert missing(context) == []
    assert context["failed_node"] is not None


def test_a_registry_class_that_raises_is_contained(harness, monkeypatch):
    install(monkeypatch, "nodes", host_like(KSampler=ExplodingSampler))

    context = collect(harness, API)

    assert missing(context) == []
    assert context["failed_node"]["class_type"] == "KSampler"
    assert context["workflow_structure"]["upstream_nodes"] == []


def test_the_public_registry_helper_matches_the_guarded_lookup(harness, monkeypatch):
    known_nodes = importlib.import_module(f"{harness.package_name}.services.diagnostics.known_nodes")
    registry = host_like()
    install(monkeypatch, "nodes", registry)

    assert known_nodes.host_node_registry() is known_nodes._host_registry()
    assert known_nodes.host_node_registry() is registry

    install(monkeypatch, "nodes", {"KSampler": FakeSampler})
    assert known_nodes.host_node_registry() is None
    monkeypatch.delitem(sys.modules, "nodes", raising=False)
    assert known_nodes.host_node_registry() is None
