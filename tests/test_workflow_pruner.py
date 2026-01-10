"""
Tests for R12 WorkflowPruner service.
"""

import unittest
import sys
import os
from typing import Dict, Any

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.workflow_pruner import WorkflowPruner, PruneConfig

class TestWorkflowPruner(unittest.TestCase):
    
    def setUp(self):
        self.pruner = WorkflowPruner()
        self.config = PruneConfig(
            max_depth=3,
            max_nodes=10,
            fallback_recent_nodes_count=2
        )

    def test_prune_basic_upstream(self):
        """Test basic upstream pruning."""
        # Simple chain: 1 -> 2 -> 3(target)
        workflow = {
            "1": {"class_type": "Loader", "inputs": {}},
            "2": {"class_type": "Sampler", "inputs": {"model": ["1", 0]}},
            "3": {"class_type": "Save", "inputs": {"images": ["2", 0]}},
            "4": {"class_type": "Unrelated", "inputs": {}}
        }
        
        result = self.pruner.prune(workflow, "3", self.config)
        
        self.assertEqual(result.mode, "upstream_trace")
        self.assertIn("3", result.kept_node_ids)
        self.assertIn("2", result.kept_node_ids)
        self.assertIn("1", result.kept_node_ids)
        self.assertNotIn("4", result.kept_node_ids) # Unrelated should be pruned
        self.assertEqual(result.nodes_used, 3)

    def test_prune_depth_limit(self):
        """Test max depth limit."""
        # Chain: 1 -> 2 -> 3 -> 4(target)
        # Depth limit 2 means: 4(0), 3(1), 2(2). Node 1 is depth 3.
        # Actually in BFS: 4 is depth 0. 
        # Neighbors of 4 (node 3) is depth 1.
        # Neighbors of 3 (node 2) is depth 2.
        # Neighbors of 2 (node 1) is depth 3.
        # If max_depth=2, we keep depths 0, 1, 2. (So 4, 3, 2). Node 1 should be dropped.
        
        config = PruneConfig(max_depth=2, max_nodes=10)
        
        workflow = {
            "1": {"inputs": {}},
            "2": {"inputs": {"in": ["1", 0]}},
            "3": {"inputs": {"in": ["2", 0]}},
            "4": {"inputs": {"in": ["3", 0]}}
        }
        
        result = self.pruner.prune(workflow, "4", config)
        
        self.assertIn("4", result.kept_node_ids) # depth 0
        self.assertIn("3", result.kept_node_ids) # depth 1
        self.assertIn("2", result.kept_node_ids) # depth 2
        self.assertNotIn("1", result.kept_node_ids) # depth 3 >= max_depth 2? 
        # Wait, if logic is `if current_depth >= config.max_depth: continue`
        # Depth 0 (target) -> expand depth 1.
        # Depth 1 -> expand depth 2.
        # Depth 2 -> expands depth 3?
        # If max_depth is 2. 
        # Pop(4, 0). 0 < 2. Add 3 (1).
        # Pop(3, 1). 1 < 2. Add 2 (2).
        # Pop(2, 2). 2 >= 2. Continue. (Node 1 not added).
        # So yes, Node 1 should be excluded.
        
        self.assertEqual(len(result.kept_node_ids), 3)

    def test_prune_node_limit(self):
        """Test max nodes limit."""
        # 1 -> 2 -> 3(target). Max nodes = 2.
        config = PruneConfig(max_depth=5, max_nodes=2)
        
        workflow = {
            "1": {"inputs": {}},
            "2": {"inputs": {"in": ["1", 0]}},
            "3": {"inputs": {"in": ["2", 0]}}
        }
        
        result = self.pruner.prune(workflow, "3", config)
        
        self.assertIn("3", result.kept_node_ids)
        # Should keep one more. Usually BFS order determines likelihood.
        # 3 depends on 2. So 2 is added.
        # 2 depends on 1. But limit reached.
        
        self.assertEqual(len(result.kept_node_ids), 2)
        self.assertIn("3", result.kept_node_ids)
        self.assertIn("2", result.kept_node_ids)
        self.assertNotIn("1", result.kept_node_ids)

    def test_fallback_missing_target(self):
        """Test fallback when target node missing."""
        workflow = {
            "1": {"inputs": {}},
            "2": {"inputs": {}},
            "3": {"inputs": {}}
        }
        
        # Target "99" missing
        result = self.pruner.prune(workflow, "99", self.config)
        
        self.assertEqual(result.mode, "fallback_recent_nodes")
        # specific config set fallback count to 2
        self.assertEqual(len(result.kept_node_ids), 2)
        # Should be last 2 by ID sort: 2, 3
        self.assertIn("3", result.kept_node_ids)
        self.assertIn("2", result.kept_node_ids)
        self.assertNotIn("1", result.kept_node_ids)

    def test_deterministic_traversal(self):
        """Test that traversal is deterministic (order of inputs)."""
        # Node 3 depends on 2 and 1.
        # If traversal isn't sorted, we might visit 1 or 2 first.
        # With sorting, we should always visit 1 then 2 (if keys are "a", "b") or based on key names.
        
        workflow = {
            "1": {"inputs": {}},
            "2": {"inputs": {}},
            "3": {"inputs": {
                "b_input": ["2", 0],
                "a_input": ["1", 0]
            }}
        }
        
        # Input keys: "a_input", "b_input". Sorted: a, b.
        # Should visit 1 ("a_input") then 2 ("b_input").
        
        # To test this, we set max_nodes=2 (target + 1 neighbor).
        # Target is 3. 
        # If "a" comes first, 1 is visited. Limit reached. 2 excluded.
        # If "b" comes first, 2 is visited. Limit reached. 1 excluded.
        
        config = PruneConfig(max_nodes=2)
        result = self.pruner.prune(workflow, "3", config)
        
        self.assertIn("3", result.kept_node_ids)
        self.assertIn("1", result.kept_node_ids) # "a_input" -> node 1
        self.assertNotIn("2", result.kept_node_ids) # "b_input" -> node 2 (dropped)


if __name__ == '__main__':
    unittest.main()
