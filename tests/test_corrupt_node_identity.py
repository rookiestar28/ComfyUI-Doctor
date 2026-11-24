"""Findings of nodes with a malformed or duplicate identity are kept, never targeted.

R66 made node identity exact (a malformed or duplicate id is not coerced), which made every finding of
such a node disappear. These tests pin the replacement contract across workflow lint, model assets and
signature packs: the finding survives, it carries no node target, two corrupt nodes get distinct and
deterministic issue ids, and the issue ids of ordinary valid nodes are byte-identical to what they were.
"""
import asyncio
import copy
import json
import time
from unittest.mock import patch

import pytest

from services.diagnostics.checks import model_assets, signature_packs, workflow_lint
from services.diagnostics.models import HealthCheckRequest

OPAQUE = "insert:synthetic-operation:root:node:9"
MARK = "LEAKMARK"
MISSING = object()

# The twelve malformed kinds; the string kinds carry a marker so a leak into any text is detectable.
MALFORMED = {
    "missing": MISSING,
    "none": None,
    "empty": "",
    "bool": True,
    "float": 1.5,
    "negative": -1,
    "above_safe_integer": 2**53,
    "leading_space": f" {MARK}",
    "control_char": f"{MARK}\x00",
    "over_1024": MARK * 200,
    "list": [MARK],
    "dict": {MARK: 1},
}


def resolver():
    from services.diagnostics.node_identity import resolve_node_identities
    return resolve_node_identities


def lint_node(node_id, link=None, extra=None):
    node = {"type": "KSampler", "inputs": [{"name": "model", "type": "MODEL", "link": link}]}
    if node_id is not MISSING:
        node["id"] = node_id
    node.update(extra or {})
    return node


def run_check(check, workflow):
    return asyncio.run(check(workflow, HealthCheckRequest(workflow=workflow)))


def lint(workflow):
    return run_check(workflow_lint.check_workflow_lint, workflow)


def dumped(issues):
    return json.dumps([issue.to_dict() for issue in issues], ensure_ascii=False)


def rows(issues):
    return [(issue.title, issue.issue_id, issue.target.to_dict()) for issue in issues]


ASSET_PATHS = {"checkpoints": [], "input": [], "input_3d": [], "output": [], "vae": []}


def assets(workflow):
    with patch.object(model_assets, "_get_comfy_model_paths", return_value=ASSET_PATHS):
        return run_check(model_assets.check_model_assets, workflow)


def asset_node(node_id, value="r68_missing_model.safetensors", node_type="CheckpointLoaderSimple"):
    node = {"type": node_type, "title": "Loader", "widgets_values": [value]}
    if node_id is not MISSING:
        node["id"] = node_id
    return node


def signatures(workflow, monkeypatch):
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", raising=False)
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACK_IDS", raising=False)
    return run_check(signature_packs.check_signature_packs, workflow)


def signature_node(node_id):
    node = {"type": "CheckpointLoaderSimple", "title": "Loader", "widgets_values": ["path/to/model.safetensors"]}
    if node_id is not MISSING:
        node["id"] = node_id
    return node


# ---------------------------------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(MALFORMED))
def test_resolver_marks_each_malformed_kind_non_actionable(kind):
    nodes = [lint_node(5), lint_node(MALFORMED[kind])]
    original = copy.deepcopy(nodes)
    valid, bad = resolver()(nodes)
    assert (valid.state, valid.node_id, valid.discriminator, valid.label) == ("valid", 5, "", "#5")
    assert (bad.state, bad.node_id, bad.discriminator, bad.position) == ("malformed", None, "pos~1", 1)
    assert bad.label == "unidentified node at nodes[1]"
    assert MARK not in bad.label
    assert nodes == original


@pytest.mark.parametrize("first,second", [(5, 5), (5, "5"), ("x:1", "x:1")])
def test_resolver_marks_every_member_of_a_duplicate_group(first, second):
    one, two, other = resolver()([lint_node(first), lint_node(second), lint_node(7)])
    assert [(i.state, i.node_id, i.discriminator) for i in (one, two)] == [
        ("duplicate", None, "pos~0"), ("duplicate", None, "pos~1"),
    ]
    assert (other.state, other.node_id) == ("valid", 7)


