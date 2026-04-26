from pathlib import Path


def test_active_analyzer_pipeline_includes_llm_context_builder():
    import analyzer
    from pipeline.stages.llm_builder import LLMContextBuilderStage

    analyzer._pipeline_instance = None
    pipeline = analyzer.get_pipeline()

    stage_types = [type(stage) for stage in pipeline.stages]
    assert LLMContextBuilderStage in stage_types
    assert stage_types.index(LLMContextBuilderStage) > 0


def test_analyzer_analysis_metadata_contains_llm_context_manifest():
    from analyzer import ErrorAnalyzer

    _, metadata = ErrorAnalyzer.analyze("CUDA out of memory while running node 7")

    assert metadata is not None
    assert "context_manifest" in metadata
    assert "estimated_tokens" in metadata


def test_analyzer_build_llm_context_uses_pipeline_and_real_workflow_pruner():
    from analyzer import ErrorAnalyzer

    workflow = {
        "3": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "4": {"class_type": "KSampler", "inputs": {"model": ["3", 0]}},
    }

    ctx = ErrorAnalyzer.build_llm_context(
        "RuntimeError: CUDA out of memory\nerror occurred in node 4: KSampler",
        workflow_json=workflow,
        node_context={"node_id": "4", "node_name": "KSampler"},
        execution_logs=["Executing node 4"],
        system_info={"os": "Windows", "python_version": "3.11"},
        settings={"privacy_mode": "basic"},
    )

    assert ctx.llm_context is not None
    assert ctx.llm_context["node_info"]["node_id"] == "4"
    assert ctx.llm_context["execution_logs"] == ["Executing node 4"]
    assert ctx.llm_context["system_info"]["os"] == "Windows"
    assert ctx.llm_context["workflow_subset"] == workflow
    assert "context_manifest" in ctx.metadata


def test_routes_delegate_llm_context_construction_to_analyzer_helper():
    project_root = Path(__file__).resolve().parent.parent
    entrypoint = project_root / "__init__.py"
    if not entrypoint.exists():
        entrypoint = project_root / "__init__.py.bak"
    source = entrypoint.read_text(encoding="utf-8")

    assert "ErrorAnalyzer.build_llm_context" in source
    assert "from .services.context_extractor import extract_error_summary" not in source
