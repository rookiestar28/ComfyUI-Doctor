"""Exact identity regressions using Doctor modules and inert workflow snapshots."""
import asyncio
import copy
import json

import pytest

from services.diagnostics.checks import model_assets, signature_packs, workflow_lint
from services.diagnostics.models import HealthCheckRequest, IssueTarget
from services.diagnostics.runner import DiagnosticsRunner

OPAQUE_ID = "insert:synthetic-operation:root:node:9"


def node(node_id, link=None):
    return {"id": node_id, "type": "KSampler", "inputs": [
        {"name": "model", "type": "MODEL", "link": link},
    ]}


@pytest.mark.parametrize("node_id", [9, "9", "09", OPAQUE_ID, "insert:other:root:node:9"])
def test_lint_and_runner_preserve_exact_node_identity(node_id):
    workflow = {"nodes": [node(node_id)], "links": []}
    original = copy.deepcopy(workflow)
    request = HealthCheckRequest(workflow=workflow)
    issues = asyncio.run(workflow_lint.check_workflow_lint(workflow, request))
    assert [issue.title for issue in issues] == ["Disconnected Required Input"]
    assert type(issues[0].target.node_id) is type(node_id)
    assert issues[0].target.node_id == node_id
    contained = asyncio.run(DiagnosticsRunner()._run_check_with_timeout(
        "workflow_lint", workflow_lint.check_workflow_lint, workflow, request, 2000,
    ))
    assert [issue.to_dict() for issue in contained] == [issue.to_dict() for issue in issues]
    assert workflow == original


@pytest.mark.parametrize("invalid", [None, True, False, 1.5, [], {}, "", " 9", "9\n", "x" * 1025])
def test_invalid_node_identity_cannot_discard_unrelated_findings(invalid):
    workflow = {"nodes": [node(invalid), node(OPAQUE_ID, 99), node(9)], "links": []}
    original = copy.deepcopy(workflow)
    issues = asyncio.run(workflow_lint.check_workflow_lint(workflow, HealthCheckRequest(workflow=workflow)))
    assert [(issue.title, issue.target.node_id) for issue in issues] == [
        ("Broken Link Reference", OPAQUE_ID), ("Disconnected Required Input", 9),
    ]
    assert workflow == original


def test_mixed_links_and_leading_zero_identities_are_not_coerced_or_overwritten():
    workflow = {"nodes": [node(9, 1), node("09"), node(OPAQUE_ID, 2)],
                "links": [[1, OPAQUE_ID, 0, 9, 0], [2, 9, 0, OPAQUE_ID, 0]]}
    issues = asyncio.run(workflow_lint.check_workflow_lint(workflow, HealthCheckRequest(workflow=workflow)))
    assert [(issue.title, issue.target.node_id) for issue in issues] == [
        ("Disconnected Required Input", "09"),
    ]


def test_duplicate_identities_are_skipped_without_hiding_other_nodes():
    workflow = {"nodes": [node(9), node("9"), node(OPAQUE_ID)], "links": []}
    issues = asyncio.run(workflow_lint.check_workflow_lint(workflow, HealthCheckRequest(workflow=workflow)))
    assert [issue.target.node_id for issue in issues] == [OPAQUE_ID]


@pytest.mark.parametrize("node_id", [9, "9", "09", OPAQUE_ID, "insert:other:root:node:9"])
def test_signature_target_and_json_round_trip_retain_scalar_type(node_id):
    converted = signature_packs._safe_node_id({"id": node_id})
    assert converted == node_id and type(converted) is type(node_id)
    restored = IssueTarget(**json.loads(json.dumps(IssueTarget(node_id=converted).to_dict())))
    assert restored.node_id == node_id and type(restored.node_id) is type(node_id)


@pytest.mark.parametrize("invalid", [True, 1.5, [], {}, "", " 9", "x" * 1025])
def test_signature_target_rejects_non_scalar_or_malformed_ids(invalid):
    assert signature_packs._safe_node_id({"id": invalid}) is None


def test_opaque_asset_components_are_bounded_distinct_and_do_not_leak_raw_ids():
    identifiers = [OPAQUE_ID, "insert:other:root:node:9", "../private:synthetic:9", "sha256~synthetic"]
    values = [model_assets._safe_execution_id_component(value) for value in identifiers]
    assert len(set(values)) == len(identifiers)
    for raw, safe in zip(identifiers, values):
        assert safe != "unknown" and raw not in safe
        assert safe.startswith("sha256~") and len(safe) == 71
        assert not any(char in safe for char in (":", "/", "\\", "\n"))
    assert model_assets._safe_execution_id_component(9) == "9"
    assert model_assets._safe_execution_id_component("09") == "09"
    # A raw string equal to a hashed component must enter a different namespace.
    assert model_assets._safe_execution_id_component(values[0]) != values[0]


def test_asset_context_keeps_raw_mapping_while_public_provenance_is_sanitized():
    child_id = "insert:child:root:node:9"
    workflow = {"nodes": [{"id": OPAQUE_ID, "type": "synthetic-subgraph"}],
                "definitions": {"subgraphs": [{"id": "synthetic-subgraph", "nodes": [
                    {"id": child_id, "type": "CheckpointLoaderSimple", "widgets_values": ["missing.safetensors"]},
                ]}]}}
    original = copy.deepcopy(workflow)
    contexts = model_assets._collect_workflow_asset_nodes(workflow)
    assert len(contexts) == 1
    context = contexts[0]
    assert context.visible_node_id == OPAQUE_ID
    assert context.source_node["id"] == child_id
    assert context.source_execution_id == ":".join(
        model_assets._safe_execution_id_component(value) for value in (OPAQUE_ID, child_id)
    )
    metadata = model_assets._asset_provenance_metadata(context, "CheckpointLoaderSimple", 0)
    serialized = json.dumps(metadata)
    assert OPAQUE_ID not in serialized and child_id not in serialized and "unknown" not in serialized
    assert workflow == original


def test_malformed_asset_nodes_do_not_hide_valid_root_or_nested_contexts():
    invalid = {"id": [], "type": "CheckpointLoaderSimple"}
    child = {"id": "child:9", "type": "CheckpointLoaderSimple"}
    workflow = {"nodes": [invalid, {"id": OPAQUE_ID, "type": "synthetic-subgraph"},
                           {"id": 9, "type": "CheckpointLoaderSimple"}],
                "definitions": {"subgraphs": [{"id": "synthetic-subgraph", "nodes": [invalid, child]}]}}
    original = copy.deepcopy(workflow)
    contexts = model_assets._collect_workflow_asset_nodes(workflow)
    assert [(context.visible_node_id, context.source_node["id"]) for context in contexts] == [
        (OPAQUE_ID, "child:9"), (9, 9),
    ]
    assert workflow == original
