"""Intent signals keep node ids exactly and never act on an id that is not valid.

The signal extractor used to coerce every digit-looking id with ``int(...)``: ``"09"`` became 9, Arabic-Indic
digits collapsed onto ASCII ids, ``"²"`` made ``int()`` raise (the node silently vanished from the signal), and a
link endpoint such as ``"٩"`` resolved to the node with id 9. A link endpoint that is a list crashed the whole
extraction. Ids are now the exact valid scalars; an invalid id is skipped on its own.
"""
import hashlib
import json

import pytest

from services.intent import SignalExtractor

# Digest of the signals for the valid-id workflows below, captured before the change.
GOLDEN_TXT2IMG = "51d56fe1e3bc52f35e204fcefc380863e88c1a46a4c493aebcea2ffa5e48aa92"  # pragma: allowlist secret
GOLDEN_IMG2IMG = "dee8ba2b9e4318f30756a65c1248fbf90b982b1851e15f4e1ad45b7acef1b679"  # pragma: allowlist secret

TXT2IMG = {
    "nodes": [
        {"id": 1, "type": "KSampler"},
        {"id": 2, "type": "CLIPTextEncode"},
        {"id": 3, "type": "EmptyLatentImage"},
        {"id": 4, "type": "VAEDecode"},
        {"id": 5, "type": "SaveImage"},
    ],
    "links": [
        [1, 3, 0, 1, 3, "LATENT"],
        [2, 2, 0, 1, 1, "CONDITIONING"],
        [3, 1, 0, 4, 0, "LATENT"],
    ],
}
IMG2IMG = {
    "nodes": [
        {"id": 1, "type": "KSampler"},
        {"id": 2, "type": "LoadImage"},
        {"id": 3, "type": "VAEEncode"},
        {"id": 4, "type": "VAEDecode"},
    ],
    "links": [],
}


def signals(workflow):
    return {signal.signal_id: signal for signal in SignalExtractor().extract(workflow)}