def test_resolver_keeps_leading_zero_and_integer_distinct():
    five, zero_five = resolver()([lint_node(5), lint_node("05")])
    assert (five.state, five.node_id) == ("valid", 5)
    assert (zero_five.state, zero_five.node_id) == ("valid", "05")


def test_resolver_positions_count_non_dict_entries_and_non_lists_are_empty():
    identities = resolver()(["junk", None, lint_node(MISSING), 3, lint_node(4)])
    assert [(i.position, i.state) for i in identities] == [(2, "malformed"), (4, "valid")]
    for value in (None, {}, "nodes", 5, ()):
        assert resolver()(value) == []


def test_resolver_is_linear_on_large_lists():
    nodes = [lint_node(index) for index in range(20000)] + [lint_node(MISSING) for _ in range(20000)]
    started = time.perf_counter()
    identities = resolver()(nodes)
    assert time.perf_counter() - started < 5
    assert len(identities) == 40000
    assert sum(1 for i in identities if i.state == "valid") == 20000


# ---------------------------------------------------------------------------------------------------
# Workflow lint
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(MALFORMED))
def test_lint_keeps_findings_of_every_malformed_kind_without_a_target(kind):
    workflow = {"nodes": [lint_node(MALFORMED[kind]), lint_node(5)], "links": []}
    original = copy.deepcopy(workflow)
    issues = lint(workflow)
    assert [(i.title, i.target.to_dict()) for i in issues] == [
        ("Disconnected Required Input", {}), ("Disconnected Required Input", {"node_id": 5}),
    ]
    text = dumped(issues)
    assert MARK not in text and "None" not in text and "#None" not in text
    assert "unidentified node at nodes[0]" in issues[0].summary
    assert not any("Locate Node" in step and "unavailable" not in step for step in issues[0].recommendation)
    assert any("Locate Node is unavailable" in step for step in issues[0].recommendation)
    assert any("Use 'Locate Node'" in step for step in issues[1].recommendation)
    assert workflow == original


def test_lint_keeps_every_check_for_a_corrupt_node():
    latent = {
        "type": "EmptyLatentImage", "title": "Latent", "widgets_values": [8192, 8192, 32],
        "inputs": [{"name": "model", "type": "MODEL", "link": 99}],
    }
    missing = {"type": "MissingThing", "title": "Missing", "properties": {"missing_node": True}}
    issues = lint({"nodes": [latent, missing], "links": []})
    assert {i.title for i in issues} == {
        "Broken Link Reference", "Missing Custom Node", "Very High Resolution Width",
        "Very High Resolution Height", "Very High Batch Size",
    }
    assert all(i.target.to_dict() == {} for i in issues)
    assert len({i.issue_id for i in issues}) == len(issues)


def test_lint_gives_distinct_deterministic_ids_to_identical_corrupt_nodes():
    workflow = {"nodes": [lint_node(None), lint_node(None), lint_node("")], "links": []}
    first = [i.issue_id for i in lint(workflow)]
    assert len(first) == 3 and len(set(first)) == 3
    assert first == [i.issue_id for i in lint(copy.deepcopy(workflow))]


@pytest.mark.parametrize("first,second", [(5, 5), (5, "5")])
def test_lint_duplicates_keep_both_findings_untargeted_and_report_the_group_once(first, second):
    workflow = {"nodes": [lint_node(first), lint_node(second), lint_node(OPAQUE)], "links": []}
    issues = lint(workflow)
    assert [(i.title, i.target.to_dict()) for i in issues] == [
        ("Disconnected Required Input", {}),
        ("Disconnected Required Input", {}),
        ("Disconnected Required Input", {"node_id": OPAQUE}),
        ("Duplicate Node ID", {}),
    ]
    assert len({i.issue_id for i in issues}) == 4
    duplicate = issues[-1]
    assert duplicate.issue_id == lint(copy.deepcopy(workflow))[-1].issue_id
    assert any("nodes[0]" in line and "nodes[1]" in line for line in duplicate.evidence)
    assert any("2" in line for line in duplicate.evidence)
    assert duplicate.severity.value == "warning" and duplicate.category.value == "workflow"


