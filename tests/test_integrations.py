
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
            result = ErrorAnalyzer.analyze(traceback_text)
            self.assertIsNotNone(result, f"Failed to detect pattern for: {expected_key}")
            suggestion, metadata = result
            self.assertIsNotNone(suggestion, f"Failed to generate suggestion for: {expected_key}")
            self.assertIn(expected_snippet, suggestion, f"Suggestion content mismatch for: {expected_key}")
            
    def test_logger_timeout(self):
        """Test DoctorLogProcessor buffer timeout mechanism (new architecture)."""
        # Note: New architecture uses SafeStreamWrapper + DoctorLogProcessor
        # The timeout mechanism is now in the background processor thread

        import queue
        from logger import DoctorLogProcessor

        # Create message queue and processor
        message_queue = queue.Queue(maxsize=100)
        processor = DoctorLogProcessor(message_queue)

        try:
            # Start background processor
            processor.start()

            # Simulate start of traceback
            message_queue.put("Traceback (most recent call last):\n")
            time.sleep(0.1)  # Let processor handle the message
            self.assertTrue(processor.in_traceback)

            # Wait for timeout (default is 5 seconds)
            time.sleep(5.2)

            # Write next line, should reset buffer due to timeout
            message_queue.put("  File foo.py line 10\n")
            time.sleep(0.1)  # Let processor handle the message

            self.assertFalse(processor.in_traceback, "Processor should have timed out and reset in_traceback")
            self.assertEqual(len(processor.buffer), 0, "Buffer should be empty after timeout")

        finally:
            processor.stop()
            processor.join(timeout=2.0)

    def test_logger_install_uninstall(self):
        """Test the safe install/uninstall mechanism (new architecture)."""
        # Note: New architecture uses SafeStreamWrapper instead of SmartLogger instances
        from logger import SafeStreamWrapper, install, uninstall

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            log_path = tf.name

        try:
            # Install
            install(log_path)
            self.assertIsInstance(sys.stdout, SafeStreamWrapper)
            self.assertIsInstance(sys.stderr, SafeStreamWrapper)

            # Verify double install doesn't wrap twice
            first_wrapper = sys.stdout
            install(log_path)
            self.assertIs(sys.stdout, first_wrapper, "Double install should not create new wrapper")

            # Uninstall
            uninstall()
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