def digest(workflow):
    payload = [signal.to_dict() for signal in SignalExtractor().extract(workflow)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ valid ids keep their exact signals
def test_signals_for_ordinary_integer_ids_are_unchanged():
    assert digest(TXT2IMG) == GOLDEN_TXT2IMG
    assert digest(IMG2IMG) == GOLDEN_IMG2IMG


@pytest.mark.parametrize("node_id", ["09", "007", "٩", "²", "abc", "12:3"])
def test_a_string_id_is_reported_exactly_and_not_as_a_number(node_id):
    found = signals({"nodes": [{"id": node_id, "type": "Probe"}]})

    assert found["node_type.Probe"].node_ids == [node_id]
    assert type(found["node_type.Probe"].node_ids[0]) is str


def test_ids_that_look_alike_stay_distinct():
    # "09", "9", the Arabic-Indic nine and the integer 9 are four different ids.
    nodes = [{"id": value, "type": "Probe"} for value in ("09", "9", "٩", 9)]

    found = signals({"nodes": nodes})

    assert found["node_type.Probe"].node_ids == ["09", "9", "٩", 9]
    assert found["node_count.Probe"].node_ids == ["09", "9", "٩", 9]


def test_a_superscript_digit_id_is_no_longer_dropped():
    found = signals({"nodes": [{"id": "²", "type": "Probe"}, {"id": 1, "type": "Probe"}]})

    assert found["node_type.Probe"].node_ids == ["²", 1]


# ------------------------------------------------------------------ an invalid id is skipped alone
@pytest.mark.parametrize(
    "invalid",
    [None, True, False, 1.5, -1, 2 ** 53, "", " bad", "bad ", "a\tb", "a\x00b", "﻿x", "x\u0085", [], {}, "x" * 1025],
    ids=repr,
)
def test_an_invalid_id_is_skipped_without_dropping_valid_siblings(invalid):
    found = signals({"nodes": [{"id": 1, "type": "Probe"}, {"id": invalid, "type": "Probe"}, {"id": "ok", "type": "Probe"}]})

    assert found["node_type.Probe"].node_ids == [1, "ok"]
    assert "node_count.Probe" in found


def test_a_node_without_an_id_or_type_is_skipped_as_before():
    found = signals({"nodes": [{"type": "A"}, {"id": 1}, {"id": 2, "type": "B"}, "not a node"]})

    assert set(found) == {"node_type.B"}


# ------------------------------------------------------------------ links resolve by exact id
def test_a_link_endpoint_never_resolves_to_a_look_alike_id():
    # Before: the Arabic-Indic "9" was turned into 9 and matched the node with id 9.
    workflow = {
        "nodes": [{"id": 9, "type": "B"}, {"id": "1", "type": "C"}],
        "links": [[1, "٩", 0, "1", 0, "X"]],
    }

    assert not any(signal_id.startswith("edge.") for signal_id in signals(workflow))


def test_a_leading_zero_link_endpoint_does_not_resolve_to_the_plain_number():
    workflow = {
        "nodes": [{"id": 9, "type": "B"}, {"id": 1, "type": "C"}],
        "links": [[1, "09", 0, 1, 0, "X"]],
    }

    assert not any(signal_id.startswith("edge.") for signal_id in signals(workflow))


@pytest.mark.parametrize("origin, target", [(5, 6), ("5", "6"), (5, "6"), ("5", 6)])
def test_the_host_integer_and_its_canonical_string_are_the_same_id(origin, target):
    # Hosts serialize link endpoints as integers while API-format ids are strings.
    workflow = {
        "nodes": [{"id": 5, "type": "A"}, {"id": "6", "type": "B"}],
        "links": [[1, origin, 0, target, 0, "X"]],
    }

    found = signals(workflow)

    assert found["edge.A_B"].node_ids == [origin, target]


def test_an_opaque_string_id_links_exactly():
    workflow = {
        "nodes": [{"id": "node-a", "type": "A"}, {"id": "node-b", "type": "B"}],
        "links": [[1, "node-a", 0, "node-b", 0, "X"]],
    }

    assert signals(workflow)["edge.A_B"].node_ids == ["node-a", "node-b"]


@pytest.mark.parametrize("endpoint", [None, True, [1], {"id": 1}, 1.5, -1, "", " 1", "1\n"], ids=repr)
def test_an_invalid_link_endpoint_is_skipped_without_raising(endpoint):
    workflow = {
        "nodes": [{"id": 1, "type": "A"}, {"id": 2, "type": "B"}],
        "links": [[1, endpoint, 0, 2, 0, "X"], [2, 1, 0, 2, 0, "Y"]],
    }

    found = signals(workflow)

    assert found["edge.A_B"].node_ids == [1, 2]  # the valid link after the bad one still counts
    assert sum(signal_id.startswith("edge.") for signal_id in found) == 1


@pytest.mark.parametrize(
    "endpoint, spelled_id",
    [(True, "True"), (False, "False"), (None, "None"), (1.5, "1.5"), (-1, "-1"), ([1], "[1]"), ({"a": 1}, "{'a': 1}")],
    ids=repr,
)
@pytest.mark.parametrize("side", ["origin", "target"])
def test_a_link_endpoint_that_is_not_an_id_never_matches_a_string_id_that_spells_it(endpoint, spelled_id, side):
    # str(True) == "True": an endpoint that is not a valid id must not be looked up through its text,
    # whichever end of the link it is on.
    workflow = {
        "nodes": [{"id": spelled_id, "type": "A"}, {"id": 2, "type": "B"}],
        "links": [[1, endpoint, 0, 2, 0, "X"] if side == "origin" else [1, 2, 0, endpoint, 0, "X"]],
    }

    assert not any(signal_id.startswith("edge.") for signal_id in signals(workflow))


def test_the_evidence_is_json_serializable_with_string_and_integer_ids():
    workflow = {"nodes": [{"id": "x", "type": "A"}, {"id": 2, "type": "A"}], "links": []}

    payload = [signal.to_dict() for signal in SignalExtractor().extract(workflow)]

    assert json.loads(json.dumps(payload))[0]["node_ids"] == ["x", 2]