def test_lint_duplicate_group_bounds_positions_and_groups():
    big_group = {"nodes": [lint_node(1) for _ in range(12)], "links": []}
    duplicate = [i for i in lint(big_group) if i.title == "Duplicate Node ID"]
    assert len(duplicate) == 1
    positions_line = next(line for line in duplicate[0].evidence if "nodes[" in line)
    assert positions_line.count("nodes[") == 8 and "4 more" in positions_line

    many_groups = {"nodes": [lint_node(group) for group in range(25) for _ in range(2)], "links": []}
    duplicates = [i for i in lint(many_groups) if i.title == "Duplicate Node ID"]
    assert len(duplicates) == 20
    assert any("5 more duplicate groups" in line for line in duplicates[-1].evidence)


def test_lint_duplicate_identity_is_shown_only_through_the_bounded_component():
    long_id = "insert:" + MARK * 100
    issues = lint({"nodes": [lint_node(long_id), lint_node(long_id)], "links": []})
    duplicate = next(i for i in issues if i.title == "Duplicate Node ID")
    text = dumped([duplicate])
    assert MARK not in text and "sha256~" in text
    assert all(len(line) < 300 for line in duplicate.evidence + [duplicate.summary])


def test_lint_mixed_workflow_keeps_valid_findings_exactly():
    valid = {"nodes": [lint_node(5), lint_node(7)], "links": []}
    base = rows(lint(valid))
    mixed = {"nodes": [lint_node(5), lint_node(None), lint_node(7)], "links": []}
    with_corrupt = rows(lint(mixed))
    assert [r for r in with_corrupt if r[2]] == base


LINT_GOLDEN = [
    ("Disconnected Required Input", "76cbd0abb937b5ce", {"node_id": 5}),  # pragma: allowlist secret
    ("Broken Link Reference", "f6ce8bf1537613ee", {"node_id": 5}),  # pragma: allowlist secret
    ("Unknown Node Type", "e773a26ea2dae007", {"node_id": OPAQUE}),
    ("Unknown Node Type", "fd154785651f6e68", {"node_id": "09"}),  # pragma: allowlist secret
    ("Missing Custom Node", "9cfe2b52c47234b9", {"node_id": 11}),  # pragma: allowlist secret
    ("Very High Step Count", "659aa0fe8f868c8a", {"node_id": 5}),
    ("Very High Resolution Width", "cea256e96d9d0461", {"node_id": 7}),  # pragma: allowlist secret
    ("Very High Resolution Height", "2c95dab719bad184", {"node_id": 7}),  # pragma: allowlist secret
    ("Very High Batch Size", "aa57e6d31b160b4e", {"node_id": 7}),  # pragma: allowlist secret
    ("Unusually Large Parameter Value", "6dc5cb9c8c7155cd", {"node_id": "09"}),
]


def test_lint_issue_ids_of_valid_unique_nodes_match_the_pre_change_values():
    # Computed at the commit before the change (archived with the implementation evidence).
    workflow = {"nodes": [
        {"id": 5, "type": "KSampler", "title": "Sampler",
         "inputs": [{"name": "model", "type": "MODEL", "link": None},
                    {"name": "positive", "type": "CONDITIONING", "link": 99}],
         "widgets_values": [1, "fixed", 200, 35.0, "euler", "normal", 1.0]},
        {"id": OPAQUE, "type": "WeirdNodeType123", "title": "Weird", "widgets_values": []},
        {"id": 7, "type": "EmptyLatentImage", "title": "Latent", "widgets_values": [8192, 8192, 32]},
        {"id": "09", "type": "Foo", "title": "Foo", "widgets_values": [200000]},
        {"id": 11, "type": "MissingThing", "title": "Missing", "properties": {"missing_node": True}},
    ], "links": []}
    assert rows(lint(workflow)) == LINT_GOLDEN


# ---------------------------------------------------------------------------------------------------
# Model assets
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(MALFORMED))
def test_assets_keep_findings_of_every_malformed_root_without_a_target(kind):
    workflow = {"nodes": [asset_node(MALFORMED[kind]), asset_node(5, "r68_other.safetensors")]}
    original = copy.deepcopy(workflow)
    issues = assets(workflow)
    assert [(i.title, i.target.to_dict()) for i in issues] == [
        ("Asset File Not Found", {}), ("Asset File Not Found", {"node_id": 5}),
    ]
    assert issues[0].issue_id != issues[1].issue_id
    text = dumped(issues)
    assert MARK not in text and "#None" not in text and "None" not in issues[0].summary
    assert "unidentified node at nodes[0]" in issues[0].summary
    assert workflow == original


