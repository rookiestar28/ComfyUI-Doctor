"""
Tests for R12 TokenBudget service.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.token_budget import TokenBudgetService, BudgetConfig, BudgetResult
from services.token_estimator import TokenEstimate

class TestTokenBudget(unittest.TestCase):
    
    def setUp(self):
        # Mock dependencies
        self.mock_estimator = MagicMock()
        self.mock_pruner = MagicMock()
        
        # Setup estimator to return predictable low values by default
        self.mock_estimator.estimate.return_value = TokenEstimate(
            estimated_tokens=100, method="fallback", multiplier_applied=1.0, chars=400, tokens_per_char=4.0
        )
        
        self.service = TokenBudgetService(estimator=self.mock_estimator, pruner=self.mock_pruner)
        
        self.payload = {
            "messages": [],
            "error_context": {
                "error": "Some error",
                "traceback": "line1\nline2\nline3",
                "workflow": {"1": {}, "2": {}}
            }
        }

    def test_budget_disabled(self):
        """Test disabled budget."""
        config = BudgetConfig(enabled_remote=False)
        res, meta = self.service.apply_token_budget(self.payload, True, config)
        
        self.assertEqual(res, self.payload)
        self.assertEqual(meta, {})

    def test_budget_within_soft_limit(self):
        """Test payload within soft limit."""
        config = BudgetConfig(enabled_remote=True, soft_max_tokens=1000)
        # Mock size: 100 tokens + 1000 overhead = 1100 > 1000? 
        # Wait, overhead is hardcoded 1000 in service.
        # Estimator returns 100. Total 1100.
        # If soft limit is 2000, should pass.
        config.soft_max_tokens = 2000
        
        res, meta = self.service.apply_token_budget(self.payload, True, config)
        
        self.assertEqual(res, self.payload)
        self.assertTrue(meta["token_budget"]["enabled"])
        self.assertFalse(meta["trim"]["degraded"])

    def test_progressive_trimming_workflow(self):
        """Test trimming triggers workflow prune."""
        config = BudgetConfig(
            enabled_remote=True, 
            soft_max_tokens=500, # Very low limit to force trim
            hard_max_tokens=800,
            trimming_policy="remote_strict"
        )
        # Total estimated roughly 1100 (100 + 1000 overhead).
        # Should trigger trim loop.
        
        # Mock pruner result
        mock_prune_res = MagicMock()
        mock_prune_res.pruned_workflow_json = {"1": {}} # Pruned
        mock_prune_res.mode = "upstream_trace"
        mock_prune_res.kept_node_ids = ["1"]
        mock_prune_res.dropped_nodes_count = 1
        self.mock_pruner.prune.return_value = mock_prune_res
        
        # Make estimator return smaller value after pruning call
        # Initial call: 1100 total
        # Second call (after prune): return 50 tokens (total 1050) -> still > 800? 
        # Need it to reduce enough to stop or go deeper.
        
        # side_effect for estimator.estimate:
        # 1. Initial full payload
        # 2. Pruned payload (checked inside loop)
        counts = [100, 50, 40, 30] # Decreasing size
        
        def side_effect(text):
            val = counts.pop(0) if counts else 10
            return TokenEstimate(val, "fallback", 1.0, val*4, 4.0)
            
        self.mock_estimator.estimate.side_effect = side_effect
        
        res, meta = self.service.apply_token_budget(self.payload, True, config)
        
        # Verify pruning was called
        self.mock_pruner.prune.assert_called()
        self.assertTrue(meta["pruning"]["applied"])
        self.assertIn("prune_workflow", meta["trim"]["steps"][0])
        self.assertTrue(meta["trim"]["degraded"])

    def test_hard_cap_strictness(self):
        """Test that strict mode tries multiple steps."""
        config = BudgetConfig(
            enabled_remote=True, 
            soft_max_tokens=100, 
            hard_max_tokens=200, 
            trimming_policy="remote_strict"
        )
        
        # Setup mock pruner to return serializable data
        mock_prune_res = MagicMock()
        mock_prune_res.pruned_workflow_json = {"1": {}}
        mock_prune_res.kept_node_ids = ["1"]
        mock_prune_res.dropped_nodes_count = 1
        mock_prune_res.mode = "upstream_trace"
        self.mock_pruner.prune.return_value = mock_prune_res
        
        res, meta = self.service.apply_token_budget(self.payload, True, config)
        
        # Check that it tried multiple steps
        steps = meta["trim"]["steps"]
        self.assertTrue(len(steps) > 1)
        self.assertIn("drop_system_info", str(steps))
        self.assertIn("truncate_traceback", str(steps))

if __name__ == '__main__':
    unittest.main()
