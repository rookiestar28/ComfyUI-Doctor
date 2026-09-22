"""Synthetic serialized-workflow contracts; never load host node schemas."""
import asyncio
import copy

import pytest

from services.diagnostics.checks.workflow_lint import (
    _check_disconnected_links,
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
