"""Synthetic serialized-workflow contracts; never load host node schemas."""
import asyncio
import copy

import pytest

from services.diagnostics.checks.workflow_lint import (
    HOST_OPTIONAL_SLOT_SHAPE,
    _check_disconnected_links,
    _is_host_optional_slot,
    check_workflow_lint,
)
from services.diagnostics.models import HealthCheckRequest, HealthReport, IssueSeverity

SWITCHES = ("ComfySwitchNode", "ComfySoftSwitchNode")
BRANCHES = ("on_true", "on_false")
TYPES = ("MODEL", "CLIP", "VAE", "LATENT", "CONDITIONING")


def workflow(node_type, name, input_type, link=None, *, omit_link=False):
    inp = {"name": name, "type": input_type}
    if not omit_link:
        inp["link"] = link
    return {"nodes": [{"id": 1, "type": node_type, "inputs": [inp]}], "links": []}


def diagnose(value):
    return asyncio.run(check_workflow_lint(value, HealthCheckRequest(workflow=value)))


@pytest.mark.parametrize("node_type", SWITCHES)
@pytest.mark.parametrize("branch", BRANCHES)
@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("omit_link", (False, True))
def test_optional_switch_branch_has_no_false_warning_or_score_penalty(
    node_type, branch, input_type, omit_link
):
    value = workflow(node_type, branch, input_type, omit_link=omit_link)
    original = copy.deepcopy(value)
    assert _check_disconnected_links({1: value["nodes"][0]}, {}) == []
    issues = diagnose(value)
    assert issues == []
    assert HealthReport.compute_health_score(issues) == 100
    assert value == original


@pytest.mark.parametrize("node_type", SWITCHES)
@pytest.mark.parametrize("branch", BRANCHES)
@pytest.mark.parametrize("link", (0, 7))
def test_optional_switch_dangling_link_retains_critical_issue(node_type, branch, link):
    value = workflow(node_type, branch, "MODEL", link)
    issues = diagnose(value)
    control = diagnose(workflow("KSampler", branch, "MODEL", link))
    assert len(issues) == 1
    assert issues[0].title == "Broken Link Reference"
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].target.node_id == 1
    assert issues[0].issue_id == control[0].issue_id
    assert HealthReport.compute_health_score(issues) == 70


@pytest.mark.parametrize("node_type,name", (
    ("KSampler", "model"),
    ("CustomComfySwitchNode", "on_true"),
    ("ComfySwitchNodeCustom", "on_false"),
    ("comfyswitchnode", "on_true"),
    ("ComfySwitchNode", "model"),
    ("ComfySwitchNode", "On_true"),
    ("ComfySoftSwitchNode", "on_other"),
))
@pytest.mark.parametrize("input_type", TYPES)
def test_required_inputs_and_unverified_optional_flags_keep_existing_warning(node_type, name, input_type):
    value = workflow(node_type, name, input_type)
    value["nodes"][0]["inputs"][0]["optional"] = True
    issues = diagnose(value)
    expected_unknown = node_type not in SWITCHES + ("KSampler",)
    assert [issue.title for issue in issues] == ["Disconnected Required Input"] + (
        ["Unknown Node Type"] if expected_unknown else []
    )
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].target.node_id == 1
    assert HealthReport.compute_health_score(issues) == (88 if expected_unknown else 90)


@pytest.mark.parametrize("node_type", SWITCHES + ("KSampler",))
@pytest.mark.parametrize("input_type", TYPES + ("*",))
def test_valid_connections_remain_clean(node_type, input_type):
    value = workflow(node_type, "on_true", input_type, 7)
    value["links"] = [[7, 2, 0, 1, 0, input_type]]
    value["nodes"].append({"id": 2, "type": "CheckpointLoaderSimple"})
    original = copy.deepcopy(value)
    assert diagnose(value) == []
    assert value == original


def test_mixed_report_removes_only_optional_false_positive():
    value = workflow("ComfySwitchNode", "on_true", "MODEL")
    value["nodes"].append({"id": 2, "type": "KSampler", "inputs": [
        {"name": "model", "type": "MODEL", "link": None},
    ]})
    issues = diagnose(value)
    assert len(issues) == 1
    assert issues[0].target.node_id == 2
    assert HealthReport.compute_health_score(issues) == 90


def test_unconnected_wildcard_remains_clean():
    assert diagnose(workflow("ComfySwitchNode", "on_false", "*")) == []


@pytest.mark.parametrize("index", range(32))
@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("omit_link", (False, True))
@pytest.mark.parametrize("node_id", (9, "insert:synthetic:node:9"))
def test_optional_branch_autogrow_has_no_false_issue_or_score_penalty(index, input_type, omit_link, node_id):
    value = workflow("BranchNode", f"autogrow.branch{index}", input_type, omit_link=omit_link)
    value["nodes"][0]["id"] = node_id
    original = copy.deepcopy(value)
    issues = diagnose(value)
    assert issues == []
    assert HealthReport.compute_health_score(issues) == 100
    assert value == original


