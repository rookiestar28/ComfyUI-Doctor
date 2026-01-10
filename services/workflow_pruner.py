"""
R12 Service: Workflow Pruner.
Reduces workflow JSON size by tracing relevant upstream nodes from the error point.
Implements deterministic traversal for consistent testing and A/B validation.
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Literal

logger = logging.getLogger(__name__)

@dataclass
class PruneConfig:
    """Configuration for workflow pruning."""
    max_depth: int = 3
    max_nodes: int = 40
    min_nodes_floor: int = 10
    allow_cycle_break: bool = True
    fallback_recent_nodes_count: int = 20

@dataclass
class PruneResult:
    """Result of workflow pruning."""
    pruned_workflow_json: Dict[str, Any]
    kept_node_ids: List[str]
    dropped_nodes_count: int
    depth_used: int
    nodes_used: int
    mode: Literal["upstream_trace", "fallback_recent_nodes", "metadata_only", "full_pass"]
    reason: str

class WorkflowPruner:
    """
    Intelligent workflow pruning service.
    """
    
    def __init__(self):
        pass

    def prune(self, workflow: Dict[str, Any], target_node_id: Optional[str], config: Optional[PruneConfig] = None) -> PruneResult:
        """
        Prune the workflow to relevant subgraph ending at target_node_id.
        
        Args:
            workflow: The full ComfyUI workflow JSON (API format or UI format).
                      Expected to be API format (dict of node_id -> node_data) for backend.
            target_node_id: The ID of the node where error occurred.
            config: Pruning configuration.
        
        Returns:
            PruneResult containing the reduced workflow.
        """
        config = config or PruneConfig()
        
        # 1. Validation & Format Normalization
        if not workflow or not isinstance(workflow, dict):
            return self._return_empty_result(workflow, "invalid_format")

        # Detect prompt format (API format) vs UI format (with "nodes", "links")
        # Start with API format assumption (node_id -> keys)
        is_api_format = True
        nodes_dict = workflow
        
        # If it looks like UI format (has "nodes" list), we might need conversion or different handling.
        # R12 scope focuses on backend payload which is typically the prompt/API format.
        # Standard ComfyUI API prompt is key-value pairs of node_id -> node_data.
        # Example: {"3": {"inputs": {...}, "class_type": "KSampler"}}
        
        # Check if basic validation holds for API format
        if "nodes" in workflow and isinstance(workflow["nodes"], list):
            # It's UI format (saved workflow)
            # We treat this as "metadata_only" fallback for now or extraction
            # But usually doctor receives the executing prompt which is API format.
            # If we receive UI format, we might fallback to recent nodes or just return as is if small.
            # Let's assume API format for the primary logic as per "node_context" usage.
            is_api_format = False

        if not is_api_format:
            # Fallback for UI format (not structured for upstream tracing easily without conversion)
            # Just truncate if too large?
            # For MVP, we'll try to keep it simple. If not API format, return as is or minimal fallback.
            return self._fallback_pruning(workflow, target_node_id, config, "unsupported_format_fallback")

        # 2. Target Node Validation
        if not target_node_id or str(target_node_id) not in nodes_dict:
            return self._fallback_pruning(workflow, target_node_id, config, "target_node_missing")

        # 3. Upstream Tracing (BFS/DFS)
        try:
            kept_nodes, depth = self._trace_upstream(nodes_dict, str(target_node_id), config)
            
            # Construct pruned workflow
            pruned_workflow = {nid: nodes_dict[nid] for nid in kept_nodes}
            
            dropped_count = len(nodes_dict) - len(kept_nodes)
            
            return PruneResult(
                pruned_workflow_json=pruned_workflow,
                kept_node_ids=sorted(list(kept_nodes)), # Deterministic sort for metadata
                dropped_nodes_count=dropped_count,
                depth_used=depth,
                nodes_used=len(kept_nodes),
                mode="upstream_trace",
                reason="success"
            )
            
        except Exception as e:
            logger.error(f"Pruning failed: {e}")
            return self._fallback_pruning(workflow, target_node_id, config, f"error: {str(e)}")

    def _trace_upstream(self, nodes: Dict[str, Any], start_node: str, config: PruneConfig) -> tuple[Set[str], int]:
        """
        Trace upstream nodes starting from start_node.
        Returns (set of kept node_ids, max_depth_reached).
        """
        visited = set()
        queue = [(start_node, 0)] # (node_id, depth)
        visited.add(start_node)
        
        kept_nodes = {start_node}
        max_depth_reached = 0
        
        # Deterministic traversal:
        # We use a queue, but when we expand inputs, we must do so in a deterministic order.
        
        while queue:
            # Check node limit
            if len(kept_nodes) >= config.max_nodes:
                break
                
            current_id, current_depth = queue.pop(0)
            max_depth_reached = max(max_depth_reached, current_depth)
            
            if current_depth >= config.max_depth:
                continue
            
            node_data = nodes.get(current_id, {})
            inputs = node_data.get("inputs", {})
            
            # Find upstream dependencies
            # In API format, inputs usually look like: "key": ["other_node_id", 0]
            dependencies = []
            
            # Sort input keys for deterministic traversal ordering
            sorted_keys = sorted(inputs.keys())
            
            for key in sorted_keys:
                val = inputs[key]
                if isinstance(val, list) and len(val) == 2:
                    # Potential link: [node_id, output_index]
                    # Check if val[0] is a node_id in our graph
                    upstream_id = str(val[0])
                    if upstream_id in nodes:
                        dependencies.append(upstream_id)
            
            # Add unique dependencies to queue
            for dep_id in dependencies:
                if dep_id not in visited:
                    if len(kept_nodes) < config.max_nodes:
                        visited.add(dep_id)
                        kept_nodes.add(dep_id)
                        queue.append((dep_id, current_depth + 1))
        
        return kept_nodes, max_depth_reached

    def _fallback_pruning(self, workflow: Dict[str, Any], target_id: Optional[str], config: PruneConfig, reason: str) -> PruneResult:
        """
        Fallback strategy when tracing fails or target missing.
        Keeps the last N nodes based on some heuristic (ID sorting or insertion order).
        """
        if not isinstance(workflow, dict):
             return self._return_empty_result(workflow, "invalid_type")
             
        # Heuristic: Sort by Node ID (assuming numeric IDs usually imply creation order)
        # fallback_recent_nodes_count
        
        try:
            # Try to sort keys numerically if possible, else alphanumeric
            sorted_ids = sorted(workflow.keys(), key=lambda x: int(x) if x.isdigit() else x)
            # Keep last N
            keep_ids = sorted_ids[-config.fallback_recent_nodes_count:]
            
            pruned_workflow = {nid: workflow[nid] for nid in keep_ids if nid in workflow}
            
            return PruneResult(
                pruned_workflow_json=pruned_workflow,
                kept_node_ids=keep_ids,
                dropped_nodes_count=len(workflow) - len(pruned_workflow),
                depth_used=0,
                nodes_used=len(pruned_workflow),
                mode="fallback_recent_nodes",
                reason=reason
            )
        except Exception:
            # Absolute fallback: return as is or empty
            return PruneResult(
                pruned_workflow_json=workflow, # Return full as safe fallback? Or empty?
                # A safer budget-conscious fallback might be to return minimal info, 
                # but to be safe for now, let's just return what we have and let budget truncator handle text.
                kept_node_ids=list(workflow.keys()),
                dropped_nodes_count=0,
                depth_used=0,
                nodes_used=len(workflow),
                mode="full_pass",
                reason=f"{reason}_fatal"
            )

    def _return_empty_result(self, original_workflow: Any, reason: str) -> PruneResult:
        return PruneResult(
            pruned_workflow_json={},
            kept_node_ids=[],
            dropped_nodes_count=len(original_workflow) if isinstance(original_workflow, dict) else 0,
            depth_used=0,
            nodes_used=0,
            mode="metadata_only",
            reason=reason
        )
            
    def estimate_tokens(self, data: Any) -> int:
        """Estimate token count for JSON data (legacy helper)."""
        text = json.dumps(data)
        # Rough estimation: 1 token ~= 4 chars
        return len(text) // 4
