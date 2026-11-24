"""Intent signals skip a node whose type is not a non-empty string, and keep every sibling's signals.

The node type is used as a dict key while the signals are built. A list or dict type raised
``TypeError: unhashable``; ``DiagnosticsRunner`` swallows that and drops the whole intent signature of the
workflow because of one malformed node. An int or a bool did not raise but produced a meaningless
``node_type`` signal. Ids were hardened by R74; types are hardened here without a grammar change.
"""
import asyncio
import copy

import pytest

from services.intent import IntentScorer, SignalExtractor
from tests.test_r74_intent_node_ids import GOLDEN_IMG2IMG, GOLDEN_TXT2IMG, IMG2IMG, TXT2IMG, digest

SIBLINGS = copy.deepcopy(TXT2IMG)


def with_odd_type(odd_type, **extra):
    workflow = copy.deepcopy(SIBLINGS)
    workflow["nodes"].append({"id": 99, "type": odd_type, **extra})
    return workflow


def signals(workflow):
    return {signal.signal_id: signal for signal in SignalExtractor().extract(workflow)}


ODD_TYPES = [
    ["KSampler"], {"a": 1}, [], {}, 5, 1.5, True, False, None, "", 0,
]


def test_signals_of_valid_workflows_are_unchanged():
    assert digest(TXT2IMG) == GOLDEN_TXT2IMG
    assert digest(IMG2IMG) == GOLDEN_IMG2IMG


@pytest.mark.parametrize("odd_type", ODD_TYPES, ids=repr)
def test_a_node_with_a_non_string_type_is_skipped_alone(odd_type):
    original = with_odd_type(odd_type)
    before = copy.deepcopy(original)

    # The extraction neither raises nor changes any signal of the valid nodes.
    assert digest(original) == GOLDEN_TXT2IMG
    assert original == before


@pytest.mark.parametrize("odd_type", [["x"], {"a": 1}, 5, True], ids=repr)
def test_an_unusable_type_beats_a_class_type_like_any_other_falsy_choice(odd_type):
    # The type field decides first (`type or class_type`); a type that is truthy but not a string is not a node name.
    workflow = copy.deepcopy(SIBLINGS)
    workflow["nodes"].append({"id": 99, "type": odd_type, "class_type": "KSampler"})

    assert digest(workflow) == GOLDEN_TXT2IMG


def test_the_class_type_of_an_api_format_node_is_still_used():
    api = {"nodes": [{"id": 7, "class_type": "KSampler"}]}
    ui = {"nodes": [{"id": 7, "type": "KSampler"}]}

    assert digest(api) == digest(ui)
    assert "node_type.KSampler" in signals(api)


def test_a_dict_form_nodes_collection_skips_odd_types_too():
    workflow = {"nodes": {"1": {"id": 1, "type": ["x"]}, "2": {"id": 2, "type": "KSampler"}, "3": {"id": 3, "type": {"a": 1}}}}

    assert set(signals(workflow)) == set(signals({"nodes": [{"id": 2, "type": "KSampler"}]}))


def test_a_workflow_that_only_has_odd_types_yields_no_node_type_signal():
    found = signals({"nodes": [{"id": 1, "type": ["x"]}, {"id": 2, "type": {"a": 1}}, {"id": 3, "type": 5}]})

    assert not [signal_id for signal_id in found if signal_id.startswith("node_type.") or signal_id.startswith("node_count.")]


def test_the_intent_signature_is_still_computed_for_a_workflow_with_one_odd_node():
    async def run():
        scorer = IntentScorer()
        clean = await scorer.compute(copy.deepcopy(TXT2IMG), "h-clean")
        odd = await scorer.compute(with_odd_type(["KSampler"]), "h-odd")
        return clean, odd

    clean, odd = asyncio.run(run())

    assert [intent.intent_id for intent in odd.top_intents] == [intent.intent_id for intent in clean.top_intents]
    assert odd.top_intents and odd.top_intents[0].intent_id == "txt2img"
