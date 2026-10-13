"""
T5 Service: Node Health Scoring.

Calculates heuristic health scores for nodes based on error history.
Currently limited to "Failure Frequency" as we do not track successful executions yet.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict


def _node_class(entry: Dict[str, Any]) -> Optional[str]:
    """Node class of a history entry: HistoryEntry.node_context first, then the legacy node_info."""
    # IMPORTANT: history entries are HistoryEntry.to_dict() and carry `node_context`; reading only
    # the legacy `node_info` shape made node_health empty for every real entry.
    node_context = entry.get("node_context")
    if isinstance(node_context, dict):
        node_class = node_context.get("node_class") or node_context.get("node_name")
        if node_class:
            return str(node_class)
    node_info = entry.get("node_info")
    if isinstance(node_info, dict):
        node_class = node_info.get("node_class") or node_info.get("node_type")
        if node_class:
            return str(node_class)
    return None


def _error_label(entry: Dict[str, Any]) -> str:
    """Pattern id or category only; raw error text (paths, prompts) never enters statistics."""
    return entry.get("matched_pattern_id") or entry.get("pattern_category") or "unknown"


class NodeHealthService:
    """
    Analyzes error history to determine node health.
    """

    @staticmethod
    def calculate_node_failures(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate failure counts per node type.

        Args:
            history: List of error history entries.

        Returns:
            List of dicts: [{"node_class": str, "count": int, "last_error": str}, ...]
            Sorted by count descending.
        """
        node_stats = defaultdict(lambda: {"count": 0, "last_error": "", "node_class": ""})

        for entry in history:
            node_class = _node_class(entry)
            if not node_class:
                continue

            # Key by node class (type) rather than specific node_id instance
            # to capture systematic improvements needed for a node type.
            key = node_class
            
            try:
                weight = int(entry.get("repeat_count", 1) or 1)
            except Exception:
                weight = 1
                
            node_stats[key]["node_class"] = node_class
            node_stats[key]["count"] += weight
            node_stats[key]["last_error"] = _error_label(entry)
            
        # Convert to list and sort
        results = list(node_stats.values())
        results.sort(key=lambda x: x["count"], reverse=True)
        
        return results

    @staticmethod
    def calculate_health_score(failures: int, total_executions: int = 0) -> float:
        """
        Calculate a 0.0-1.0 health score.
        If total_executions is 0 (unknown), score is based on raw failure count decay.
        """
        if total_executions > 0:
            return max(0.0, 1.0 - (failures / total_executions))
        
        # Heuristic decay: 1 failure = 0.9, 10 failures = 0.5, 100 failures = 0.1
        # Simple exponential decay for now
        import math
        return float(max(0.0, 1.0 * (0.95 ** failures)))