def test_assets_duplicate_roots_are_untargeted_with_distinct_ids():
    issues = assets({"nodes": [asset_node(5), asset_node("5"), asset_node(6, "r68_six.safetensors")]})
    assert [i.target.to_dict() for i in issues] == [{}, {}, {"node_id": 6}]
    assert len({i.issue_id for i in issues}) == 3


def test_assets_two_corrupt_roots_with_the_same_file_get_distinct_ids():
    issues = assets({"nodes": [asset_node(None), asset_node(None)]})
    assert len(issues) == 2 and issues[0].issue_id != issues[1].issue_id


SUBGRAPH_ID = "r68-subgraph"


def subgraph_workflow(children, root_id=OPAQUE):
    return {
        "nodes": [{"id": root_id, "type": SUBGRAPH_ID, "title": "Sub"}],
        "definitions": {"subgraphs": [{"id": SUBGRAPH_ID, "nodes": children}]},
    }


def test_assets_nested_duplicate_children_keep_both_findings():
    children = [asset_node(7, "r68_first.safetensors"), asset_node(7, "r68_second.safetensors")]
    issues = assets(subgraph_workflow(children))
    assert len(issues) == 2
    assert {i.target.to_dict().get("node_id") for i in issues} == {OPAQUE}
    assert len({i.issue_id for i in issues}) == 2
    names = " ".join(i.summary for i in issues)
    assert "r68_first.safetensors" in names and "r68_second.safetensors" in names


def test_assets_nested_child_without_an_id_is_kept_and_distinct():
    issues = assets(subgraph_workflow([asset_node(MISSING, "r68_a.safetensors"), asset_node(3, "r68_b.safetensors")]))
    assert len(issues) == 2 and issues[0].issue_id != issues[1].issue_id
    assert all(i.target.to_dict() == {"node_id": OPAQUE} for i in issues)
    for issue in issues:
        serialized = dumped([issue])
        assert "None" not in serialized


def test_assets_corrupt_root_subgraph_children_have_no_target_at_all():
    issues = assets(subgraph_workflow([asset_node(3, "r68_child.safetensors")], root_id=None))
    assert len(issues) == 1 and issues[0].target.to_dict() == {}
    assert issues[0].metadata["asset_provenance"]["visible_node_id"] is None
    assert "None" not in issues[0].summary


def test_promoted_values_are_never_written_through_an_ambiguous_id():
    definition = {
        "nodes": [
            {"id": 7, "type": "CheckpointLoaderSimple", "inputs": [{"name": "ckpt_name", "widget": {"name": "ckpt_name"}}],
             "widgets_values": ["r68_first.safetensors"]},
            {"id": 7, "type": "CheckpointLoaderSimple", "inputs": [{"name": "ckpt_name", "widget": {"name": "ckpt_name"}}],
             "widgets_values": ["r68_second.safetensors"]},
        ],
        "inputs": [{"name": "ckpt_name", "linkIds": [1]}],
        "links": [{"id": 1, "origin_id": -10, "origin_slot": 0, "target_id": 7, "target_slot": 0}],
    }
    children = model_assets._apply_promoted_widget_values(definition, {"widgets_values": ["promoted.safetensors"]})
    assert [(child["widgets_values"], promoted) for child, promoted in children] == [
        (["r68_first.safetensors"], frozenset()), (["r68_second.safetensors"], frozenset()),
    ]


def test_asset_provenance_of_a_non_actionable_node_reports_no_raw_id():
    issues = assets(subgraph_workflow([asset_node(f" {MARK}", "r68_a.safetensors")]))
    assert len(issues) == 1
    provenance = issues[0].metadata["asset_provenance"]
    assert provenance["source_node_id"] is None
    assert MARK not in dumped(issues)
    assert provenance["source_execution_id"].endswith(":pos~0")


