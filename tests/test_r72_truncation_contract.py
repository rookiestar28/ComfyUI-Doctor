"""Input-shape and neighborhood contract of ``truncate_workflow_smart``.

The chat and analyze routes hand it whatever the sidebar sent: a JSON string or an already parsed dict
or list, in the host's serialized-graph shape or as an API prompt keyed by node id. Every accepted shape
must stay within the character budget, the documented hop count must be honoured, and the metadata must
tell the truth about the error node.
"""
import copy
import itertools
import json
import os
import sys

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from truncate_workflow import _get_priority_nodes, truncate_workflow_smart  # noqa: E402

CONTRACT_KEYS = {
    "truncation_method", "original_length", "truncated_length", "original_nodes", "kept_nodes",
    "error_node_preserved",
}


def api_prompt(count, pad=60, first=1):
    """An API prompt: ``{"<id>": {"class_type": ..., "inputs": {...}}}`` forming one chain."""
    return {
        str(i): {
            "class_type": f"Step{i}",
            "inputs": {"x": [str(i - 1), 0]} if i > first else {},
            "_meta": {"title": "t" * pad},
        }
        for i in range(first, first + count)
    }


def ui_graph(count, pad=60):
    """The host's serialized graph: slot-list ``inputs`` and every connection in a top-level link row."""
    nodes = [
        {
            "id": i, "type": f"Step{i}",
            "inputs": [{"name": "x", "type": "X", "link": i - 1}] if i > 1 else [],
            "outputs": [{"name": "out", "type": "X", "links": [i]}] if i < count else [],
            "properties": {"note": "n" * pad},
        }
        for i in range(1, count + 1)
    ]
    links = [[i - 1, i - 1, 0, i, 0, "X"] for i in range(2, count + 1)]
    return {"nodes": nodes, "links": links, "version": 0.4}


def ids_in(output):
    """Node ids of a parsed output, read independently of the implementation."""
    parsed = json.loads(output)
    if isinstance(parsed, dict) and isinstance(parsed.get("nodes"), list):
        return {str(node["id"]) for node in parsed["nodes"]}
    if isinstance(parsed, dict):
        return set(parsed)
    return {str(node["id"]) for node in parsed}


SHAPES = {
    "ui_string": lambda n: json.dumps(ui_graph(n)),
    "ui_dict": lambda n: ui_graph(n),
    "api_string": lambda n: json.dumps(api_prompt(n)),
    "api_dict": lambda n: api_prompt(n),
    "node_list": lambda n: ui_graph(n)["nodes"],
}


# ------------------------------------------------------------------ accepted input shapes
@pytest.mark.parametrize("error_node", [None, "15", "999"])
@pytest.mark.parametrize("shape", list(SHAPES))
def test_every_shape_stays_within_the_budget_and_reports_the_error_node_truthfully(shape, error_node):
    workflow = SHAPES[shape](30)
    original = copy.deepcopy(workflow)
    max_chars = 1800

    output, meta = truncate_workflow_smart(workflow, error_node, max_chars=max_chars)

    assert workflow == original
    assert isinstance(output, str)
    assert len(output) <= max_chars
    assert meta["truncation_method"] != "none"
    assert set(meta) <= CONTRACT_KEYS | {"reason"}
    if meta["truncation_method"] in {"property_pruning", "node_removal"}:
        kept = ids_in(output)
        assert meta["kept_nodes"] == len(kept)
        if error_node is None:
            assert meta["error_node_preserved"] in (None, False)
        else:
            assert meta["error_node_preserved"] is (error_node in kept)


@pytest.mark.parametrize("shape", ["ui_dict", "api_dict", "node_list"])
def test_a_parsed_workflow_over_the_budget_is_truncated_not_passed_through(shape):
    # Before: a dict or list was measured by its key or element count, so it bypassed the budget.
    workflow = SHAPES[shape](29)
    output, meta = truncate_workflow_smart(workflow, "5", max_chars=1500)

    assert meta["truncation_method"] != "none"
    assert len(output) <= 1500
    assert meta["original_length"] == len(json.dumps(workflow, ensure_ascii=False, separators=(",", ":")))


@pytest.mark.parametrize("shape", ["ui_string", "api_string", "ui_dict", "api_dict", "node_list"])
def test_an_input_within_the_budget_is_returned_unchanged(shape):
    workflow = SHAPES[shape](3)

    output, meta = truncate_workflow_smart(workflow, "2", max_chars=4000)

    assert output is workflow
    assert meta["truncation_method"] == "none"
    assert meta["truncated_length"] == meta["original_length"]


