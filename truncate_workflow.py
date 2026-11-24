"""
R8: Smart Workflow Truncation

Provides intelligent truncation of ComfyUI workflow JSON that:
1. Preserves error-related nodes and their connections
2. Keeps nodes within N hops of the error node
3. Falls back to property pruning before node removal
4. Returns metadata about what was truncated
"""
import json
from collections import defaultdict
from typing import Any, Optional


def _normalize_error_node_id(error_node_id: Optional[str]) -> Optional[str]:
    """Normalize execution IDs like '12:34:56' to their local node id."""
    if error_node_id is None:
        return None
    text = str(error_node_id)
    if not text:
        return None
    return text.split(':')[-1]


def _has_ui_nodes(workflow: Any) -> bool:
    """True for a serialized graph (``{"nodes": [...], ...}``); an API prompt is ``{"<id>": {...}}``."""
    return isinstance(workflow, dict) and isinstance(workflow.get("nodes"), list)


def _node_entries(workflow: Any) -> list[tuple[str, dict]]:
    """``(id, node)`` pairs for every accepted shape; entries that are not objects carry no identity.

    The id is the node's ``id`` member for a graph or a list and the KEY for an API prompt, whose nodes
    have no ``id`` member. Reading ``node.get("id")`` on an API prompt raised ``AttributeError`` (its
    iteration yielded the key strings) and the "first N nodes" fallback matched list positions, not keys.
    """
    if _has_ui_nodes(workflow):
        return [(str(node.get("id", "")), node) for node in workflow["nodes"] if isinstance(node, dict)]
    if isinstance(workflow, dict):
        return [(str(key), node) for key, node in workflow.items() if isinstance(node, dict)]
    if isinstance(workflow, list):
        return [(str(node.get("id", "")), node) for node in workflow if isinstance(node, dict)]
    return []