ASSET_GOLDEN = [
    ("Asset File Not Found", "e0f44967b9e39cc0", {"node_id": 5}),  # pragma: allowlist secret
    ("Asset File Not Found", "28f44d5eefb3e6a0", {"node_id": OPAQUE}),  # pragma: allowlist secret
    ("Asset File Not Found", "5227ac70ab474f9f", {"node_id": OPAQUE}),  # pragma: allowlist secret
]


def test_asset_issue_ids_of_valid_unique_nodes_match_the_pre_change_values():
    workflow = {
        "nodes": [asset_node(5, "r68_golden_missing_model.safetensors"), {"id": OPAQUE, "type": "r68-golden-subgraph", "title": "Sub"}],
        "definitions": {"subgraphs": [{"id": "r68-golden-subgraph", "nodes": [
            {"id": 3, "type": "CheckpointLoaderSimple", "widgets_values": ["r68_golden_nested_missing.safetensors"]},
            {"id": "child:9", "type": "VAELoader", "widgets_values": ["r68_golden_vae.safetensors"]},
        ]}]},
    }
    assert rows(assets(workflow)) == ASSET_GOLDEN


def test_extraction_budgets_are_unchanged():
    assert (model_assets.MAX_WORKFLOW_NODES, model_assets.MAX_SUBGRAPH_DEPTH) == (1000, 8)
    assert (model_assets.DEFAULT_MAX_PATHS, model_assets.MAX_PATH_BUDGET) == (50, 500)
    assert (signature_packs.MAX_NODES_SCAN, signature_packs.MAX_ISSUES_PER_RUN) == (400, 20)


# ---------------------------------------------------------------------------------------------------
# Signature packs
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["missing", "none", "bool", "leading_space", "list"])
def test_signature_packs_keep_malformed_nodes_without_a_target(kind, monkeypatch):
    issues = signatures({"nodes": [signature_node(MALFORMED[kind])]}, monkeypatch)
    assert len(issues) == 1 and issues[0].target.to_dict() == {}
    assert MARK not in dumped(issues) and "None" not in dumped(issues)
    assert "unidentified node at nodes[0]" in " ".join(issues[0].evidence)


def test_signature_packs_duplicate_ids_are_not_targeted_and_have_distinct_ids(monkeypatch):
    # The built-in rule stops after max_matches (2), so a valid node is checked in its own call.
    issues = signatures({"nodes": [signature_node(5), signature_node("5")]}, monkeypatch)
    assert [i.target.to_dict() for i in issues] == [{}, {}]
    assert len({i.issue_id for i in issues}) == 2
    valid = signatures({"nodes": [signature_node(6)]}, monkeypatch)
    assert [i.target.to_dict() for i in valid] == [{"node_id": 6}]


def test_signature_packs_two_corrupt_nodes_get_distinct_deterministic_ids(monkeypatch):
    workflow = {"nodes": [signature_node(None), signature_node(MISSING)]}
    first = [i.issue_id for i in signatures(workflow, monkeypatch)]
    assert len(first) == 2 and first[0] != first[1]
    assert first == [i.issue_id for i in signatures(copy.deepcopy(workflow), monkeypatch)]


SIGNATURE_GOLDEN = [
    ("Placeholder or Example Model Path", "d5a0ed7d46582210", {"node_id": 1}),  # pragma: allowlist secret
    (
        "Possible Missing Asset / Unconfigured Loader",
        "810d42eb5f8084cd",  # pragma: allowlist secret
        {"node_id": OPAQUE},
    ),
    ("Sampler Denoise Value Looks Out of Range", "767442bd60a5b2e6", {"node_id": "09"}),  # pragma: allowlist secret
]


def test_signature_issue_ids_of_valid_unique_nodes_match_the_pre_change_values(monkeypatch):
    workflow = {"nodes": [
        {"id": 1, "type": "CheckpointLoaderSimple", "title": "Checkpoint Loader", "widgets_values": ["path/to/model.safetensors"]},
        {"id": OPAQUE, "type": "ControlNetLoader", "title": "ControlNet Loader", "widgets_values": ["model not found - select model"]},
        {"id": "09", "type": "KSampler", "title": "KSampler", "widgets_values": [12345, "fixed", 20, 8.0, "euler", "normal", 1.5]},
    ]}
    assert rows(signatures(workflow, monkeypatch)) == SIGNATURE_GOLDEN
