import pytest
from unittest.mock import MagicMock
from pipeline.context import AnalysisContext, NodeContext
from pipeline.stages.llm_builder import LLMContextBuilderStage
from services.workflow_pruner import WorkflowPruner

def test_llm_builder_di():
    """Verify that WorkflowPruner can be injected and used."""
    
    # 1. Create Mock Pruner
    mock_pruner = MagicMock(spec=WorkflowPruner)
    mock_pruner.prune.return_value = {"nodes": ["pruned"]}
    mock_pruner.estimate_tokens.return_value = 100
    
    # 2. Inject into Stage
    stage = LLMContextBuilderStage(workflow_pruner=mock_pruner)
    
    # 3. Create Context
    ctx = AnalysisContext(traceback="error")
    ctx.sanitized_traceback = "error"
    ctx.workflow_json = {"nodes": ["full", "graph"]}
    ctx.node_context = NodeContext(node_id="123")
    
    # 4. Run Stage
    stage.process(ctx)
    
    # 5. Verify Mock calls
    mock_pruner.prune.assert_called_once_with({"nodes": ["full", "graph"]}, "123")
    mock_pruner.estimate_tokens.assert_called_once()
    
    # 6. Verify Context Update
    assert ctx.llm_context is not None
    assert ctx.llm_context["workflow_subset"] == {"nodes": ["pruned"]}
    assert ctx.metadata["estimated_tokens"] == 100
