"""Known node types for the workflow lint: the running host's registry first, a static list as fallback.

``Unknown Node Type`` must mean "the running host does not know this type". A hand-written list alone
flagged common first-party nodes (``UNETLoader``, ``DualCLIPLoader``, ...), and a node type that is not a
string made the whole check raise.
"""
import asyncio
import importlib
import sys
import types

import pytest

from services.diagnostics.checks.workflow_lint import check_workflow_lint
from services.diagnostics.models import HealthCheckRequest, IssueSeverity

# Every first-party name in the reference host's `nodes.py` mapping at the aligned revision (names only).
HOST_FIRST_PARTY_NAMES = (
    "KSampler", "CheckpointLoaderSimple", "CLIPTextEncode", "CLIPSetLastLayer", "VAEDecode", "VAEEncode",
    "VAEEncodeForInpaint", "VAELoader", "EmptyLatentImage", "LatentUpscale", "LatentUpscaleBy",
    "LatentFromBatch", "RepeatLatentBatch", "SaveImage", "PreviewImage", "LoadImage", "LoadImageMask",
    "LoadImageOutput", "ImageScale", "ImageScaleBy", "ImageInvert", "ImageBatch", "ImagePadForOutpaint",
    "EmptyImage", "ConditioningAverage", "ConditioningCombine", "ConditioningConcat", "ConditioningMultiply",
    "ConditioningSetArea", "ConditioningSetAreaPercentage", "ConditioningSetAreaStrength",
    "ConditioningSetMask", "KSamplerAdvanced", "SetLatentNoiseMask", "LatentComposite", "LatentBlend",
    "LatentRotate", "LatentFlip", "LatentCrop", "LoraLoader", "CLIPLoader", "UNETLoader", "DualCLIPLoader",
    "CLIPVisionEncode", "StyleModelApply", "unCLIPConditioning", "ControlNetApply", "ControlNetApplyAdvanced",
    "ControlNetLoader", "DiffControlNetLoader", "StyleModelLoader", "CLIPVisionLoader", "VAEDecodeTiled",
    "VAEEncodeTiled", "unCLIPCheckpointLoader", "GLIGENLoader", "GLIGENTextBoxApply",
    "InpaintModelConditioning", "CheckpointLoader", "DiffusersLoader", "LoadLatent", "SaveLatent",
    "ConditioningZeroOut", "ConditioningSetTimestepRange", "LoraLoaderModelOnly",
)
# Registered by the host frontend as virtual nodes: they have no backend class, so only the list knows them.
FRONTEND_VIRTUAL_NAMES = ("PrimitiveNode", "Reroute", "Note", "MarkdownNote")
HOST_ANCHORS = ("KSampler", "CheckpointLoaderSimple", "VAEDecode", "CLIPTextEncode")

# Issue id of the INFO finding for an unregistered type (golden value captured before the change).
GOLDEN_UNKNOWN = ("NotARealNodeXyz", 7, "c02dfcaec0718168")  # pragma: allowlist secret


@pytest.fixture
def known_nodes():
    return importlib.import_module("services.diagnostics.known_nodes")


@pytest.fixture(autouse=True)
def _no_host_module(monkeypatch):
    # Tests start without a registry; an individual test injects one explicitly.
    monkeypatch.delitem(sys.modules, "nodes", raising=False)


def install_registry(monkeypatch, mapping):
    module = types.ModuleType("nodes")
    module.NODE_CLASS_MAPPINGS = mapping
    monkeypatch.setitem(sys.modules, "nodes", module)
    return module


def host_mapping(*extra):
    return {name: object() for name in (*HOST_ANCHORS, *extra)}


def lint(node_type, node_id=7, properties=None):
    node = {"id": node_id, "type": node_type, "inputs": []}
    if properties is not None:
        node["properties"] = properties
    workflow = {"nodes": [node], "links": []}
    return asyncio.run(check_workflow_lint(workflow, HealthCheckRequest(workflow=workflow)))


def unknown_findings(node_type, **kwargs):
    return [issue for issue in lint(node_type, **kwargs) if issue.title in {"Unknown Node Type", "Missing Custom Node"}]


# ------------------------------------------------------------------ the static fallback
@pytest.mark.parametrize("name", HOST_FIRST_PARTY_NAMES)
def test_every_first_party_host_name_is_known_without_a_registry(name):
    assert unknown_findings(name) == []


@pytest.mark.parametrize("name", FRONTEND_VIRTUAL_NAMES)
def test_frontend_virtual_nodes_are_known_even_with_a_registry_that_lacks_them(name, monkeypatch):
    install_registry(monkeypatch, host_mapping())

    assert unknown_findings(name) == []


def test_the_exported_core_list_still_contains_the_previous_names():
    from services.diagnostics.checks import workflow_lint

    for name in ("KSampler", "PrimitiveNode", "ComfySwitchNode", "BranchNode"):
        assert name in workflow_lint.KNOWN_CORE_NODE_TYPES


