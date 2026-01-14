import logging
from typing import Optional, Dict, Any
from ..base import PipelineStage
from ..context import AnalysisContext
try:
    from services.workflow_pruner import WorkflowPruner
    from services.context_extractor import (
        extract_error_summary,
        collapse_stack_frames,
        build_context_manifest,
    )
except ImportError:
    # Use relative import for flexibility
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from services.workflow_pruner import WorkflowPruner
    from services.context_extractor import (
        extract_error_summary,
        collapse_stack_frames,
        build_context_manifest,
    )

logger = logging.getLogger(__name__)

class LLMContextBuilderStage(PipelineStage):
    """
    Stage 4: LLM Context Builder.
    Prepares the context for LLM analysis (R12 + R14).
    - Extracts error summary (R14: summary-first prompt)
    - Collapses stack frames (R14: semantic truncation)
    - Prunes workflow JSON to relevant subgraph (R12)
    - Builds context manifest for observability (R14)
    """
    
    def __init__(self, workflow_pruner: WorkflowPruner):
        """
        Initialize with injected dependencies.
        
        Args:
            workflow_pruner: Service to prune workflows.
        """
        self._name = "LLMContextBuilderStage"
        self.stage_id = "llm_context_builder"
        self.requires = ["sanitized_traceback"]
        self.provides = ["llm_context", "metadata.estimated_tokens", "metadata.context_manifest"]
        self.version = "2.0"  # R14 upgrade
        self.pruner = workflow_pruner

    @property
    def name(self) -> str:
        return self._name

    def process(self, context: AnalysisContext) -> None:
        """
        Builds the LLM context with R14 optimizations.
        
        Order of sections in llm_context (summary-first):
        1. error_summary - Short exception type + message
        2. node_info - Failed node details
        3. traceback - Collapsed if long
        4. execution_logs - Recent log lines
        5. workflow_subset - Pruned workflow
        6. system_info - Environment info
        """
        if not context.sanitized_traceback:
            return

        # R14 Step 1: Extract error summary
        pattern_category = context.metadata.get("pattern_match", {}).get("category")
        error_summary = extract_error_summary(
            context.sanitized_traceback,
            pattern_category=pattern_category
        )
        if error_summary:
            context.error_summary = error_summary.to_string()

        # R14 Step 2: Collapse stack frames for token efficiency
        collapsed_traceback = collapse_stack_frames(
            context.sanitized_traceback,
            head_frames=3,
            tail_frames=5
        )

        # Step 3: Prune Workflow if available
        pruned_workflow = None
        if context.workflow_json and context.node_context and context.node_context.node_id:
            try:
                pruned_workflow = self.pruner.prune(
                    context.workflow_json, 
                    context.node_context.node_id
                )
            except Exception as e:
                logger.warning(f"Workflow pruning failed: {e}")
                pruned_workflow = context.workflow_json

        # Step 4: Build LLM Context Dict (summary-first order)
        llm_data = {
            "error_summary": context.error_summary,  # R14: First
            "node_info": context.node_context.to_dict() if context.node_context else {},
            "traceback": collapsed_traceback,  # R14: Collapsed
            "execution_logs": context.execution_logs,  # R14: From ring buffer
            "workflow_subset": pruned_workflow,
            "system_info": context.system_info
        }
        
        context.llm_context = llm_data
        
        # R14 Step 5: Build context manifest for observability
        manifest = build_context_manifest(
            traceback_text=context.sanitized_traceback,
            execution_logs=context.execution_logs,
            workflow_json=context.workflow_json,
            system_info=context.system_info,
            error_summary=error_summary
        )
        context.add_metadata("context_manifest", manifest.to_dict())
        
        # Step 6: Estimate Tokens (Optional Metadata)
        try:
            tokens = self.pruner.estimate_tokens(llm_data)
            context.add_metadata("estimated_tokens", tokens)
        except Exception:
            pass

