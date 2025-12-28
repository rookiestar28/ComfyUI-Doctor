
import unittest
import sys
import io
import time
import os
import tempfile
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
from logger import SmartLogger

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
            suggestion = ErrorAnalyzer.analyze(traceback_text)
            self.assertIsNotNone(suggestion, f"Failed to detect pattern for: {expected_key}")
            self.assertIn(expected_snippet, suggestion, f"Suggestion content mismatch for: {expected_key}")
            
    def test_logger_timeout(self):
        """Test SmartLogger buffer timeout mechanism."""
        # Create a temp log file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            log_path = tf.name
        
        mock_stream = io.StringIO()
        logger = SmartLogger(log_path, mock_stream)
        
        try:
            # Simulate start of traceback
            logger.write("Traceback (most recent call last):\n")
            self.assertTrue(logger.in_traceback)
            
            # Wait for timeout (simulated manually or by time.sleep if logic depended on system time)
            # Since our implementation checks time.time(), we can sleep
            time.sleep(5.1)
            
            # Write next line, should reset buffer due to timeout
            logger.write("  File foo.py line 10\n")
            
            self.assertFalse(logger.in_traceback, "Logger should have timed out and reset in_traceback")
            self.assertEqual(len(logger.buffer), 0, "Buffer should be empty after timeout")
            
        finally:
            logger.close()
            os.remove(log_path)

    def test_logger_install_uninstall(self):
        """Test the safe install/uninstall mechanism."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            log_path = tf.name
            
        try:
            # Install
            SmartLogger.install(log_path)
            self.assertIsInstance(sys.stdout, SmartLogger)
            self.assertIsInstance(sys.stderr, SmartLogger)
            
            # Verify double install doesn't wrap twice
            first_wrapper = sys.stdout
            SmartLogger.install(log_path)
            self.assertIs(sys.stdout, first_wrapper)
            
            # Uninstall
            SmartLogger.uninstall()
            self.assertIs(sys.stdout, original_stdout)
            self.assertIs(sys.stderr, original_stderr)
            
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)
            # Ensure restoration even if test fails
            sys.stdout = original_stdout
            sys.stderr = original_stderr

if __name__ == '__main__':
    unittest.main()
