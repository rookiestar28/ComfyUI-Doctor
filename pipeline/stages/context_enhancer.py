import re
from ..base import PipelineStage
from ..context import AnalysisContext, NodeContext


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

    COMPAT_EVENT_PATTERNS = {
        "display_node": (
            "compat_display_node",
            r"(?:['\"]display_node['\"]\s*[:=]\s*['\"]?([^'\",}\s]+)|\bdisplay_node\s*=\s*([^,\s]+))",
            0.95,
        ),
        "parent_node": (
            "compat_parent_node",
            r"(?:['\"]parent_node['\"]\s*[:=]\s*['\"]?([^'\",}\s]+)|\bparent_node\s*=\s*([^,\s]+))",
            0.95,
        ),
        "real_node_id": (
            "compat_real_node_id",
            r"(?:['\"]real_node_id['\"]\s*[:=]\s*['\"]?([^'\",}\s]+)|\breal_node_id\s*=\s*([^,\s]+))",
            0.95,
        ),
    }

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
        traceback_text = context.traceback
        if not traceback_text and not context.node_context:
            return

        current_node = context.node_context or NodeContext()
        node_data = {
            "node_id": current_node.node_id,
            "node_name": current_node.node_name,
            "node_class": current_node.node_class,
            "custom_node_path": current_node.custom_node_path,
            "display_node": current_node.display_node,
            "parent_node": current_node.parent_node,
            "real_node_id": current_node.real_node_id,
        }
        provenance = {
            "source_pattern": None,
            "confidence": 0.0,
            "used_raw": True,
            "compat_fields": [],
            "used_incoming_node_context": bool(context.node_context),
        }

        if traceback_text:
            self._extract_node_identity(node_data, traceback_text, provenance)
            self._extract_compat_fields(node_data, traceback_text, provenance)
            self._extract_custom_node_path(node_data, traceback_text, provenance)
            self._extract_node_class(node_data, traceback_text, provenance)

        if node_data.get("display_node") and not node_data.get("node_id"):
            node_data["node_id"] = node_data["display_node"]
        if node_data.get("real_node_id") and not node_data.get("display_node"):
            node_data["display_node"] = node_data["real_node_id"]

        node_ctx = NodeContext(**node_data)

        if node_ctx.is_valid():
            context.node_context = node_ctx
            context.metadata["context_extraction"] = {
                "source_pattern": provenance["source_pattern"] or "unknown",
                "confidence": provenance["confidence"],
                "used_raw": provenance["used_raw"],
                "used_incoming_node_context": provenance["used_incoming_node_context"],
                "compat_fields": provenance["compat_fields"],
                "node_id_found": bool(node_ctx.node_id),
                "node_name_found": bool(node_ctx.node_name),
                "node_class_found": bool(node_ctx.node_class),
                "display_node_found": bool(node_ctx.display_node),
                "parent_node_found": bool(node_ctx.parent_node),
                "real_node_id_found": bool(node_ctx.real_node_id),
                "subgraph_lineage": node_ctx.subgraph_lineage(),
            }

    def _extract_node_identity(
        self, node_data: dict, traceback_text: str, provenance: dict
    ) -> None:
        for idx, (pattern_name, pattern, confidence) in enumerate(self.NODE_ID_PATTERNS):
            match = re.search(pattern, traceback_text, re.IGNORECASE)
            if not match:
                continue

            groups = match.groups()
            if not groups:
                continue

            if idx == 0:
                if len(groups) > 0 and groups[0] and not node_data.get("node_name"):
                    node_data["node_name"] = groups[0].strip()
                if len(groups) > 1 and groups[1] and groups[1].isdigit() and not node_data.get("node_id"):
                    node_data["node_id"] = groups[1]
            else:
                if groups[0] and groups[0].isdigit() and not node_data.get("node_id"):
                    node_data["node_id"] = groups[0]
                if len(groups) > 1 and groups[1] and not node_data.get("node_name"):
                    node_data["node_name"] = groups[1].strip()

            provenance["source_pattern"] = pattern_name
            provenance["confidence"] = confidence
            break

    def _extract_compat_fields(
        self, node_data: dict, traceback_text: str, provenance: dict
    ) -> None:
        for field_name, (pattern_name, pattern, confidence) in self.COMPAT_EVENT_PATTERNS.items():
            match = re.search(pattern, traceback_text, re.IGNORECASE)
            if not match:
                continue

            value = next((group for group in match.groups() if group), None)
            if not value or node_data.get(field_name):
                continue

            node_data[field_name] = value.strip()
            provenance["compat_fields"].append(field_name)
            if not provenance["source_pattern"]:
                provenance["source_pattern"] = pattern_name
                provenance["confidence"] = confidence

    def _extract_custom_node_path(
        self, node_data: dict, traceback_text: str, provenance: dict
    ) -> None:
        custom_node_match = re.search(self.CUSTOM_NODE_PATTERN[1], traceback_text)
        if not custom_node_match or node_data.get("custom_node_path"):
            return

        node_data["custom_node_path"] = custom_node_match.group(1)
        if not provenance["source_pattern"]:
            provenance["source_pattern"] = self.CUSTOM_NODE_PATTERN[0]
            provenance["confidence"] = self.CUSTOM_NODE_PATTERN[2]

    def _extract_node_class(
        self, node_data: dict, traceback_text: str, provenance: dict
    ) -> None:
        for pattern_name, pattern, confidence in self.NODE_CLASS_PATTERNS:
            class_match = re.search(pattern, traceback_text)
            if not class_match:
                continue

            if not node_data.get("node_class"):
                node_data["node_class"] = class_match.group(1)
            if not provenance["source_pattern"]:
                provenance["source_pattern"] = pattern_name
                provenance["confidence"] = confidence
            break
