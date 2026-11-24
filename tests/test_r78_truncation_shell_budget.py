"""A serialized workflow with a heavy non-node member keeps its error node when the nodes alone fit the budget.

``_preserve_workflow_shell`` copied every non-node member (``definitions``, ``extra``, ``groups``, ...) unpruned and
wrote it before ``nodes``. With a few KB of definitions and a 2,000-character budget no neighborhood fit, the
character-slice fallback kept only the start of the text, and the output held no node at all. A reduced-shell pass
now runs only on that path: the nodes and their links come first, then the non-node members that still fit, in their
original order, and the members that were left out are named in an ``_omitted_members`` marker that is part of the
measured text. Every output that fits the budget today is byte-identical.
"""
import copy
import hashlib
import json

import pytest

from truncate_workflow import truncate_workflow_smart

ERROR_ID = "5"


def make_nodes(count=12):
    return [
        {
            "id": index,
            "type": "KSampler" if index % 2 else "CLIPTextEncode",
            "pos": [index * 10, index * 20],
            "size": [315, 262],
            "inputs": [{"name": "model", "type": "MODEL", "link": index - 1 if index > 1 else None}],
            "outputs": [{"name": "OUT", "type": "MODEL", "links": [index]}],
            "widgets_values": [index, "fixed", 20, 8, "euler"],
        }
        for index in range(1, count + 1)
    ]


def make_links(count=12):
    return [[index, index, 0, index + 1, 0, "MODEL"] for index in range(1, count)]


def ui_workflow(definitions_size=6000, count=12, **extra_members):
    workflow = {
        "version": 0.4,
        "definitions": {"subgraphs": [{"id": "sg-1", "name": "x" * definitions_size}]},
        "nodes": make_nodes(count),
        "links": make_links(count),
        "extra": {"ds": {"scale": 1.0}},
        "groups": [{"title": "G", "bounding": [0, 0, 10, 10]}],
    }
    workflow.update(extra_members)
    return workflow


def text_of(workflow):
    return json.dumps(workflow, ensure_ascii=False, separators=(",", ":"))


def run(workflow, error_id=ERROR_ID, max_chars=2000, max_hops=2):
    return truncate_workflow_smart(text_of(workflow), error_id, max_chars=max_chars, max_hops=max_hops)


# The node text in every over-budget result is the pruned one (the same keys the existing node-removal result drops).
PRUNED_KEYS = {"widgets_values", "widgets_values_named", "pos", "size", "order", "mode", "flags", "color", "bgcolor"}


def error_node_text(workflow, node_id=int(ERROR_ID)):
    node = next(node for node in workflow["nodes"] if node["id"] == node_id)
    pruned = {key: value for key, value in node.items() if key not in PRUNED_KEYS}
    return json.dumps(pruned, ensure_ascii=False, separators=(",", ":"))


