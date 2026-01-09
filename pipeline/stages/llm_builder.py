import logging
from typing import Optional, Dict, Any
from ..base import PipelineStage
from ..context import AnalysisContext
try:
    from services.workflow_pruner import WorkflowPruner
except ImportError:
    # Use relative import for flexibility
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from services.workflow_pruner import WorkflowPruner

logger = logging.getLogger(__name__)

class LLMContextBuilderStage(PipelineStage):
    """
    Stage 4: LLM Context Builder.
    Prepares the context for LLM analysis (R12).
    - Prunes workflow JSON to relevant subgraph.
    - Estimates token usage.
    - Structures data for the LLM prompt.
    """
    
    def __init__(self, workflow_pruner: WorkflowPruner):
        """
        Initialize with injected dependencies.
        
        Args:
            workflow_pruner: Service to prune workflows.
        """
        self._name = "LLMContextBuilderStage"
        self.stage_id = "llm_context_builder"
        self.requires = ["sanitized_traceback|traceback"]
        self.provides = ["llm_context", "metadata.estimated_tokens"]
        self.version = "1.0"
        self.pruner = workflow_pruner

    @property
    def name(self) -> str:
        return self._name

    def process(self, context: AnalysisContext) -> None:
        """
        Builds the LLM context.
        """
        # 1. Prune Workflow if available
        pruned_workflow = None
        if context.workflow_json and context.node_context and context.node_context.node_id:
            try:
                pruned_workflow = self.pruner.prune(
                    context.workflow_json, 
                    context.node_context.node_id
                )
            except Exception as e:
                logger.warning(f"Workflow pruning failed: {e}")
                # Fallback to original or summary?
                # For now, maybe just keep original or nothing
                pruned_workflow = context.workflow_json

        # 2. Build LLM Context Dict
        llm_data = {
            "traceback": context.sanitized_traceback or context.traceback,
            "node_info": context.node_context.to_dict() if context.node_context else {},
            "workflow_subset": pruned_workflow,
            "system_info": context.system_info
        }
        
        context.llm_context = llm_data
        
        # 3. Estimate Tokens (Optional Metadata)
        try:
            tokens = self.pruner.estimate_tokens(llm_data)
            context.add_metadata("estimated_tokens", tokens)
        except Exception:
            pass