def test_a_json_string_of_an_api_prompt_with_an_error_node_does_not_raise():
    # Before: AttributeError ('str' object has no attribute 'get'), reached by /doctor/analyze.
    text = json.dumps(api_prompt(30))

    output, meta = truncate_workflow_smart(text, "7", max_chars=1500)

    assert len(output) <= 1500
    assert meta["truncation_method"] == "node_removal"
    assert {"7", "6", "8"} <= ids_in(output)
    assert meta["error_node_preserved"] is True


def test_the_first_twenty_nodes_of_an_api_prompt_are_selected_by_key_not_position():
    workflow = api_prompt(40, pad=40, first=101)

    output, meta = truncate_workflow_smart(workflow, None, max_chars=3000)

    assert meta["truncation_method"] == "node_removal"
    assert ids_in(output) == {str(i) for i in range(101, 121)}
    assert meta["kept_nodes"] == 20


def test_the_exact_execution_id_is_tried_before_its_last_segment():
    workflow = api_prompt(30)
    workflow["12:3"] = {"class_type": "SubgraphStep", "inputs": {"x": ["29", 0]}, "_meta": {"title": "s" * 60}}

    exact, _ = truncate_workflow_smart(workflow, "12:3", max_chars=1500)
    local, _ = truncate_workflow_smart(workflow, "99:3", max_chars=1500)

    assert "12:3" in ids_in(exact)
    assert "12:3" not in ids_in(local) and "3" in ids_in(local)


def test_an_api_prompt_node_that_is_named_nodes_is_not_mistaken_for_a_graph():
    workflow = api_prompt(6, pad=50)
    workflow["nodes"] = {"class_type": "Holder", "inputs": {}, "_meta": {"title": "h" * 400}}

    output, meta = truncate_workflow_smart(workflow, "3", max_chars=900)

    assert meta["truncation_method"] == "property_pruning"
    parsed = json.loads(output)
    assert parsed["nodes"]["class_type"] == "Holder"
    assert set(parsed) == set(workflow)


# ------------------------------------------------------------------ error_node_preserved
def test_property_pruning_does_not_claim_a_node_the_workflow_does_not_have():
    text = json.dumps(ui_graph(12, pad=300))

    present = truncate_workflow_smart(text, "6", max_chars=4000)[1]
    absent = truncate_workflow_smart(text, "999", max_chars=4000)[1]
    none_given = truncate_workflow_smart(text, None, max_chars=4000)[1]

    assert present["truncation_method"] == absent["truncation_method"] == "property_pruning"
    assert present["error_node_preserved"] is True
    assert absent["error_node_preserved"] is False
    assert none_given["error_node_preserved"] is None


def test_a_character_slice_that_cuts_the_error_node_says_so():
    workflow = api_prompt(10, pad=60)
    workflow["5"]["inputs"]["note"] = "v" * 6000  # trimmed in pruning, but kept whole by node removal

    output, meta = truncate_workflow_smart(workflow, "5", max_chars=1200)

    assert meta["truncation_method"] == "char_slice"
    assert len(output) <= 1200
    assert meta["error_node_preserved"] is False


# ------------------------------------------------------------------ neighborhood hops
def prompt_chain_with_nodes_wrapper(count):
    return {"nodes": [dict(node, id=key) for key, node in api_prompt(count).items()]}


@pytest.mark.parametrize("builder", [ui_graph, api_prompt, prompt_chain_with_nodes_wrapper], ids=["ui", "api", "wrapper"])
def test_the_neighborhood_grows_with_max_hops_up_to_the_whole_chain(builder):
    workflow = builder(11)
    expected = {0: {6}, 1: {5, 6, 7}, 2: {4, 5, 6, 7, 8}, 3: {3, 4, 5, 6, 7, 8, 9}, 20: set(range(1, 12))}

    for hops, ids in expected.items():
        assert _get_priority_nodes(workflow, "6", hops) == {str(i) for i in ids}, hops


def test_a_cycle_terminates_and_keeps_each_node_once():
    cycle = {
        "1": {"class_type": "A", "inputs": {"x": ["3", 0]}},
        "2": {"class_type": "B", "inputs": {"x": ["1", 0]}},
        "3": {"class_type": "C", "inputs": {"x": ["2", 0]}},
        "4": {"class_type": "D", "inputs": {}},
    }

    assert _get_priority_nodes(cycle, "1", 50) == {"1", "2", "3"}


