"""
R8: Smart Workflow Truncation

Provides intelligent truncation of ComfyUI workflow JSON that:
1. Preserves error-related nodes and their connections
2. Keeps nodes within N hops of the error node
3. Falls back to property pruning before node removal
4. Returns metadata about what was truncated
"""
import json
from typing import Optional


def truncate_workflow_smart(
    workflow_str: str,
    error_node_id: Optional[str] = None,
    max_chars: int = 4000,
    max_hops: int = 2
) -> tuple[str, dict]:
    """
    Smartly truncate a workflow JSON string while preserving relevant context.
    
    Args:
        workflow_str: The workflow JSON as a string (or simplified text)
        error_node_id: ID of the node that caused the error (prioritized)
        max_chars: Maximum character length for output
        max_hops: How many connection hops from error node to keep
        
    Returns:
        Tuple of (truncated_workflow_str, metadata_dict)
        
        metadata_dict contains:
        - original_length: Original string length
        - truncated_length: Final string length
        - original_nodes: Number of nodes before truncation
        - kept_nodes: Number of nodes after truncation
        - truncation_method: "none", "property_pruning", "node_removal", or "char_slice"
        - error_node_preserved: Whether the error node was kept
    """
    if not workflow_str:
        return "", {"truncation_method": "none", "original_length": 0}
    
    original_length = len(workflow_str)
    
    # If already under limit, return as-is
    if original_length <= max_chars:
        return workflow_str, {
            "truncation_method": "none",
            "original_length": original_length,
            "truncated_length": original_length
        }
    
    # Try to parse as JSON
    try:
        workflow = json.loads(workflow_str)
    except json.JSONDecodeError:
        # Not valid JSON, fall back to simple character truncation
        truncated = workflow_str[:max_chars - 50] + "\n\n[... workflow truncated ...]"
        return truncated, {
            "truncation_method": "char_slice",
            "original_length": original_length,
            "truncated_length": len(truncated),
            "reason": "invalid_json"
        }
    
    # Workflow can be dict (API format) or has "nodes" key
    nodes = None
    if isinstance(workflow, dict):
        if "nodes" in workflow:
            nodes = workflow["nodes"]
        elif all(isinstance(v, dict) for v in workflow.values()):
            # Dict of node_id -> node_data format
            nodes = list(workflow.values())
    elif isinstance(workflow, list):
        nodes = workflow
    
    if not nodes:
        # Unknown format, use character truncation
        truncated = workflow_str[:max_chars - 50] + "\n\n[... workflow truncated ...]"
        return truncated, {
            "truncation_method": "char_slice",
            "original_length": original_length,
            "truncated_length": len(truncated),
            "reason": "unknown_format"
        }
    
    original_node_count = len(nodes)
    error_node_preserved = False
    
    # Strategy 1: Property pruning (keep all nodes but remove verbose properties)
    pruned_workflow = _prune_node_properties(workflow, nodes)
    pruned_str = json.dumps(pruned_workflow, ensure_ascii=False, separators=(',', ':'))
    
    if len(pruned_str) <= max_chars:
        return pruned_str, {
            "truncation_method": "property_pruning",
            "original_length": original_length,
            "truncated_length": len(pruned_str),
            "original_nodes": original_node_count,
            "kept_nodes": original_node_count,
            "error_node_preserved": True if error_node_id else None
        }
    
    # Strategy 2: Node removal (keep error node and neighbors)
    if error_node_id:
        priority_nodes = _get_priority_nodes(workflow, error_node_id, max_hops)
    else:
        # No error node specified, keep first N nodes
        priority_nodes = set(str(n.get("id", i)) for i, n in enumerate(nodes[:20]))
    
    filtered_workflow = _filter_nodes(workflow, nodes, priority_nodes)
    filtered_str = json.dumps(filtered_workflow, ensure_ascii=False, separators=(',', ':'))
    
    # Check if error node is preserved
    if error_node_id:
        for n in (filtered_workflow.get("nodes", []) if isinstance(filtered_workflow, dict) else filtered_workflow):
            if str(n.get("id", "")) == str(error_node_id):
                error_node_preserved = True
                break
    
    kept_node_count = len(filtered_workflow.get("nodes", filtered_workflow) if isinstance(filtered_workflow, dict) else filtered_workflow)
    
    if len(filtered_str) <= max_chars:
        return filtered_str, {
            "truncation_method": "node_removal",
            "original_length": original_length,
            "truncated_length": len(filtered_str),
            "original_nodes": original_node_count,
            "kept_nodes": kept_node_count,
            "error_node_preserved": error_node_preserved
        }
    
    # Strategy 3: Final fallback - character truncation with note
    truncated = filtered_str[:max_chars - 80] + ',"_truncated":true}'
    # Ensure valid JSON by trying to close it properly
    try:
        json.loads(truncated)
    except json.JSONDecodeError:
        # Can't make valid JSON, just slice
        truncated = filtered_str[:max_chars - 50] + "\n\n[... workflow truncated ...]"
    
    return truncated, {
        "truncation_method": "char_slice",
        "original_length": original_length,
        "truncated_length": len(truncated),
        "original_nodes": original_node_count,
        "kept_nodes": kept_node_count,
        "error_node_preserved": error_node_preserved
    }


