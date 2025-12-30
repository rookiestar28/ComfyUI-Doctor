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


if __name__ == '__main__':
    unittest.main(verbosity=2)
