from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_node_context_is_frozen_and_normalizes_values():
    from pipeline.context import NodeContext

    ctx = NodeContext(node_id=15, node_name="  KSampler  ", display_node="")

    assert is_dataclass(ctx)
    assert ctx.node_id == "15"
    assert ctx.node_name == "KSampler"
    assert ctx.display_node is None

    with pytest.raises(FrozenInstanceError):
        ctx.node_id = "16"


def test_node_context_rejects_control_characters():
    from pipeline.context import NodeContext

    with pytest.raises(ValueError, match="node_id"):
        NodeContext(node_id="12\n13")


def test_context_enhancer_builds_immutable_node_context():
    from pipeline.context import AnalysisContext
    from pipeline.stages.context_enhancer import ContextEnhancerStage

    ctx = AnalysisContext(
        traceback='execution_error detail={"display_node":"65:70:63","parent_node":"65:70","real_node_id":"63"}'
    )

    ContextEnhancerStage().process(ctx)

    assert ctx.node_context is not None
    assert ctx.node_context.preferred_node_id() == "65:70:63"
    assert ctx.node_context.subgraph_lineage() == ["65:70", "65:70:63", "63"]
    with pytest.raises(FrozenInstanceError):
        ctx.node_context.display_node = "1"
