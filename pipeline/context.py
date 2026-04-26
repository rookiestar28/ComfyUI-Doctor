from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, ClassVar
from .metadata_contract import METADATA_SCHEMA_VERSION

@dataclass(frozen=True)
class NodeContext:
    """Context information about the node where an error occurred."""
    node_id: Optional[Any] = None
    node_name: Optional[Any] = None
    node_class: Optional[Any] = None
    custom_node_path: Optional[Any] = None
    display_node: Optional[Any] = None
    parent_node: Optional[Any] = None
    real_node_id: Optional[Any] = None

    _FIELD_NAMES: ClassVar[tuple[str, ...]] = (
        "node_id",
        "node_name",
        "node_class",
        "custom_node_path",
        "display_node",
        "parent_node",
        "real_node_id",
    )

    def __post_init__(self) -> None:
        for field_name in self._FIELD_NAMES:
            normalized = self._normalize_field(field_name, getattr(self, field_name))
            object.__setattr__(self, field_name, normalized)

    @staticmethod
    def _normalize_field(field_name: str, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if any(ord(ch) < 32 for ch in text):
            raise ValueError(f"{field_name} contains control characters")
        return text

    def preferred_node_id(self) -> Optional[str]:
        """Return the best node id for UI navigation and workflow targeting."""
        return self.display_node or self.node_id or self.real_node_id

    def subgraph_lineage(self) -> List[str]:
        """Return a de-duplicated lineage for subgraph-expanded executions."""
        lineage = []
        for node_id in (self.parent_node, self.display_node, self.real_node_id, self.node_id):
            if node_id and node_id not in lineage:
                lineage.append(node_id)
        return lineage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_class": self.node_class,
            "custom_node_path": self.custom_node_path,
            "display_node": self.display_node,
            "parent_node": self.parent_node,
            "real_node_id": self.real_node_id,
            "preferred_node_id": self.preferred_node_id(),
            "subgraph_lineage": self.subgraph_lineage(),
        }
    
    def is_valid(self) -> bool:
        """Check if any context was extracted."""
        return any(
            [
                self.node_id,
                self.node_name,
                self.node_class,
                self.display_node,
                self.parent_node,
                self.real_node_id,
            ]
        )

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
