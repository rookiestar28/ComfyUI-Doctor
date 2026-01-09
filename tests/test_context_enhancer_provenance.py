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