@pytest.mark.parametrize("index", range(32))
@pytest.mark.parametrize("link", (0, 7))
@pytest.mark.parametrize("node_id", (9, "insert:synthetic:node:9"))
def test_branch_dangling_link_is_still_critical_with_exact_target(index, link, node_id):
    value = workflow("BranchNode", f"autogrow.branch{index}", "MODEL", link)
    value["nodes"][0]["id"] = node_id
    original = copy.deepcopy(value)
    issues = diagnose(value)
    assert len(issues) == 1
    assert issues[0].title == "Broken Link Reference"
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].target.node_id == node_id
    assert type(issues[0].target.node_id) is type(node_id)
    assert HealthReport.compute_health_score(issues) == 70
    assert value == original


@pytest.mark.parametrize("name", (
    "model", "branch0", "autogrow.branch", "autogrow.branch-1", "autogrow.branch32",
    "autogrow.branch00", "autogrow.branch01", "autogrow.branch1suffix", "autogrow.branch1.foo",
    "autogrow.branch1 ", "Autogrow.branch1", "autogrow.Branch0", "autogrow.branch１",
))
@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("node_id", (9, "insert:synthetic:node:9"))
def test_branch_exception_cannot_hide_required_or_deceptive_input(name, input_type, node_id):
    value = workflow("BranchNode", name, input_type)
    value["nodes"][0]["id"] = node_id
    original = copy.deepcopy(value)
    issues = diagnose(value)
    assert [issue.title for issue in issues] == ["Disconnected Required Input"]
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].target.node_id == node_id
    assert HealthReport.compute_health_score(issues) == 90
    assert value == original


@pytest.mark.parametrize("node_type", ("CustomBranchNode", "BranchNodeCustom", "branchnode", "Branch"))
@pytest.mark.parametrize("input_type", TYPES)
def test_custom_branch_names_do_not_inherit_core_optionality(node_type, input_type):
    value = workflow(node_type, "autogrow.branch0", input_type)
    issues = diagnose(value)
    assert [issue.title for issue in issues] == ["Disconnected Required Input", "Unknown Node Type"]
    assert HealthReport.compute_health_score(issues) == 88


@pytest.mark.parametrize("index", range(32))
@pytest.mark.parametrize("node_id", (9, "insert:synthetic:node:9"))
def test_connected_branch_inputs_remain_clean(index, node_id):
    value = workflow("BranchNode", f"autogrow.branch{index}", "MODEL", 7)
    value["nodes"][0]["id"] = node_id
    value["nodes"].append({"id": 2, "type": "CheckpointLoaderSimple"})
    value["links"] = [[7, 2, 0, node_id, 0, "MODEL"]]
    original = copy.deepcopy(value)
    assert diagnose(value) == []
    assert value == original


def test_mixed_branch_switch_and_required_node_keep_only_real_warning():
    value = workflow("BranchNode", "autogrow.branch31", "MODEL")
    value["nodes"].extend([
        {"id": 2, "type": "ComfySoftSwitchNode", "inputs": [
            {"name": "on_false", "type": "MODEL", "link": None},
        ]},
        {"id": "insert:synthetic:node:9", "type": "KSampler", "inputs": [
            {"name": "model", "type": "MODEL", "link": None},
        ]},
    ])
    original = copy.deepcopy(value)
    issues = diagnose(value)
    assert [(issue.title, issue.target.node_id) for issue in issues] == [
        ("Disconnected Required Input", "insert:synthetic:node:9"),
    ]
    assert HealthReport.compute_health_score(issues) == 90
    assert value == original


# ---- Host-declared optional slots: the host serializes an optional input as `shape: 7` (RenderShape.HollowCircle) ----
# The literal 7 is repeated on purpose so a wrong edit of the production constant cannot silently move this contract.
HOST_MARKER = 7
OPAQUE_NODE_ID = "insert:insert-workflow-op-id-padded-to-32c:root:node:9"
HOST_OPTIONAL_NODES = (
    ("ControlNetApplyAdvanced", False),  # core node known to Doctor
    ("MiniMaxH3ImageConditioning", True),  # new first-party node, unknown to Doctor's list
    ("SomeCustomNode", True),  # custom node
)
NON_MARKER_SHAPES = (0, 1, 2, 3, 6, 8, 70, -7, "7", 7.0, True, False, None, [7], {"shape": 7})
ABSENT = object()


def slot(name, input_type, link=None, **extra):
    return {"name": name, "type": input_type, "link": link, **extra}


