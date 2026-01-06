from typing import List
import logging
import traceback
from .base import PipelineStage
from .context import AnalysisContext

logger = logging.getLogger(__name__)

class AnalysisPipeline:
    """
    Orchestrator for the ComfyUI-Doctor Error Analysis Pipeline.
    Executes stages sequentially with fail-safe error handling.
    """
    
    def __init__(self, stages: List[PipelineStage]):
        """
        Initialize the pipeline with a list of stages.
        
        Args:
            stages: Ordered list of PipelineStage objects to execute.
        """
        self.stages = stages
        self._validate_stages()
        
    def _validate_stages(self):
        """Ensure all stages implement the PipelineStage protocol."""
        for i, stage in enumerate(self.stages):
            if not isinstance(stage, PipelineStage):
                logger.warning(f"Stage at index {i} ({stage}) does not implement PipelineStage protocol")

    def run(self, context: AnalysisContext) -> AnalysisContext:
        """
        Run the analysis pipeline on the given context.
        
        Args:
            context: The initial analysis context.
            
        Returns:
            The processed analysis context.
        """
        for stage in self.stages:
            stage_name = getattr(stage, "name", str(type(stage).__name__))
            try:
                # logger.debug(f"Executing stage: {stage_name}")
                stage.process(context)
            except Exception as e:
                # Fail-Safe: Log error but continue pipeline to ensure
                # we return partial results (e.g. from earlier stages) if possible.
                error_msg = f"Stage {stage_name} failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                
                # Record stage failure in metadata
                meta_key = f"stage_error_{stage_name}"
                context.add_metadata(meta_key, str(e))
                
                # Optional: Add trace to system info if needed for debugging
                # context.system_info[f"{stage_name}_traceback"] = traceback.format_exc()
                
        return context
