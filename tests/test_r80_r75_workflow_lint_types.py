"""Workflow lint tolerates odd field types (R80) and does not flag subgraph instances as unknown (R75).

R80: one node with an odd field must not abort the whole check (the diagnostics runner swallows the exception
per check, so every finding of the run would be lost). The odd field is skipped for its own node, input or
link entry; the sibling findings and their issue ids stay exactly as they are.

R75: a node whose type names a subgraph defined in the same workflow, or a legacy ``workflow>`` group node,
is an instance, not an unknown node type. An undefined uuid type and a plain unknown name stay flagged.
"""

import asyncio
import copy

import pytest

from services.diagnostics.checks.workflow_lint import check_workflow_lint
from services.diagnostics.models import HealthCheckRequest, IssueSeverity

INF = float("inf")
NAN = float("nan")
SUBGRAPH_ID = "11111111-2222-3333-4444-555555555555"
OTHER_ID = "99999999-8888-7777-6666-555555555555"

# A valid node with exactly one finding ("Very High Step Count"): the sibling that must survive every odd field.
SIBLING = {"id": 1, "type": "KSampler", "inputs": [], "widgets_values": [1, "fixed", 500, 8.0, "euler", "normal", 1.0]}
SIBLING_TITLES = ["Very High Step Count"]


def diagnose(value):
    return asyncio.run(check_workflow_lint(value, HealthCheckRequest(workflow=value)))


def titles(issues):
    return sorted(issue.title for issue in issues)


def fingerprint(issue):
    return (issue.issue_id, issue.title, issue.severity, issue.summary)


def sibling_issues():
    return diagnose({"nodes": [copy.deepcopy(SIBLING)], "links": []})


def with_sibling(extra_node, links=None):
    return {"nodes": [copy.deepcopy(SIBLING), extra_node], "links": links or []}


def assert_sibling_kept(issues):
    expected = [fingerprint(issue) for issue in sibling_issues()]
    kept = [fingerprint(issue) for issue in issues if issue.target.node_id == 1]
    assert kept == expected


# ---------------------------------------------------------------------------------------------------- R80

@pytest.mark.parametrize("properties", [None, [], "text", 5], ids=["null", "list", "string", "number"])
def test_properties_that_is_not_a_dict_is_skipped_for_that_node_alone(properties):
    value = with_sibling({"id": 3, "type": "Foo", "inputs": [], "properties": properties})
    original = copy.deepcopy(value)
    issues = diagnose(value)
    assert_sibling_kept(issues)
    # The odd node keeps the finding it would have with empty properties.
    assert titles(issues) == sorted(SIBLING_TITLES + ["Unknown Node Type"])
    assert value == original


def test_a_dict_properties_still_marks_a_missing_node():
    issues = diagnose(with_sibling({"id": 3, "type": "Foo", "inputs": [], "properties": {"missing_node": True}}))
    assert "Missing Custom Node" in titles(issues)


@pytest.mark.parametrize("value", [INF, -INF, NAN], ids=["inf", "-inf", "nan"])
def test_a_non_finite_latent_widget_is_skipped_for_that_node_alone(value):
    widgets = [value, 512, 1]
    odd = diagnose(with_sibling({"id": 4, "type": "EmptyLatentImage", "inputs": [], "widgets_values": widgets}))
    assert_sibling_kept(odd)
    # The latent check skips the non-finite entry (width 512 and batch 1 raise nothing). Only the generic
    # "large value" check, which never converted the number to an integer, may speak about +Infinity.
    expected = ["Unusually Large Parameter Value"] if value == INF else []
    assert titles([issue for issue in odd if issue.target.node_id == 4]) == expected


def test_a_non_finite_latent_widget_does_not_hide_the_other_widgets_of_its_node():
    issues = diagnose(with_sibling({"id": 4, "type": "EmptyLatentImage", "inputs": [], "widgets_values": [NAN, 8192, 8192, 1]}))
    assert_sibling_kept(issues)
    assert any(issue.title == "Very High Resolution Width" and issue.target.node_id == 4 for issue in issues)


