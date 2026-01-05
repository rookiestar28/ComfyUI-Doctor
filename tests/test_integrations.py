
import unittest
import sys
import os
import time
from unittest.mock import MagicMock

# --- PATH SETUP ---
# Add Project Root (ComfyUI-Doctor) to Path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- MOCKING ---
mock_torch = MagicMock()
mock_torch.__version__ = "2.0.1+cu118"
mock_torch.Tensor = str
mock_torch.cuda.is_available.return_value = True
mock_torch.version.cuda = "11.8"
mock_torch.cuda.device_count.return_value = 1
mock_torch.cuda.get_device_properties.return_value.name = "Mock GPU"
mock_torch.cuda.get_device_properties.return_value.total_memory = 24 * 1024**3
sys.modules['torch'] = mock_torch
sys.modules['server'] = MagicMock() # Also mock server just in case

from analyzer import ErrorAnalyzer, NodeContext, ERROR_KEYS
from i18n import set_language, get_suggestion
from logger import SmartLogger, clear_analysis_history, get_last_analysis

class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        # Ensure clean state by uninstalling any existing logger hooks
        # This is needed because importing __init__ might auto-install them
        SmartLogger.uninstall()
        set_language("en")

    def tearDown(self):
        SmartLogger.uninstall()

    def test_new_error_patterns(self):
        """Test the detection of the 6 new error patterns."""
        
        test_cases = [
            (
                "safetensors_rust.SafetensorError: Error while deserializing header\n",
                ERROR_KEYS["SAFETENSORS_ERROR"],
                "SafeTensors Error"
            ),
            (
                "RuntimeError: cuDNN error: CUDNN_STATUS_EXECUTION_FAILED\n",
                ERROR_KEYS["CUDNN_ERROR"],
                "CUDNN Execution Failed"
            ),
            (
                "ModuleNotFoundError: No module named 'insightface'\n",
                ERROR_KEYS["MISSING_INSIGHTFACE"],
                "Missing InsightFace"
            ),
            (
                "RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn\n",
                ERROR_KEYS["MODEL_VAE_MISMATCH"],
                "Model/VAE Mismatch"
            ),
            (
                "MPS backend out of memory\n",
                ERROR_KEYS["MPS_OOM"],
                "MPS (Mac) OOM"
            ),
            (
                "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)\n",
                ERROR_KEYS["INVALID_PROMPT"],
                "Invalid Prompt Format"
            )
        ]

        for traceback_text, expected_key, expected_snippet in test_cases:
            result = ErrorAnalyzer.analyze(traceback_text)
            self.assertIsNotNone(result, f"Failed to detect pattern for: {expected_key}")
            suggestion, _metadata = result
            self.assertIsNotNone(suggestion, f"Failed to generate suggestion for: {expected_key}")
            self.assertIn(expected_snippet, suggestion, f"Suggestion content mismatch for: {expected_key}")
            
    def test_logger_validation_error_capture(self):
        """Test validation error capture via on_flush callback."""
        SmartLogger.install("test.log")
        clear_analysis_history()

        print("Failed to validate prompt for output 1:")
        print("* KSampler 1:")
        print("  - Return type mismatch between linked nodes: scheduler")
        print("Executing prompt: test-123")
        time.sleep(0.2)

        last = get_last_analysis()

        self.assertIsNotNone(last.get("error"))
        self.assertIn("Failed to validate", last.get("error", ""))

if __name__ == '__main__':
    unittest.main()
