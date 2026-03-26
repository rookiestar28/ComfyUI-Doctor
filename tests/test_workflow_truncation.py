"""
Tests for R8: Smart Workflow Truncation
"""
import unittest
import sys
import os
import json

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from truncate_workflow import truncate_workflow_smart


class TestWorkflowTruncation(unittest.TestCase):
    """Tests for R8 smart workflow truncation."""
    
    def test_small_workflow_unchanged(self):
        """Small workflows should pass through unchanged."""
        small_workflow = json.dumps({"nodes": [{"id": 1, "type": "KSampler"}]})
        result, meta = truncate_workflow_smart(small_workflow, max_chars=1000)
        
        self.assertEqual(meta["truncation_method"], "none")
        self.assertEqual(result, small_workflow)
    
    def test_empty_workflow(self):
        """Empty workflow should return empty string."""
        result, meta = truncate_workflow_smart("", max_chars=100)
        
        self.assertEqual(result, "")
        self.assertEqual(meta["truncation_method"], "none")
    
    def test_large_workflow_truncated(self):
        """Large workflows should be truncated."""
        # Create a large workflow with many nodes
        nodes = [{"id": i, "type": f"Node{i}", "properties": {"data": "x" * 100}} for i in range(50)]
        large_workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(large_workflow, max_chars=500)
        
        self.assertLess(len(result), len(large_workflow))
        self.assertIn(meta["truncation_method"], ["property_pruning", "node_removal", "char_slice"])
        self.assertIn("original_nodes", meta)
    
    def test_returns_valid_json_or_readable_string(self):
        """Output should be valid JSON or at least readable."""
        nodes = [{"id": i, "type": f"Node{i}"} for i in range(100)]
        workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(workflow, max_chars=200)
        
        # Should either be valid JSON or readable text
        try:
            json.loads(result)
            valid_json = True
        except json.JSONDecodeError:
            valid_json = False
            # If not valid JSON, should at least have truncation marker
            self.assertIn("truncated", result.lower())
    
    def test_preserves_error_node(self):
        """Error node should be preserved when specified."""
        nodes = [
            {"id": "1", "type": "NodeA", "inputs": {}},
            {"id": "2", "type": "NodeB", "inputs": {"a": ["1", 0]}},
            {"id": "3", "type": "NodeC", "inputs": {"b": ["2", 0]}},
            {"id": "4", "type": "NodeD", "inputs": {}},
            {"id": "5", "type": "NodeE", "inputs": {}},
        ]
        # Add some bulk to force truncation
        for node in nodes:
            node["properties"] = {"large_data": "x" * 500}
        
        workflow = json.dumps({"nodes": nodes})
        
        # Truncate with error node = "3"
        result, meta = truncate_workflow_smart(workflow, error_node_id="3", max_chars=800)
        
        # Check that error node 3 is preserved (if node_removal was used)
        if meta["truncation_method"] == "node_removal":
            self.assertTrue(meta.get("error_node_preserved", True))
    
    def test_invalid_json_fallback(self):
        """Invalid JSON should fall back to character truncation."""
        invalid_workflow = "This is not JSON at all, just plain text" * 100
        
        result, meta = truncate_workflow_smart(invalid_workflow, max_chars=100)
        
        self.assertEqual(meta["truncation_method"], "char_slice")
        self.assertLessEqual(len(result), 100)
    
    def test_metadata_contains_required_fields(self):
        """Metadata should contain required fields."""
        workflow = json.dumps({"nodes": [{"id": 1}]})
        _, meta = truncate_workflow_smart(workflow)
        
        self.assertIn("truncation_method", meta)
        self.assertIn("original_length", meta)
    
    def test_property_pruning_preserves_node_count(self):
        """Property pruning should keep all nodes."""
        nodes = [
            {"id": 1, "type": "A", "widgets_values": [1, 2, 3], "pos": [0, 0], "size": [100, 100]},
            {"id": 2, "type": "B", "widgets_values": [4, 5, 6], "pos": [100, 0], "size": [100, 100]},
        ]
        workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(workflow, max_chars=200)
        
        if meta["truncation_method"] == "property_pruning":
            self.assertEqual(meta["original_nodes"], meta["kept_nodes"])

    def test_execution_id_error_node_matches_local_node_id(self):
        """Execution IDs from subgraphs should still preserve the target node."""
        nodes = []
        for i in range(1, 8):
            nodes.append({
                "id": str(i),
                "type": f"Node{i}",
                "inputs": {"x": [str(i - 1), 0]} if i > 1 else {},
                "properties": {"large_data": "x" * 400},
            })
        workflow = json.dumps({"nodes": nodes, "links": []})

        result, meta = truncate_workflow_smart(
            workflow,
            error_node_id="65:70:6",
            max_chars=700,
        )

        self.assertEqual(meta["truncation_method"], "node_removal")
        self.assertTrue(meta.get("error_node_preserved"))
        parsed = json.loads(result)
        self.assertTrue(any(str(node.get("id")) == "6" for node in parsed["nodes"]))

    def test_ui_workflow_pruning_preserves_metadata_and_filters_links(self):
        """UI-format workflow pruning should preserve top-level metadata and valid links."""
        nodes = [
            {"id": "1", "type": "Loader", "inputs": {}, "properties": {"blob": "x" * 400}},
            {"id": "2", "type": "KSampler", "inputs": {"model": ["1", 0]}, "properties": {"blob": "y" * 400}},
            {"id": "3", "type": "SaveImage", "inputs": {"images": ["2", 0]}, "properties": {"blob": "z" * 400}},
            {"id": "4", "type": "Unused", "inputs": {}, "properties": {"blob": "w" * 400}},
        ]
        workflow = json.dumps({
            "nodes": nodes,
            "links": [
                [1, "1", 0, "2", 0, "MODEL"],
                [2, "2", 0, "3", 0, "IMAGE"],
                [3, "4", 0, "3", 1, "IMAGE"],
            ],
            "groups": [{"title": "Subgraph Host"}],
            "extra": {"groupNodes": {"Demo": {"version": 1}}},
        })

        result, meta = truncate_workflow_smart(workflow, error_node_id="2", max_chars=900)

        self.assertIn(meta["truncation_method"], {"property_pruning", "node_removal"})
        parsed = json.loads(result)
        self.assertIn("groups", parsed)
        self.assertIn("extra", parsed)
        self.assertEqual(parsed["groups"][0]["title"], "Subgraph Host")
        kept_ids = {str(node["id"]) for node in parsed["nodes"]}
        for link in parsed["links"]:
            self.assertIn(str(link[1]), kept_ids)
            self.assertIn(str(link[3]), kept_ids)

        if meta["truncation_method"] == "node_removal":
            self.assertNotIn("4", kept_ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