def _prune_node_properties(workflow: dict | list, nodes: list) -> dict | list:
    """Remove verbose/non-essential properties from nodes."""
    ESSENTIAL_KEYS = {"id", "type", "class_type", "inputs", "outputs", "title", "properties"}
    PRUNE_KEYS = {"widgets_values", "pos", "size", "order", "mode", "flags", "color", "bgcolor"}
    
    def prune_node(node: dict) -> dict:
        pruned = {}
        for key, value in node.items():
            if key in PRUNE_KEYS:
                continue
            if key == "inputs" and isinstance(value, dict):
                # Keep input connections but truncate large text values
                pruned_inputs = {}
                for inp_key, inp_val in value.items():
                    if isinstance(inp_val, str) and len(inp_val) > 100:
                        pruned_inputs[inp_key] = inp_val[:100] + "..."
                    else:
                        pruned_inputs[inp_key] = inp_val
                pruned[key] = pruned_inputs
            else:
                pruned[key] = value
        return pruned
    
    if isinstance(workflow, dict):
        if "nodes" in workflow:
            return {"nodes": [prune_node(n) for n in nodes]}
        else:
            return {k: prune_node(v) if isinstance(v, dict) else v for k, v in workflow.items()}
    else:
        return [prune_node(n) for n in nodes]


def _get_priority_nodes(workflow: dict | list, error_node_id: str, max_hops: int) -> set:
    """Get node IDs within max_hops of the error node."""
    nodes = workflow.get("nodes", workflow) if isinstance(workflow, dict) else workflow
    
    # Build adjacency map
    node_map = {}
    adjacency = {}
    
    for node in nodes:
        node_id = str(node.get("id", ""))
        node_map[node_id] = node
        adjacency[node_id] = set()
        
        # Check inputs for connections
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict):
            for inp_key, inp_val in inputs.items():
                # Connection format: [node_id, output_index] or just node_id
                if isinstance(inp_val, list) and len(inp_val) >= 1:
                    adjacency[node_id].add(str(inp_val[0]))
                elif isinstance(inp_val, (int, str)) and str(inp_val) in node_map:
                    adjacency[node_id].add(str(inp_val))
    
    # BFS from error node
    priority = {str(error_node_id)}
    frontier = {str(error_node_id)}
    
    for _ in range(max_hops):
        next_frontier = set()
        for node_id in frontier:
            # Add neighbors
            next_frontier.update(adjacency.get(node_id, set()))
            # Add nodes that connect TO this node
            for nid, neighbors in adjacency.items():
                if node_id in neighbors:
                    next_frontier.add(nid)
        priority.update(next_frontier)
        frontier = next_frontier - priority
    
    return priority


def _filter_nodes(workflow: dict | list, nodes: list, keep_ids: set) -> dict | list:
    """Filter workflow to only keep specified node IDs."""
    filtered = [n for n in nodes if str(n.get("id", "")) in keep_ids]
    
    if isinstance(workflow, dict):
        if "nodes" in workflow:
            return {"nodes": filtered}
        else:
            return {k: v for k, v in workflow.items() if str(k) in keep_ids}
    else:
        return filtered
