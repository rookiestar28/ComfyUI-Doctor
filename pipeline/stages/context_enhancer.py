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
    NODE_CONTEXT_PATTERNS = [
        # Pattern: Validation error format "* NodeName NodeID:" (highest priority)
        r"\*\s+([A-Za-z0-9_]+)\s+(\d+):",

        # Pattern: "Error occurred in node #123: NodeName" (common format)
        r"(?:ERROR|error)\s*(?:occurred\s*)?(?:on|in)\s*node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\s*\n|\s*$)",

        # Pattern: execution.py logs like "got prompt 123" with node info
        r"Executing node (\d+),?\s*[tT]itle:\s*(.+?)(?:,|\n|$)",

        # Pattern: "!!! Exception during processing node #123 !!!"
        r"Exception during processing.*?node\s*[#:]?\s*(\d+)",

        # Pattern: ComfyUI prompt error format
        r"Prompt executed.*?node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\)|$)",

        # Pattern: Node class from traceback File path
        r"custom_nodes[/\\]([^/\\]+)[/\\].*?\.py",

        # Pattern: Class name in traceback (self.<method> in <ClassName>)
        r"in\s+(\w+Node)\.",

        # Pattern: ComfyUI internal node class detection
        r"class\s+'([^']+Node)'",
    ]

    def __init__(self):
        self._name = "ContextEnhancerStage"

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
        patterns = self.NODE_CONTEXT_PATTERNS
        
        # Try to extract node ID and name
        for idx, pattern in enumerate(patterns[:5]):
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
                break
        
        # Extract custom node folder name
        # Pattern index 5
        custom_node_match = re.search(patterns[5], traceback_text)
        if custom_node_match:
            node_ctx.custom_node_path = custom_node_match.group(1)

        # Extract node class name
        # Patterns index 6 onwards
        for pattern in patterns[6:]:
            class_match = re.search(pattern, traceback_text)
            if class_match:
                node_ctx.node_class = class_match.group(1)
                break
        
        if node_ctx.is_valid():
            context.node_context = node_ctx
