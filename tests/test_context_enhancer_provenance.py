from pipeline.context import AnalysisContext
from pipeline.stages.context_enhancer import ContextEnhancerStage


def test_context_extraction_provenance_added():
    ctx = AnalysisContext(
        traceback="Failed to validate prompt for output 1:\n* KSampler 1:\n"
    )
    stage = ContextEnhancerStage()
    stage.process(ctx)

    assert ctx.node_context is not None
    assert ctx.node_context.node_id == "1"
    assert ctx.node_context.node_name == "KSampler"

    provenance = ctx.metadata.get("context_extraction")
    assert provenance is not None
    assert provenance["source_pattern"] == "validation_node_name_id"
    assert provenance["used_raw"] is True
    assert provenance["node_id_found"] is True


def test_context_extraction_captures_execution_error_compat_fields():
    ctx = AnalysisContext(
        traceback='execution_error detail={"display_node":"65:70:63","parent_node":"65:70","real_node_id":"63"}'
    )
    stage = ContextEnhancerStage()
    stage.process(ctx)

    assert ctx.node_context is not None
    assert ctx.node_context.display_node == "65:70:63"
    assert ctx.node_context.parent_node == "65:70"
    assert ctx.node_context.real_node_id == "63"
    assert ctx.node_context.subgraph_lineage() == ["65:70", "65:70:63", "63"]

    provenance = ctx.metadata.get("context_extraction")
    assert provenance is not None
    assert provenance["display_node_found"] is True
    assert provenance["parent_node_found"] is True
    assert provenance["real_node_id_found"] is True
    assert provenance["compat_fields"] == ["display_node", "parent_node", "real_node_id"]