def shaped(node_type, inputs, node_id=1):
    return {"nodes": [{"id": node_id, "type": node_type, "inputs": inputs}], "links": []}


def titles(issues):
    return [issue.title for issue in issues]


@pytest.mark.parametrize("node_type,unknown", HOST_OPTIONAL_NODES)
@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("node_id", (1, OPAQUE_NODE_ID))
def test_host_declared_optional_slot_has_no_false_warning_or_score_penalty(node_type, unknown, input_type, node_id):
    value = shaped(node_type, [slot("vae", input_type, shape=HOST_MARKER)], node_id)
    clean = shaped(node_type, [], node_id)
    original = copy.deepcopy(value)
    issues = diagnose(value)
    expected = diagnose(clean)
    assert "Disconnected Required Input" not in titles(issues)
    assert titles(issues) == titles(expected)
    assert HealthReport.compute_health_score(issues) == HealthReport.compute_health_score(expected)
    assert value == original


@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("shape", (ABSENT,) + NON_MARKER_SHAPES, ids=repr)
def test_only_the_exact_integer_marker_exempts_a_null_link_slot(shape, input_type):
    extra = {} if shape is ABSENT else {"shape": shape}
    issues = diagnose(shaped("ControlNetApplyAdvanced", [slot("vae", input_type, **extra)]))
    assert titles(issues) == ["Disconnected Required Input"]
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].target.node_id == 1
    assert HealthReport.compute_health_score(issues) == 90


def test_mixed_optional_and_required_slots_warn_only_for_the_required_slot():
    value = shaped("ControlNetApplyAdvanced", [slot("vae", "VAE", shape=HOST_MARKER), slot("model", "MODEL")])
    original = copy.deepcopy(value)
    issues = diagnose(value)
    control = diagnose(shaped("ControlNetApplyAdvanced", [slot("model", "MODEL")]))
    assert titles(issues) == ["Disconnected Required Input"]
    assert "'model'" in issues[0].summary and "'vae'" not in issues[0].summary
    assert issues[0].target.node_id == 1
    assert issues[0].issue_id == control[0].issue_id
    assert HealthReport.compute_health_score(issues) == 90
    assert value == original


@pytest.mark.parametrize("input_type", TYPES)
@pytest.mark.parametrize("link", (0, 99))
def test_broken_link_on_a_host_optional_slot_still_reports_a_broken_reference(input_type, link):
    issues = diagnose(shaped("ControlNetApplyAdvanced", [slot("vae", input_type, link, shape=HOST_MARKER)]))
    expected = diagnose(shaped("ControlNetApplyAdvanced", [slot("vae", input_type, link)]))
    assert titles(issues) == ["Broken Link Reference"]
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert [issue.issue_id for issue in issues] == [issue.issue_id for issue in expected]
    assert HealthReport.compute_health_score(issues) == HealthReport.compute_health_score(expected) == 70


def test_connected_host_optional_slot_stays_clean():
    value = shaped("ControlNetApplyAdvanced", [slot("vae", "VAE", 7, shape=HOST_MARKER)])
    value["links"] = [[7, 2, 0, 1, 0, "VAE"]]
    value["nodes"].append({"id": 2, "type": "CheckpointLoaderSimple"})
    original = copy.deepcopy(value)
    assert diagnose(value) == []
    assert value == original


@pytest.mark.parametrize("with_marker", (False, True))
def test_switch_and_branch_exemptions_do_not_depend_on_the_marker(with_marker):
    extra = {"shape": HOST_MARKER} if with_marker else {}
    value = {"nodes": [
        {"id": 1, "type": "ComfySwitchNode", "inputs": [slot("on_true", "MODEL", **extra)]},
        {"id": 2, "type": "BranchNode", "inputs": [slot("autogrow.branch31", "VAE", **extra)]},
    ], "links": []}
    assert diagnose(value) == []


def test_out_of_range_branch_name_is_exempt_only_with_the_host_marker():
    unmarked = diagnose(shaped("BranchNode", [slot("autogrow.branch32", "MODEL")]))
    marked = diagnose(shaped("BranchNode", [slot("autogrow.branch32", "MODEL", shape=HOST_MARKER)]))
    assert titles(unmarked) == ["Disconnected Required Input"]
    assert marked == []


def test_marker_boundary_helper_accepts_only_the_exact_integer():
    assert HOST_OPTIONAL_SLOT_SHAPE == HOST_MARKER
    assert _is_host_optional_slot({"shape": HOST_MARKER}) is True
    for bad in NON_MARKER_SHAPES:
        assert _is_host_optional_slot({"shape": bad}) is False, repr(bad)
    assert _is_host_optional_slot({}) is False
    assert _is_host_optional_slot(None) is False
    assert _is_host_optional_slot("shape") is False
