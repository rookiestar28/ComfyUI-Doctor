from typing import Protocol, runtime_checkable, List
from .context import AnalysisContext

@runtime_checkable
class PipelineStage(Protocol):
    """
    Protocol defining the interface for all analysis pipeline stages.
    """
    
    @property
    def name(self) -> str:
        """Name of the stage for logging and metadata."""
        ...

    stage_id: str
    requires: List[str]
    provides: List[str]
    version: str
        
    def process(self, context: AnalysisContext) -> None:
        """
        Process the analysis context. 
        Modifies context in-place.
        Raises exception on critical failure (handled by orchestrator).
        """
        ...
