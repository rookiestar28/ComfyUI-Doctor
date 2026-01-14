import logging
from typing import Optional, Dict, Any, List
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
    Prepares the context for LLM analysis (R12 + R14 + R15).
    - Extracts error summary (R14: summary-first prompt)
    - Collapses stack frames (R14: semantic truncation)
    - Prunes workflow JSON to relevant subgraph (R12)
    - Builds context manifest for observability (R14)
    - R15: Populates execution_logs from LogRingBuffer when empty
    - R15: Populates system_info with canonical schema when missing
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
        self.version = "2.1"  # R15 upgrade
        self.pruner = workflow_pruner

    @property
    def name(self) -> str:
        return self._name

    def _populate_execution_logs(self, context: AnalysisContext) -> List[str]:
        """
        R15: Populate execution_logs from LogRingBuffer if context.execution_logs is empty.
        
        Args:
            context: Pipeline analysis context
            
        Returns:
            List of log lines (sanitized based on privacy_mode)
        """
        if context.execution_logs:
            return context.execution_logs
        
        try:
            from services.log_ring_buffer import get_ring_buffer
            from sanitizer import sanitize_for_llm
            ring_buffer = get_ring_buffer()
            
            if ring_buffer.is_empty:
                return []
            
            privacy_mode = context.settings.get("privacy_mode", "basic")
            
            # Get recent logs (max 50 lines aligned with PromptComposerConfig.max_logs_lines)
            raw_logs = ring_buffer.get_recent(n=50, sanitize=False)
            sanitized_logs = [sanitize_for_llm(line, level=privacy_mode) for line in raw_logs]
            
            # Update context with populated logs
            context.execution_logs = sanitized_logs
            return sanitized_logs
            
        except Exception as e:
            logger.debug(f"[R15] Failed to populate execution_logs from ring buffer: {e}")
            return []

    def _populate_system_info(self, context: AnalysisContext) -> Dict[str, Any]:
        """
        R15: Populate system_info with canonical schema if missing.
        
        Args:
            context: Pipeline analysis context
            
        Returns:
            Canonical system_info dict
        """
        if context.system_info:
            return context.system_info
        
        # Guard: Only auto-populate if enabled in settings
        if not context.settings.get("include_system_info", True):
            return {}
        
        try:
            from system_info import get_system_environment, canonicalize_system_info
            
            env_info = get_system_environment()
            privacy_mode = context.settings.get("privacy_mode", "basic")
            
            canonical = canonicalize_system_info(
                env_info,
                error_text=context.sanitized_traceback,
                privacy_mode=privacy_mode
            )
            
            # Update context with populated system_info
            context.system_info = canonical
            return canonical
            
        except Exception as e:
            logger.debug(f"[R15] Failed to populate system_info: {e}")
            return {}

    def process(self, context: AnalysisContext) -> None:
        """
        Builds the LLM context with R14/R15 optimizations.
        
        Order of sections in llm_context (summary-first):
        1. error_summary - Short exception type + message
        2. node_info - Failed node details
        3. traceback - Collapsed if long
        4. execution_logs - Recent log lines (R15: auto-populated from ring buffer)
        5. workflow_subset - Pruned workflow
        6. system_info - Environment info (R15: canonical schema)
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

        # R15 Step 3a: Populate execution_logs from ring buffer if empty
        execution_logs = self._populate_execution_logs(context)
        
        # R15 Step 3b: Populate system_info with canonical schema if missing
        system_info = self._populate_system_info(context)

        # Step 4: Build LLM Context Dict (summary-first order)
        llm_data = {
            "error_summary": context.error_summary,  # R14: First
            "node_info": context.node_context.to_dict() if context.node_context else {},
            "traceback": collapsed_traceback,  # R14: Collapsed
            "execution_logs": execution_logs,  # R15: From ring buffer when empty
            "workflow_subset": pruned_workflow,
            "system_info": system_info  # R15: Canonical schema
        }
        
        context.llm_context = llm_data
        
        # R14 Step 5: Build context manifest for observability
        manifest = build_context_manifest(
            traceback_text=context.sanitized_traceback,
            execution_logs=execution_logs,
            workflow_json=context.workflow_json,
            system_info=system_info,
            error_summary=error_summary
        )
        context.add_metadata("context_manifest", manifest.to_dict())
        
        # Step 6: Estimate Tokens (Optional Metadata)
        try:
            tokens = self.pruner.estimate_tokens(llm_data)
            context.add_metadata("estimated_tokens", tokens)
        except Exception:
            pass
