"""
Tests for R12 TokenEstimator service.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.token_estimator import TokenEstimator, EstimatorConfig

class TestTokenEstimator(unittest.TestCase):
    
    def setUp(self):
        self.config = EstimatorConfig(
            mode="fallback_only", # Force fallback for predictable testing without tiktoken dep
            fallback_chars_per_token=4.0,
            safety_multiplier=1.15
        )
        self.estimator = TokenEstimator(self.config)

    def test_fallback_estimation_logic(self):
        """Test fallback calculation logic."""
        text = "12345678" # 8 chars
        # Expected: 8 / 4.0 = 2 tokens * 1.15 = 2.3 -> ceil(2.3) = 3
        
        estimate = self.estimator.estimate(text)
        
        self.assertEqual(estimate.method, "fallback")
        self.assertEqual(estimate.estimated_tokens, 3)
        self.assertEqual(estimate.chars, 8)
        self.assertEqual(estimate.multiplier_applied, 1.15)

    def test_estimate_empty_string(self):
        """Test empty string handling."""
        estimate = self.estimator.estimate("")
        self.assertEqual(estimate.estimated_tokens, 0)
    
    def test_estimate_section_map(self):
        """Test estimation of a dictionary of sections."""
        sections = {
            "s1": "1234", # 4 chars -> 1 * 1.15 = 1.15 -> 2
            "s2": "12345678" # 8 chars -> 2 * 1.15 = 2.3 -> 3
        }
        
        result = self.estimator.estimate_section_map(sections)
        
        self.assertEqual(result["s1"].estimated_tokens, 2)
        self.assertEqual(result["s2"].estimated_tokens, 3)

    @patch("services.token_estimator.tiktoken")
    @patch("services.token_estimator.TIKTOKEN_AVAILABLE", True)
    def test_tiktoken_estimation(self, mock_tiktoken):
        """Test tiktoken path if available."""
        # Setup mock encoding
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3] # 3 tokens
        mock_tiktoken.get_encoding.return_value = mock_encoding
        mock_tiktoken.encoding_for_model.return_value = mock_encoding
        
        # Use tiktoken preferred config
        tiktoken_config = EstimatorConfig(mode="tiktoken_preferred")
        tiktoken_estimator = TokenEstimator(tiktoken_config)
        
        text = "some text"
        estimate = tiktoken_estimator.estimate(text, model_name="gpt-4")
        
        self.assertEqual(estimate.method, "tiktoken")
        self.assertEqual(estimate.estimated_tokens, 3)
        self.assertEqual(estimate.multiplier_applied, 1.0)

if __name__ == '__main__':
    unittest.main()