def truncate_workflow_smart(
    workflow_str: Any,
    error_node_id: Optional[str] = None,
    max_chars: int = 4000,
    max_hops: int = 2
) -> tuple[str, dict]:
    """
    Smartly truncate a workflow JSON string while preserving relevant context.
    
    Args:
        workflow_str: The workflow as a JSON string (or simplified text), or an already parsed dict or
            list. The budget is measured on the serialized text for every shape; an input within the
            budget is returned unchanged (same object), an input over it comes back as a string.
        error_node_id: ID of the node that caused the error (prioritized). An execution id such as
            "12:34" matches a node with exactly that id first, then its last segment.
        max_chars: Maximum character length for output
        max_hops: Connection hops from the error node to keep (0 = the node alone, 1 = its direct
            neighbors in both directions, ...). When that neighborhood does not fit ``max_chars`` the
            largest smaller one that does is kept.
        
    Returns:
        Tuple of (truncated_workflow_str, metadata_dict)
        
        metadata_dict contains:
        - original_length: Original string length
        - truncated_length: Final string length
        - original_nodes: Number of nodes before truncation
        - kept_nodes: Number of nodes after truncation
        - truncation_method: "none", "property_pruning", "node_removal", or "char_slice"
        - error_node_preserved: Whether the error node is in the output (None when no error node was given)
    """
    if not workflow_str:
        return "", {"truncation_method": "none", "original_length": 0}

    # IMPORTANT: measure the serialized text for every shape. A dict or list used to be measured by its
    # key or element count, so it was never truncated and bypassed the token budget entirely.
    source = workflow_str
    if isinstance(source, str):
        workflow_text = source
    else:
        try:
            workflow_text = json.dumps(source, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError):
            workflow_text = str(source)

    original_length = len(workflow_text)

    # If already under limit, return as-is
    if original_length <= max_chars:
        return source, {
            "truncation_method": "none",
            "original_length": original_length,
            "truncated_length": original_length
        }
    
    # Try to parse as JSON
    try:
        workflow = json.loads(workflow_text)
    except json.JSONDecodeError:
        # Not valid JSON, fall back to simple character truncation
        truncated = workflow_text[:max(max_chars - 50, 0)] + "\n\n[... workflow truncated ...]"
        return truncated, {
            "truncation_method": "char_slice",
            "original_length": original_length,
            "truncated_length": len(truncated),
            "reason": "invalid_json"
        }
    
    # Workflow can be dict (API format) or has "nodes" key
    nodes = None
    if _has_ui_nodes(workflow):
        nodes = workflow["nodes"]
    elif isinstance(workflow, dict):
        if all(isinstance(v, dict) for v in workflow.values()):
            # Dict of node_id -> node_data format
            nodes = list(workflow.values())
    elif isinstance(workflow, list):
        nodes = workflow

    if not nodes:
        # Unknown format, use character truncation
        truncated = workflow_text[:max(max_chars - 50, 0)] + "\n\n[... workflow truncated ...]"
        return truncated, {
            "truncation_method": "char_slice",
            "original_length": original_length,
            "truncated_length": len(truncated),
            "reason": "unknown_format"
        }
    
    original_node_count = len(nodes)
    error_node_preserved = False

    # An execution id is "<subgraph>:<node>"; the exact spelling wins because API prompts of a subgraph
    # are keyed by the full id, and the last segment is the fallback for a graph's local ids.
    known_ids = {entry_id for entry_id, _ in _node_entries(workflow)}
    normalized_error_node_id = (
        str(error_node_id)
        if error_node_id is not None and str(error_node_id) in known_ids
        else _normalize_error_node_id(error_node_id)
    )

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
            # Every node is kept, so the error node is preserved exactly when the workflow has it.
            "error_node_preserved": (normalized_error_node_id in known_ids) if normalized_error_node_id else None
        }

    # Strategy 2: Node removal (keep error node and neighbors)
    filtered_source_workflow = pruned_workflow if _has_ui_nodes(workflow) else workflow
    filtered_source_nodes = filtered_source_workflow["nodes"] if _has_ui_nodes(workflow) else nodes
    # The documented hop count is tried first; a neighborhood that does not fit the budget degrades hop
    # by hop (down to the error node alone) instead of collapsing into a character slice.
    for hops in range(max_hops if normalized_error_node_id else 0, -1, -1):
        if normalized_error_node_id:
            priority_nodes = _get_priority_nodes(workflow, normalized_error_node_id, hops)
        else:
            # No error node specified, keep first N nodes
            priority_nodes = {entry_id for entry_id, _ in _node_entries(workflow)[:20]}
        filtered_workflow = _filter_nodes(filtered_source_workflow, filtered_source_nodes, priority_nodes)
        filtered_str = json.dumps(filtered_workflow, ensure_ascii=False, separators=(',', ':'))
        if len(filtered_str) <= max_chars:
            break

    kept_entries = _node_entries(filtered_workflow)
    kept_node_count = len(kept_entries)
    # Check if error node is preserved
    if normalized_error_node_id:
        error_node_preserved = any(entry_id == normalized_error_node_id for entry_id, _ in kept_entries)

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
    truncated = filtered_str[:max(max_chars - 80, 0)] + ',"_truncated":true}'
    # Ensure valid JSON by trying to close it properly
    try:
        json.loads(truncated)
    except json.JSONDecodeError:
        # Can't make valid JSON, just slice
        truncated = filtered_str[:max(max_chars - 50, 0)] + "\n\n[... workflow truncated ...]"
    
    if error_node_preserved:
        # The slice is a prefix of filtered_str, so the node survives only if its whole text does.
        error_text = next(
            json.dumps(node, ensure_ascii=False, separators=(',', ':'))
            for entry_id, node in kept_entries
            if entry_id == normalized_error_node_id
        )
        error_node_preserved = error_text in truncated

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
    # IMPORTANT: the host frontend serializes every widget value twice: positionally (`widgets_values`)
    # and by name (`widgets_values_named`). Both are pruned together. Pruning only the positional copy
    # leaves the named copy (including full prompt text) in Strategy 1, which then overflows the budget
    # and collapses a workflow that fits into a node_removal result holding only the error node.
    PRUNE_KEYS = {"widgets_values", "widgets_values_named", "pos", "size", "order", "mode", "flags", "color", "bgcolor"}

    def trim_value(value):
        if isinstance(value, str) and len(value) > 100:
            return value[:100] + "..."
        if isinstance(value, dict):
            return {k: trim_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [trim_value(v) for v in value]
        return value

    def prune_node(node: Any) -> Any:
        if not isinstance(node, dict):
            return trim_value(node)
        pruned = {}
        for key, value in node.items():
            if key in PRUNE_KEYS:
                continue
            if key in {"inputs", "properties"} and isinstance(value, dict):
                pruned[key] = {k: trim_value(v) for k, v in value.items()}
            else:
                pruned[key] = trim_value(value)
        return pruned

    pruned_nodes = [prune_node(n) for n in nodes]

    if isinstance(workflow, dict):
        if _has_ui_nodes(workflow):
            result = {k: v for k, v in workflow.items() if k != "nodes"}
            result["nodes"] = pruned_nodes
            return result
        return {k: prune_node(v) if isinstance(v, dict) else v for k, v in workflow.items()}
    return pruned_nodes


def _get_priority_nodes(workflow: dict | list, error_node_id: str, max_hops: int) -> set:
    """Get node IDs within max_hops of the error node (0 = the node alone)."""
    # Build adjacency map
    node_map = {}
    adjacency = {}

    for node_id, node in _node_entries(workflow):
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

    # IMPORTANT: UI-format workflows (what the host frontend serializes) carry no connections inside a
    # node: `inputs` is a list of slot dicts and every connection is a top-level `links` row
    # [link_id, origin_id, origin_slot, target_id, target_slot, type]. Without this, the neighborhood of
    # the error node is the error node alone and every over-budget UI workflow loses its context.
    # Rows are untrusted JSON: skip anything that is not a well-formed row between two known nodes
    # instead of raising (a self link is harmless: it only re-adds a node to its own neighborhood).
    # The dict-input branch above stays the only authority for API-format nodes.
    links = workflow.get("links") if isinstance(workflow, dict) else None
    if isinstance(links, list):
        for row in links:
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                continue
            origin_id, target_id = str(row[1]), str(row[3])
            if origin_id not in node_map or target_id not in node_map:
                continue
            if isinstance(node_map[target_id].get("inputs", []), dict):
                continue
            adjacency[target_id].add(origin_id)

    # Nodes that connect TO a node, indexed once instead of rescanning every node per frontier member.
    dependents = defaultdict(set)
    for nid, neighbors in adjacency.items():
        for neighbor in neighbors:
            dependents[neighbor].add(nid)

    # BFS from error node
    priority = {str(error_node_id)}
    frontier = {str(error_node_id)}

    for _ in range(max_hops):
        next_frontier = set()
        for node_id in frontier:
            # Add neighbors
            next_frontier.update(adjacency.get(node_id, set()))
            # Add nodes that connect TO this node
            next_frontier.update(dependents.get(node_id, set()))
        # IMPORTANT: the next frontier is what is NEW. Subtracting after `priority` already held the new
        # nodes emptied it, so every hop count beyond 1 returned the one-hop neighborhood.
        frontier = next_frontier - priority
        if not frontier:
            break
        priority.update(frontier)

    return priority


def _filter_links_for_nodes(links: list, keep_ids: set) -> list:
    """Keep only links whose endpoints are preserved nodes."""
    filtered = []
    for link in links:
        if not isinstance(link, list) or len(link) < 4:
            filtered.append(link)
            continue
        origin_id = str(link[1]) if len(link) > 1 else None
        target_id = str(link[3]) if len(link) > 3 else None
        if origin_id in keep_ids and target_id in keep_ids:
            filtered.append(link)
    return filtered


def _preserve_workflow_shell(workflow: dict, filtered_nodes: list, keep_ids: set) -> dict:
    """Preserve UI workflow metadata when pruning nodes."""
    result = {k: v for k, v in workflow.items() if k not in {"nodes", "links"}}
    result["nodes"] = filtered_nodes
    if isinstance(workflow.get("links"), list):
        result["links"] = _filter_links_for_nodes(workflow["links"], keep_ids)
    return result


def _filter_nodes(workflow: dict | list, nodes: list, keep_ids: set) -> dict | list:
    """Filter workflow to only keep specified node IDs."""
    filtered = [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")) in keep_ids]

    if isinstance(workflow, dict):
        if _has_ui_nodes(workflow):
            return _preserve_workflow_shell(workflow, filtered, keep_ids)
        return {k: v for k, v in workflow.items() if str(k) in keep_ids}
    return filtered
