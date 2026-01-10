"""
Golden Tests for R12 Smart Token Budget.
Ensures deterministic behavior for critical pruning/budgeting logic.
"""

import unittest
import json
import os
import sys

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.workflow_pruner import WorkflowPruner, PruneConfig, PruneResult
from services.token_budget import TokenBudgetService, BudgetConfig

class TestR12Golden(unittest.TestCase):
    
    def setUp(self):
        self.pruner = WorkflowPruner()
        self.budget = TokenBudgetService(pruner=self.pruner) # Use real pruner
        
        # Golden Workflow: A diamond structure + chain
        # 1 -> 2 -> 4 -> 5(target)
        # 1 -> 3 -> 4 -> 5
        # 6 (unconnected)
        self.golden_workflow = {
            "1": {"class_type": "Loader", "inputs": {"seed": 123}},
            "2": {"class_type": "Processor", "inputs": {"in": ["1", 0]}},
            "3": {"class_type": "Processor", "inputs": {"in": ["1", 0]}},
            "4": {"class_type": "Merger", "inputs": {"in1": ["2", 0], "in2": ["3", 0]}},
            "5": {"class_type": "Saver", "inputs": {"in": ["4", 0]}},
            "6": {"class_type": "Unconnected", "inputs": {}}
        }
        self.target_id = "5"

    def test_golden_pruning_deterministic(self):
        """
        Verify that pruning the golden workflow ALWAY yields the same result.
        """
        config = PruneConfig(
            max_depth=10, 
            max_nodes=10 # Sufficient to keep all connected
        )
        
        result = self.pruner.prune(self.golden_workflow, self.target_id, config)
        
        expected_kept = ["1", "2", "3", "4", "5"]
        self.assertEqual(sorted(result.kept_node_ids), sorted(expected_kept))
        self.assertNotIn("6", result.kept_node_ids)
        
        # Verify deterministic output structure
        json_output = json.dumps(result.pruned_workflow_json, sort_keys=True)
        # Check integrity - just ensure it runs and outputs logic
        self.assertEqual(len(result.pruned_workflow_json), 5)

    def test_golden_pruning_depth_cutoff(self):
        """
        Verify depth cutoff behaves exactly as expected on diamond graph.
        Target(5) -> Depth 0
        Merger(4) -> Depth 1
        Proc(2,3) -> Depth 2
        Loader(1) -> Depth 3
        
        If max_depth=2, should keep 5, 4, 3, 2. Drop 1.
        """
        config = PruneConfig(max_depth=2, max_nodes=10)
        result = self.pruner.prune(self.golden_workflow, self.target_id, config)
        
        expected_kept = ["2", "3", "4", "5"] # Nodes at depth 0, 1, 2
        self.assertEqual(sorted(result.kept_node_ids), sorted(expected_kept))
        self.assertNotIn("1", result.kept_node_ids)

    def test_golden_budget_trimming(self):
        """
        Verify budget application on golden payload.
        """
        payload = {
            "error_context": {
                "workflow": self.golden_workflow,
                "node_context": {"node_id": self.target_id},
                "traceback": "\n".join([f"Line {i}" for i in range(20)])
            }
        }
        
        # Set budget very tight to force prune + traceback cut
        config = BudgetConfig(
            enabled_remote=True,
            soft_max_tokens=10, 
            hard_max_tokens=800, # Large enough to not fail completely, but small enough to force trim (overhead is 1000)
            trimming_policy="remote_strict",
            prune_default_depth=2
        )
        
        res, meta = self.budget.apply_token_budget(payload, True, config)
        
        # Should have pruned workflow
        self.assertTrue(meta["pruning"]["applied"])
        # kept nodes should match depth 2 test above + node reduction implies maybe less
        
        # Should have truncated traceback
        trim_steps = str(meta["trim"]["steps"])
        self.assertIn("truncate_traceback", trim_steps)
        
        # Check traceback modification
        tb = res["error_context"]["traceback"]
        self.assertIn("...[truncated]...", tb)

if __name__ == '__main__':
    unittest.main()
