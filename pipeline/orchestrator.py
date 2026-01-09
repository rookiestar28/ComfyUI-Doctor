from typing import List
import logging
import traceback
from .base import PipelineStage
from .context import AnalysisContext
from .metadata_contract import validate_metadata_contract

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
        stage_errors = context.metadata.setdefault("stage_errors", [])
        pipeline_status = context.metadata.get("pipeline_status", "ok")
        if pipeline_status not in {"ok", "degraded", "failed"}:
            pipeline_status = "ok"

        for stage in self.stages:
            stage_name = getattr(stage, "name", str(type(stage).__name__))
            stage_id = getattr(stage, "stage_id", stage_name)
            requires = getattr(stage, "requires", []) or []

            missing = self._missing_requirements(context, requires)
            if missing:
                stage_errors.append({
                    "stage_id": stage_id,
                    "error": "missing_requirements",
                    "missing": missing,
                })
                if pipeline_status == "ok":
                    pipeline_status = "degraded"
                continue

            try:
                # logger.debug(f"Executing stage: {stage_name}")
                stage.process(context)
            except Exception as e:
                # Fail-Safe: Log error but continue pipeline to ensure
                # we return partial results (e.g. from earlier stages) if possible.
                error_msg = f"Stage {stage_name} failed: {str(e)}"
                logger.error(error_msg, exc_info=True)

                stage_errors.append({
                    "stage_id": stage_id,
                    "error": str(e),
                })
                pipeline_status = "failed"

                # Record stage failure in metadata (legacy key)
                meta_key = f"stage_error_{stage_name}"
                context.add_metadata(meta_key, str(e))
                
                # Optional: Add trace to system info if needed for debugging
                # context.system_info[f"{stage_name}_traceback"] = traceback.format_exc()

        context.metadata["pipeline_status"] = pipeline_status
        context.metadata = validate_metadata_contract(context.metadata)
        return context

    @staticmethod
    def _missing_requirements(context: AnalysisContext, requires: List[str]) -> List[str]:
        missing = []
        for requirement in requires:
            if not requirement:
                continue
            options = [option.strip() for option in requirement.split("|") if option.strip()]
            if not options:
                continue

            satisfied = False
            for option in options:
                if option.startswith("metadata."):
                    key = option.split(".", 1)[1]
                    value = context.metadata.get(key)
                    if value is not None and not (isinstance(value, str) and value == ""):
                        satisfied = True
                        break
                else:
                    value = getattr(context, option, None)
                    if value is not None and not (isinstance(value, str) and value == ""):
                        satisfied = True
                        break

            if not satisfied:
                missing.append(requirement)
        return missing