@pytest.mark.parametrize("shape", ["ui_string", "api_string"])
def test_the_kept_nodes_grow_with_the_hop_count_and_a_too_large_neighborhood_degrades(shape):
    workflow = SHAPES[shape](40)

    kept = {}
    for hops in range(4):
        _, meta = truncate_workflow_smart(workflow, "20", max_chars=3000, max_hops=hops)
        assert meta["truncation_method"] == "node_removal", (hops, meta)
        kept[hops] = meta["kept_nodes"]
    assert kept == {0: 1, 1: 3, 2: 5, 3: 7}

    # A budget that fits the one-hop neighborhood but not the two-hop one keeps the one-hop result
    # instead of collapsing into an invalid character slice.
    one_hop = len(truncate_workflow_smart(workflow, "20", max_chars=3000, max_hops=1)[0])
    output, meta = truncate_workflow_smart(workflow, "20", max_chars=one_hop + 5, max_hops=2)
    assert meta["truncation_method"] == "node_removal"
    assert meta["kept_nodes"] == 3
    assert ids_in(output) >= {"19", "20", "21"}


def test_a_two_hundred_node_prompt_stays_within_every_budget():
    workflow = api_prompt(200, pad=80)

    for budget in (1500, 4000, 12000):
        for error_node in (None, "100"):
            output, meta = truncate_workflow_smart(workflow, error_node, max_chars=budget)
            assert len(output) <= budget, (budget, error_node, meta)
            assert meta["kept_nodes"] >= 1


# ------------------------------------------------------------------ malformed input never raises
JUNK = [
    [None, 5, "x", {"id": 1, "inputs": [{"name": "a", "link": 1}]}, {"id": 1}, [], {}],
    {"nodes": {"a": {"id": 1}}, "links": [[1, 2, 3, 4, 5]]},
    {"nodes": "text", "3": {"inputs": {}}},
    {"nodes": [1, None, {"id": "a", "inputs": 5}], "links": "x"},
    {"3": {"class_type": "A", "inputs": {"x": 7}}, "4": 5},
    {"1": {"inputs": None}, "2": {"inputs": [1, 2]}, "3": {"inputs": {"x": [None, 0], "y": [[1]], "z": {}}}},
    {"1": {"class_type": "A", "inputs": {"x": ["1", 0]}}},
    {"nodes": [{"id": None, "inputs": {"x": [None]}}, {"id": 2}, {"id": 2}]},
]


@pytest.mark.parametrize("error_node", [None, "", "1", "2", "x:1", "99", 3])
@pytest.mark.parametrize("junk", range(len(JUNK)))
def test_malformed_workflows_never_raise_and_stay_within_the_budget(junk, error_node):
    workflow = copy.deepcopy(JUNK[junk])
    for padded in (workflow, json.dumps(workflow)):
        output, meta = truncate_workflow_smart(padded, error_node, max_chars=60)
        assert isinstance(meta, dict)
        # Anything within the budget comes back unchanged; anything else is cut to it.
        assert output is padded or len(output) <= 60 + 32


@pytest.mark.parametrize("budget", [0, 1, 10, 49, 50, 79, 80])
def test_a_tiny_budget_never_turns_into_a_negative_slice(budget):
    workflow = api_prompt(30)

    for candidate in (workflow, json.dumps(workflow), "not json " * 50):
        output, _ = truncate_workflow_smart(candidate, "7", max_chars=budget)
        # The cut is at most the budget plus the fixed 32-character marker.
        assert len(output) <= budget + 32, (budget, len(output))


def test_an_unserializable_input_never_raises():
    output, meta = truncate_workflow_smart({"1": {"inputs": {"x": {1, 2}}}}, "1", max_chars=20)

    assert isinstance(meta, dict)


def test_metadata_keys_are_unchanged_for_every_strategy():
    chain = json.dumps(api_prompt(30))
    for budget, error_node in itertools.product((30000, 1800, 120), ("7", None)):
        _, meta = truncate_workflow_smart(chain, error_node, max_chars=budget)
        assert set(meta) <= CONTRACT_KEYS | {"reason"}


# ------------------------------------------------------------------ review follow-ups
@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("error_node", ["999", "12:999", "not-a-node"])
def test_an_error_node_that_is_not_in_the_workflow_keeps_the_first_nodes(shape, error_node):
    # An error id that names no node (a stale error, or a node deleted since) used to select an empty
    # neighborhood, so the over-budget workflow came back as an empty graph; it must behave as if no
    # error node had been named: the first nodes are kept, and the metadata still says it was not found.
    max_chars = 1800
    workflow = SHAPES[shape](30)

    output, meta = truncate_workflow_smart(workflow, error_node, max_chars=max_chars)

    assert len(output) <= max_chars
    assert meta["kept_nodes"] >= 1
    assert "Step1" in output
    assert meta["error_node_preserved"] is False


@pytest.mark.parametrize("max_hops", [-1, -5])
def test_a_negative_hop_count_means_the_error_node_alone(max_hops):
    # Before: the hop range was empty, so the call raised UnboundLocalError (no caller passes it today).
    output, meta = truncate_workflow_smart(api_prompt(30), "7", max_chars=1500, max_hops=max_hops)

    assert meta["error_node_preserved"] is True
    assert ids_in(output) == {"7"}