# ------------------------------------------------------------------ the running host's registry
def test_a_type_registered_in_the_host_is_not_reported(monkeypatch):
    install_registry(monkeypatch, host_mapping("MyRegisteredCustomNode"))

    assert unknown_findings("MyRegisteredCustomNode") == []


def test_a_type_missing_from_the_host_registry_is_still_reported_exactly_as_before(monkeypatch):
    name, node_id, golden_id = GOLDEN_UNKNOWN
    install_registry(monkeypatch, host_mapping("SomethingElse"))

    (issue,) = unknown_findings(name, node_id=node_id)

    assert issue.issue_id == golden_id
    assert issue.title == "Unknown Node Type"
    assert issue.severity == IssueSeverity.INFO
    assert issue.target.node_id == node_id
    assert issue.summary == f"Node type '{name}' (#{node_id}) is not in the known node registry"


def test_the_same_finding_is_produced_without_a_registry():
    name, node_id, golden_id = GOLDEN_UNKNOWN

    (issue,) = unknown_findings(name, node_id=node_id)

    assert issue.issue_id == golden_id


def test_the_registry_is_read_on_every_call(known_nodes, monkeypatch):
    assert known_nodes.is_known_node_type("LateCustomNode") is False
    mapping = host_mapping()
    install_registry(monkeypatch, mapping)
    assert known_nodes.is_known_node_type("LateCustomNode") is False
    mapping["LateCustomNode"] = object()
    assert known_nodes.is_known_node_type("LateCustomNode") is True


def test_the_missing_node_property_and_custom_prefixes_behave_as_before(monkeypatch):
    install_registry(monkeypatch, host_mapping())

    (missing,) = unknown_findings("GhostNode", properties={"missing_node": True})
    assert missing.title == "Missing Custom Node" and missing.severity == IssueSeverity.CRITICAL
    assert unknown_findings("IPAdapterAdvanced") == []
    assert unknown_findings("VHS_VideoCombine") == []


# ------------------------------------------------------------------ an unusable registry
def test_a_module_that_is_not_the_host_registry_is_ignored(known_nodes, monkeypatch):
    # The package's own `nodes.py` maps one node; imported as top-level `nodes` it must not become the registry.
    install_registry(monkeypatch, {"DebugPrintNode": object()})

    assert known_nodes.is_known_node_type("DebugPrintNode") is False
    assert known_nodes.is_known_node_type("KSampler") is True  # static list still applies


@pytest.mark.parametrize("mapping", [None, [], "KSampler", 5, ("KSampler",)], ids=repr)
def test_a_registry_that_is_not_a_mapping_is_ignored(known_nodes, monkeypatch, mapping):
    install_registry(monkeypatch, mapping)

    assert known_nodes.is_known_node_type("UNETLoader") is True
    assert known_nodes.is_known_node_type("NotARealNodeXyz") is False


def test_a_registry_whose_lookup_raises_never_breaks_the_check(known_nodes, monkeypatch):
    class Hostile(dict):
        def __contains__(self, key):
            raise RuntimeError("registry is being mutated")

    install_registry(monkeypatch, Hostile(host_mapping("X")))

    assert known_nodes.is_known_node_type("NotARealNodeXyz") is False
    assert known_nodes.is_known_node_type("UNETLoader") is True
    assert [issue.title for issue in lint("NotARealNodeXyz")] == ["Unknown Node Type"]


def test_a_registry_that_fails_only_for_the_looked_up_name_is_treated_as_not_knowing_it(known_nodes, monkeypatch):
    class FailsOnLookup(dict):
        def __contains__(self, key):
            if key in HOST_ANCHORS:
                return True
            raise RuntimeError("registry is being mutated")

    install_registry(monkeypatch, FailsOnLookup(host_mapping()))

    assert known_nodes.is_known_node_type("NotARealNodeXyz") is False
    assert known_nodes.is_known_node_type("UNETLoader") is True
    assert [issue.title for issue in lint("NotARealNodeXyz")] == ["Unknown Node Type"]


def test_a_host_module_without_the_attribute_is_ignored(known_nodes, monkeypatch):
    monkeypatch.setitem(sys.modules, "nodes", types.ModuleType("nodes"))

    assert known_nodes.is_known_node_type("NotARealNodeXyz") is False


# ------------------------------------------------------------------ type values that are not names
@pytest.mark.parametrize("value", [None, 5, 1.5, True, [], ["x"], {}, {"a": 1}, b"KSampler", "", "x" * 5000])
def test_a_node_type_that_is_not_a_usable_name_never_raises(known_nodes, value):
    assert known_nodes.is_known_node_type(value) is False
    # The lint check as a whole keeps working; a value that is not a name yields no unknown-type finding.
    titles = [issue.title for issue in lint(value)]
    if isinstance(value, str) and value:
        assert titles.count("Unknown Node Type") == 1
    else:
        assert "Unknown Node Type" not in titles


def test_an_oversized_name_is_reported_without_echoing_unbounded_text():
    findings = unknown_findings("x" * 5000)

    assert len(findings) == 1
    assert len(findings[0].summary) < 5200
