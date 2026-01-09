import logging
import re
from typing import Optional
from ..base import PipelineStage
from ..context import AnalysisContext, NodeContext

logger = logging.getLogger(__name__)

class ContextEnhancerStage(PipelineStage):
    """
    Stage 3: Context Enhancer.
    Extracts ComfyUI node context (ID, Name, Class) from the traceback.
    """
    
    # ComfyUI-specific patterns for extracting node context
    # Copied from original analyzer.py
    NODE_ID_PATTERNS = [
        ("validation_node_name_id", r"\*\s+([A-Za-z0-9_]+)\s+(\d+):", 0.9),
        ("error_on_node_id", r"(?:ERROR|error)\s*(?:occurred\s*)?(?:on|in)\s*node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\s*\n|\s*$)", 0.85),
        ("executing_node_title", r"Executing node (\d+),?\s*[tT]itle:\s*(.+?)(?:,|\n|$)", 0.8),
        ("exception_processing_node", r"Exception during processing.*?node\s*[#:]?\s*(\d+)", 0.7),
        ("prompt_executed_node", r"Prompt executed.*?node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\)|$)", 0.7),
    ]

    CUSTOM_NODE_PATTERN = ("custom_node_path", r"custom_nodes[/\\]([^/\\]+)[/\\].*?\.py", 0.6)
    NODE_CLASS_PATTERNS = [
        ("node_class_method", r"in\s+(\w+Node)\.", 0.5),
        ("node_class_literal", r"class\s+'([^']+Node)'", 0.5),
    ]

    def __init__(self):
        self._name = "ContextEnhancerStage"
        self.stage_id = "context_enhancer"
        self.requires = ["traceback"]
        self.provides = ["node_context"]
        self.version = "1.0"

    @property
    def name(self) -> str:
        return self._name

    def process(self, context: AnalysisContext) -> None:
        """
        Extracts node context from traceback and populates context.node_context.
        """
        # Use sanitized traceback to overlap with what LLM sees, 
        # but for regex extraction original traceback is usually safe and maybe more complete?
        # Let's use original traceback for extraction as it might contain paths we need.
        # But wait, PII sanitizer removes paths. 
        # If we need paths for "custom_node_path" extraction, we should use original.
        # PII sanitizer removes User Path but keeps structure.
        # Safest is to use ORIGINAL traceback for extraction logic, as it's regex based and internal.
        traceback_text = context.traceback
        
        if not traceback_text:
            return

        node_ctx = NodeContext()
        provenance = {"source_pattern": None, "confidence": 0.0, "used_raw": True}
        
        # Try to extract node ID and name
        for idx, (pattern_name, pattern, confidence) in enumerate(self.NODE_ID_PATTERNS):
            match = re.search(pattern, traceback_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups:
                    # First pattern (* NodeName NodeID:) has reversed order
                    if idx == 0:
                        # First group is node name, second is node ID
                        if len(groups) > 0 and groups[0]:
                            node_ctx.node_name = groups[0].strip()
                        if len(groups) > 1 and groups[1] and groups[1].isdigit():
                            node_ctx.node_id = groups[1]
                    else:
                        # Other patterns: First group is usually node ID
                        if groups[0] and groups[0].isdigit():
                            node_ctx.node_id = groups[0]
                        # Second group (if exists) is usually node name
                        if len(groups) > 1 and groups[1]:
                            node_ctx.node_name = groups[1].strip()
                provenance["source_pattern"] = pattern_name
                provenance["confidence"] = confidence
                break
        
        # Extract custom node folder name
        custom_node_match = re.search(self.CUSTOM_NODE_PATTERN[1], traceback_text)
        if custom_node_match:
            node_ctx.custom_node_path = custom_node_match.group(1)
            if not provenance["source_pattern"]:
                provenance["source_pattern"] = self.CUSTOM_NODE_PATTERN[0]
                provenance["confidence"] = self.CUSTOM_NODE_PATTERN[2]

        # Extract node class name
        for pattern_name, pattern, confidence in self.NODE_CLASS_PATTERNS:
            class_match = re.search(pattern, traceback_text)
            if class_match:
                node_ctx.node_class = class_match.group(1)
                if not provenance["source_pattern"]:
                    provenance["source_pattern"] = pattern_name
                    provenance["confidence"] = confidence
                break
        
        if node_ctx.is_valid():
            context.node_context = node_ctx
            context.metadata["context_extraction"] = {
                "source_pattern": provenance["source_pattern"] or "unknown",
                "confidence": provenance["confidence"],
                "used_raw": provenance["used_raw"],
                "node_id_found": bool(node_ctx.node_id),
                "node_name_found": bool(node_ctx.node_name),
                "node_class_found": bool(node_ctx.node_class),
            }