@pytest.mark.parametrize("link", [[1], {"a": 1}], ids=["list", "dict"])
def test_an_input_link_that_is_not_hashable_is_skipped_for_that_input_alone(link):
    node = {
        "id": 5, "type": "Foo",
        "inputs": [{"name": "x", "type": "IMAGE", "link": link}, {"name": "model", "type": "MODEL", "link": None}],
    }
    issues = diagnose(with_sibling(node))
    assert_sibling_kept(issues)
    # The odd input is skipped; the other input of the same node is still checked.
    assert titles(issues) == sorted(SIBLING_TITLES + ["Disconnected Required Input", "Unknown Node Type"])


@pytest.mark.parametrize("input_type", [["MODEL"], {"a": 1}], ids=["list", "dict"])
def test_an_input_type_that_is_not_hashable_is_skipped_for_that_input_alone(input_type):
    node = {
        "id": 5, "type": "Foo",
        "inputs": [{"name": "x", "type": input_type, "link": None}, {"name": "model", "type": "MODEL", "link": None}],
    }
    issues = diagnose(with_sibling(node))
    assert_sibling_kept(issues)
    assert titles(issues) == sorted(SIBLING_TITLES + ["Disconnected Required Input", "Unknown Node Type"])


@pytest.mark.parametrize("link_id", [[1], {"a": 1}], ids=["list", "dict"])
def test_a_links_entry_with_an_unhashable_id_is_skipped_for_that_entry_alone(link_id):
    node = {"id": 6, "type": "KSampler", "inputs": [{"name": "model", "type": "MODEL", "link": 5}]}
    links = [[link_id, 1, 0, 6, 0, "MODEL"], [5, 1, 0, 6, 0, "MODEL"]]
    issues = diagnose(with_sibling(node, links))
    assert_sibling_kept(issues)
    # The valid link after the odd entry is still recorded, so input link 5 is not reported as broken.
    assert "Broken Link Reference" not in titles(issues)


def test_known_nodes_with_odd_properties_still_lint_cleanly():
    issues = diagnose(with_sibling({"id": 3, "type": "KSampler", "inputs": [], "properties": None}))
    assert_sibling_kept(issues)
    assert titles(issues) == SIBLING_TITLES


# ---------------------------------------------------------------------------------------------------- R75

def unknown_types(issues):
    return [issue for issue in issues if issue.title == "Unknown Node Type"]


def defined(*ids):
    return {"subgraphs": [{"id": sid, "name": "S", "nodes": [], "links": []} for sid in ids]}


def instance(node_type, node_id=1):
    return {"id": node_id, "type": node_type, "inputs": []}


def test_an_instance_of_a_subgraph_defined_in_the_workflow_is_not_unknown():
    value = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": defined(SUBGRAPH_ID)}
    original = copy.deepcopy(value)
    assert unknown_types(diagnose(value)) == []
    assert value == original


def test_an_instance_of_a_subgraph_defined_inside_a_nested_definition_is_not_unknown():
    inner = {"id": SUBGRAPH_ID, "name": "inner", "nodes": [], "links": []}
    outer = {"id": OTHER_ID, "name": "outer", "nodes": [], "links": [], "definitions": {"subgraphs": [inner]}}
    value = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": {"subgraphs": [outer]}}
    assert unknown_types(diagnose(value)) == []


def test_a_group_node_type_is_not_unknown():
    value = {"nodes": [instance("workflow>My Group")], "links": []}
    assert unknown_types(diagnose(value)) == []


