from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .metadata_contract import METADATA_SCHEMA_VERSION

# Forward reference for NodeContext to avoid circular import if needed in future,
# but for now we can define it or import it if it's moved.
# Since we are planning to move NodeContext, let's keep it flexible.
# For now, we will type hint it as Any or import it if appropriate.
# However, the plan says "Stage 3 Output: Node Context", and NodeContext currently is in analyzer.py.
# To avoid circular imports between analyzer and pipeline, we should eventually move NodeContext to pipeline/context.py or a shared model file.
# For this step, I will define a placeholder or duplicate minimal structure if needed, 
# or better yet, move NodeContext definition here or import it if analyzer imports pipeline.
# analyzer.py will import pipeline, so pipeline cannot import analyzer.
# SO: NodeContext MUST be moved to here or acceptable common place.
# I will define NodeContext here as part of the refactor plan implies "Strongly Typed Data Class".

@dataclass
class NodeContext:
    """Context information about the node where an error occurred."""
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    node_class: Optional[str] = None
    custom_node_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_class": self.node_class,
            "custom_node_path": self.custom_node_path,
        }
    
    def is_valid(self) -> bool:
        """Check if any context was extracted."""
        return any([self.node_id, self.node_name, self.node_class])

@dataclass
class AnalysisContext:
    """
    Context object passed through the Analysis Pipeline.
    Contains immutable inputs and mutable processing state.
    """
    # Inputs (Immutable-ish)
    traceback: str
    workflow_json: Optional[Dict[str, Any]] = None
    system_info: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    # Mutable Processing State (Populated by Stages)
    sanitized_traceback: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Stage 3 Output: Node Context
    node_context: Optional[NodeContext] = None
    
    # R12 / LLM Data
    llm_context: Optional[Dict[str, Any]] = None
    
    # R14: Error Context Extraction
    error_summary: Optional[str] = None  # Short summary (exception type + message)
    execution_logs: List[str] = field(default_factory=list)  # Recent log lines from ring buffer

    def __post_init__(self) -> None:
        # Ensure metadata contract version is always present
        if "metadata_schema_version" not in self.metadata:
            self.metadata["metadata_schema_version"] = METADATA_SCHEMA_VERSION
        self.metadata.setdefault("pipeline_status", "ok")
        self.metadata.setdefault("stage_errors", [])
    
    def add_metadata(self, key: str, value: Any):
        """Helper to safely add metadata."""
        self.metadata[key] = value