def digest(result):
    text, meta = result
    payload = json.dumps([text, meta], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Cases whose output fits the budget (or falls through to the character slice) today. They are computed here and
# compared with digests captured at the base, before the reduced-shell pass existed.
def unchanged_cases():
    small_shell = ui_workflow(definitions_size=10)
    api = {str(i): {"class_type": "KSampler", "inputs": {"model": [str(i - 1), 0]} if i > 1 else {}, "pad": "y" * 200}
           for i in range(1, 30)}
    return {
        "fits_whole": (text_of(ui_workflow(definitions_size=10, count=2)), ERROR_ID, 20000, 2),
        "property_pruning": (text_of(small_shell), ERROR_ID, 2400, 2),
        "node_removal_with_full_shell": (text_of(small_shell), ERROR_ID, 1500, 2),
        "node_removal_degraded_hops": (text_of(small_shell), ERROR_ID, 900, 2),
        "no_error_id": (text_of(small_shell), None, 1500, 2),
        "api_format_over_budget": (text_of(api), "7", 1200, 2),
        "invalid_json": ("{not json" + "z" * 5000, ERROR_ID, 800, 2),
        "api_format_nothing_fits": (text_of(api), "7", 150, 2),
        "ui_heavy_shell_nothing_fits": (text_of(ui_workflow()), ERROR_ID, 150, 2),
        "no_shell_members_nodes_over_budget": (
            text_of({"nodes": [dict(node, note="n" * 400) for node in make_nodes(6)], "links": make_links(6)}),
            ERROR_ID, 150, 2),
    }


GOLDEN = {  # captured at the base, before the reduced-shell pass existed (r78-golden-digests-at-base.txt)
    "api_format_nothing_fits": (
        "c0746f967bab2d1394bee7c4d3f22948feb89c838eb00641e4d28ca8eedf6e6f"  # pragma: allowlist secret
    ),
    "ui_heavy_shell_nothing_fits": (
        "7ce5594b44f52a9cb67a508e6bd446c4ea3b1ed976e4b3565f1bf5e67b54613c"  # pragma: allowlist secret
    ),
    "api_format_over_budget": (
        "b35e79b885d034fc9bd02858a0491d4d5d4b97cc470b2cccc88c1911e332368b"  # pragma: allowlist secret
    ),
    "fits_whole": (
        "0917ab22a445476eb089ca02650e8b17e76520b78b3f715261e2edc67b2ff1a9"  # pragma: allowlist secret
    ),
    "invalid_json": (
        "a79df098eb4f9d539483634228e9d62a6deb258894eea8d911c0a8ebd0a44fd3"  # pragma: allowlist secret
    ),
    "no_error_id": (
        "06ee9c5e5e82009f452bcc3c192b36fddb4b204958e63703b57085820f55721c"  # pragma: allowlist secret
    ),
    "no_shell_members_nodes_over_budget": (
        "9a31ac0d5e205d36f1aa91ec61c97699907b7f021f68cca126a995f6d0fe4ea0"  # pragma: allowlist secret
    ),
    "node_removal_degraded_hops": (
        "2acbb1ac7539fc501e1dfb88ca0d14dee779559e3065f1ba3a9528a281fc51d7"  # pragma: allowlist secret
    ),
    "node_removal_with_full_shell": (
        "15a02741e2d7bf4a8a6f07c330851dc43a2d54f15fe767822c05b0f7152d6ff4"  # pragma: allowlist secret
    ),
    "property_pruning": (
        "1f5eaa5c4ec2386eaf75c89419c4ff105870dd56aa5f3d97646123e49d43a979"  # pragma: allowlist secret
    ),
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_outputs_that_do_not_need_the_reduced_shell_are_byte_identical(name):
    text, error_id, max_chars, hops = unchanged_cases()[name]

    assert digest(truncate_workflow_smart(text, error_id, max_chars=max_chars, max_hops=hops)) == GOLDEN[name]


# ------------------------------------------------------------------------------------------------ the fix
def test_a_heavy_shell_no_longer_costs_the_error_node():
    workflow = ui_workflow()
    text, meta = run(workflow)

    assert len(text) <= 2000
    parsed = json.loads(text)
    assert error_node_text(workflow) in text
    assert any(node["id"] == int(ERROR_ID) for node in parsed["nodes"])
    assert meta["error_node_preserved"] is True
    assert meta["truncation_method"] == "node_removal"
    assert meta["truncated_length"] == len(text)
    assert meta["omitted_members"] == ["definitions"]
    assert parsed["_omitted_members"] == ["definitions"]
    assert "definitions" not in parsed


def test_the_nodes_come_first_and_the_small_members_that_fit_keep_their_original_order():
    workflow = ui_workflow()
    text, _ = run(workflow)
    parsed = json.loads(text)

    assert list(parsed) == ["nodes", "links", "version", "extra", "groups", "_omitted_members"]
    assert parsed["version"] == 0.4
    assert parsed["extra"] == workflow["extra"]
    assert parsed["groups"] == workflow["groups"]


def test_a_member_is_kept_only_when_the_whole_output_still_fits():
    # `alpha` and `beta` are each too big to keep together: the full shell does not fit at any hop count, so the
    # existing hop loop cannot help and the reduced pass runs. `alpha` is earlier and fits, `beta` does not fit
    # after it, and the small `gamma` after `beta` still fits: a member that does not fit is skipped, not a stop.
    workflow = ui_workflow(definitions_size=10, alpha="a" * 1100, beta="b" * 1100, gamma="g" * 10)
    text, meta = run(workflow, max_chars=2200)
    parsed = json.loads(text)

    assert len(text) <= 2200
    assert list(parsed) == ["nodes", "links", "version", "definitions", "extra", "groups", "alpha", "gamma", "_omitted_members"]
    assert meta["omitted_members"] == ["beta"] == parsed["_omitted_members"]
    assert meta["error_node_preserved"] is True


def test_every_budget_keeps_the_output_within_the_limit_and_the_flag_matches_the_text():
    workflow = ui_workflow()
    needle = error_node_text(workflow)
    reduced = 0
    for max_chars in range(150, 3200, 41):
        text, meta = run(workflow, max_chars=max_chars)
        if "omitted_members" in meta:
            reduced += 1
            assert len(text) <= max_chars, max_chars
            json.loads(text)
            assert json.loads(text)["_omitted_members"] == meta["omitted_members"]
        # The flag is exactly "the node text is in the output".
        assert meta["error_node_preserved"] is (needle in text), max_chars
    assert reduced > 5


def test_a_tight_budget_degrades_the_neighborhood_before_giving_up_on_the_shell():
    workflow = ui_workflow()
    wide_text, wide_meta = run(workflow, max_chars=2000, max_hops=2)
    narrow_text, narrow_meta = run(workflow, max_chars=2000, max_hops=0)

    assert wide_meta["kept_nodes"] >= narrow_meta["kept_nodes"] == 1
    assert json.loads(narrow_text)["nodes"][0]["id"] == int(ERROR_ID)
    # A very small budget keeps only what fits: the hop count shrinks, the error node stays.
    tiny_text, tiny_meta = run(workflow, max_chars=700, max_hops=2)
    assert len(tiny_text) <= 700 and tiny_meta["error_node_preserved"] is True
    assert tiny_meta["kept_nodes"] < wide_meta["kept_nodes"]


def test_the_links_of_the_kept_nodes_stay_and_the_others_are_dropped():
    workflow = ui_workflow()
    text, meta = run(workflow, max_hops=1)
    parsed = json.loads(text)
    kept = {node["id"] for node in parsed["nodes"]}

    assert kept == {4, 5, 6}
    assert all(row[1] in kept and row[3] in kept for row in parsed["links"])
    assert len(parsed["links"]) == 2
    assert meta["kept_nodes"] == 3


def test_an_execution_id_names_the_node_by_its_last_segment():
    workflow = ui_workflow()
    text, meta = run(workflow, error_id="12:5")

    assert meta["error_node_preserved"] is True
    assert error_node_text(workflow) in text


def test_an_error_id_that_is_not_in_the_workflow_keeps_the_first_nodes_and_reports_it_missing():
    workflow = ui_workflow()
    text, meta = run(workflow, error_id="999")
    parsed = json.loads(text)

    assert meta["error_node_preserved"] is False
    assert parsed["nodes"] and parsed["nodes"][0]["id"] == 1
    assert len(text) <= 2000


def test_a_member_that_is_called_like_the_marker_is_replaced_by_the_marker():
    workflow = ui_workflow(_omitted_members=["from-the-file"])
    text, meta = run(workflow)
    parsed = json.loads(text)

    assert parsed["_omitted_members"] == meta["omitted_members"]
    assert "from-the-file" not in text
    assert "_omitted_members" in meta["omitted_members"]
    assert text.count('"_omitted_members":') == 1


def test_the_input_is_not_modified():
    workflow = ui_workflow()
    before = copy.deepcopy(workflow)
    run(workflow)

    assert workflow == before


def test_when_even_the_error_node_alone_does_not_fit_the_old_fallback_runs_unchanged():
    # Nodes alone are over the budget and no member could be dropped to help: nothing for the new pass to do.
    text, error_id, max_chars, hops = unchanged_cases()["no_shell_members_nodes_over_budget"]
    result_text, meta = truncate_workflow_smart(text, error_id, max_chars=max_chars, max_hops=hops)

    assert meta["truncation_method"] == "char_slice"
    assert "omitted_members" not in meta
    assert len(result_text) <= max_chars + 30


def expected_kept_nodes(workflow, max_chars, max_hops=2):
    """Independent oracle: the widest neighborhood whose nodes, links and a full marker fit, by this test's own sums."""
    names = [key for key in workflow if key not in {"nodes", "links"}]
    error_id = int(ERROR_ID)
    for hops in range(max_hops, -1, -1):
        ids = {index for index in range(error_id - hops, error_id + hops + 1) if 1 <= index <= len(workflow["nodes"])}
        nodes = [
            {key: value for key, value in node.items() if key not in PRUNED_KEYS}
            for node in workflow["nodes"] if node["id"] in ids
        ]
        links = [row for row in workflow["links"] if row[1] in ids and row[3] in ids]
        if len(text_of({"nodes": nodes, "links": links, "_omitted_members": names})) <= max_chars:
            return len(nodes)
    return None


def test_every_single_budget_keeps_exactly_the_widest_neighborhood_that_fits_with_its_marker():
    workflow = ui_workflow()
    outcomes = {"reduced": 0, "fallback": 0}
    for max_chars in range(150, 3300):
        text, meta = run(workflow, max_chars=max_chars)
        expected = expected_kept_nodes(workflow, max_chars)
        if expected is None:
            outcomes["fallback"] += 1
            assert "omitted_members" not in meta, max_chars
            continue
        outcomes["reduced"] += 1
        assert meta["kept_nodes"] == expected, max_chars
        assert meta["truncation_method"] == "node_removal" and len(text) <= max_chars, max_chars
        assert meta["error_node_preserved"] is True, max_chars
    assert outcomes["reduced"] > 2000 and outcomes["fallback"] > 20