def test_an_undefined_uuid_type_is_still_flagged_with_the_same_finding():
    control = diagnose({"nodes": [instance(SUBGRAPH_ID)], "links": []})
    # A definition with another id must not hide it.
    with_other = diagnose({"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": defined(OTHER_ID)})
    assert [fingerprint(i) for i in unknown_types(with_other)] == [fingerprint(i) for i in unknown_types(control)]
    assert len(unknown_types(with_other)) == 1
    assert unknown_types(with_other)[0].severity == IssueSeverity.INFO
    assert unknown_types(with_other)[0].title == "Unknown Node Type"


def test_a_plain_unknown_name_is_still_flagged_with_the_same_finding():
    control = diagnose({"nodes": [instance("TotallyUnknownThing")], "links": []})
    with_defs = diagnose({"nodes": [instance("TotallyUnknownThing")], "links": [], "definitions": defined(SUBGRAPH_ID)})
    assert [fingerprint(i) for i in unknown_types(with_defs)] == [fingerprint(i) for i in unknown_types(control)]
    assert len(unknown_types(with_defs)) == 1


def test_a_type_that_only_looks_like_the_group_convention_is_still_flagged():
    for node_type in ("Workflow>My Group", "my workflow>x", " workflow>x"):
        assert len(unknown_types(diagnose({"nodes": [instance(node_type)], "links": []}))) == 1, node_type


@pytest.mark.parametrize(
    "definitions",
    [
        None, [], "x", 5,
        {"subgraphs": None}, {"subgraphs": "x"}, {"subgraphs": {"id": SUBGRAPH_ID}},
        {"subgraphs": [None, 5, "x", [SUBGRAPH_ID]]},
        {"subgraphs": [{"id": 5}, {"id": ["x"]}, {"id": {"a": 1}}, {"id": ""}, {"id": None}, {}]},
        {"subgraphs": [{"id": OTHER_ID, "definitions": {"subgraphs": [None, {"id": 7}]}}]},
    ],
    ids=lambda value: type(value).__name__,
)
def test_odd_definition_shapes_never_raise_and_never_hide_a_real_unknown_type(definitions):
    value = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": definitions}
    assert len(unknown_types(diagnose(value))) == 1


def test_a_definition_nested_too_deep_is_not_recognized_but_nothing_breaks():
    def wrapped(depth):
        node = {"id": SUBGRAPH_ID}
        for level in range(depth):
            node = {"id": f"wrapper-{level}", "definitions": {"subgraphs": [node]}}
        return {"subgraphs": [node]}

    shallow = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": wrapped(3)}
    deep = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": wrapped(60)}
    assert unknown_types(diagnose(shallow)) == []
    # Past the walk limit the type is not recognized and keeps its finding (the old behavior), never a crash.
    assert len(unknown_types(diagnose(deep))) == 1


def test_a_very_large_definition_list_is_bounded():
    many = [{"id": f"filler-{index}"} for index in range(2500)]
    first = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": {"subgraphs": [{"id": SUBGRAPH_ID}] + many}}
    last = {"nodes": [instance(SUBGRAPH_ID)], "links": [], "definitions": {"subgraphs": many + [{"id": SUBGRAPH_ID}]}}
    assert unknown_types(diagnose(first)) == []
    assert len(unknown_types(diagnose(last))) == 1


def test_the_collector_and_matcher_are_pure_and_total():
    from services.diagnostics.known_nodes import collect_workflow_local_node_types, is_workflow_local_node_type

    assert collect_workflow_local_node_types({"definitions": defined("a", "b")}) == frozenset({"a", "b"})
    assert collect_workflow_local_node_types(None) == frozenset()
    assert collect_workflow_local_node_types([]) == frozenset()
    assert collect_workflow_local_node_types({"definitions": {"subgraphs": [{"id": "a"}, {"id": 3}, 4]}}) == frozenset({"a"})
    local = frozenset({"a"})
    assert is_workflow_local_node_type("a", local) is True
    assert is_workflow_local_node_type("workflow>Group", frozenset()) is True
    assert is_workflow_local_node_type("b", local) is False
    for bad in (None, 5, [], {}, "", ["a"]):
        assert is_workflow_local_node_type(bad, local) is False
