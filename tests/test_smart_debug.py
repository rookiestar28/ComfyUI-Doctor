"""
Test suite for the Smart Debug system with i18n support.
Tests logger, analyzer, and i18n modules.
"""

import os
import sys
import time
from unittest.mock import MagicMock

# --- MOCKING DEPENDENCIES ---
# Mock server
class MockPromptServer:
    class instance:
        class routes:
            @staticmethod
            def get(path):
                def decorator(func):
                    return func
                return decorator
            @staticmethod
            def post(path):
                def decorator(func):
                    return func
                return decorator
sys.modules['server'] = MagicMock()
sys.modules['server'].PromptServer = MockPromptServer

# Mock torch
mock_torch = MagicMock()
mock_torch.__version__ = "2.0.1+cu118"
mock_torch.Tensor = str 
mock_torch.cuda.is_available.return_value = True
mock_torch.version.cuda = "11.8"
mock_torch.cuda.device_count.return_value = 1
mock_torch.cuda.get_device_properties.return_value.name = "Mock GPU"
mock_torch.cuda.get_device_properties.return_value.total_memory = 24 * 1024**3
sys.modules['torch'] = mock_torch

# --- END MOCKING ---

# Add Project Root to Path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
sys.path.insert(0, project_root)

node_root = os.path.abspath(os.path.join(current_dir, ".."))
log_dir = os.path.join(node_root, "logs")

print(f">>> TEST: Project Root: {project_root}")
print(">>> TEST: Importing modules...")

try:
    from ComfyUI_Runtime_Diagnostics.i18n import (
        set_language, get_language, get_suggestion, 
        SUPPORTED_LANGUAGES, ERROR_KEYS
    )
    from ComfyUI_Runtime_Diagnostics.analyzer import ErrorAnalyzer
    print("✅ All modules imported successfully.")
except ImportError as e:
    print(f"❌ Import Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# --- Test i18n ---
print("\n" + "="*50)
print("TEST: i18n Module")
print("="*50)

print(f"Supported languages: {SUPPORTED_LANGUAGES}")
print(f"Default language: {get_language()}")

# Test language switching
for lang in SUPPORTED_LANGUAGES:
    success = set_language(lang)
    current = get_language()
    status = "✅" if success and current == lang else "❌"
    print(f"{status} set_language('{lang}'): success={success}, current={current}")

# Test invalid language
success = set_language("invalid_lang")
print(f"{'✅' if not success else '❌'} set_language('invalid_lang'): success={success} (should be False)")

# --- Test Suggestions ---
print("\n" + "="*50)
print("TEST: Suggestion Generation")
print("="*50)

# Reset to Traditional Chinese
set_language("zh_TW")

# Test with arguments
suggestion = get_suggestion(ERROR_KEYS["TYPE_MISMATCH"], "Float16", "Float32")
print(f"Type Mismatch (zh_TW):\n  {suggestion}")

# Test English
set_language("en")
suggestion = get_suggestion(ERROR_KEYS["OOM"])
print(f"OOM (en):\n  {suggestion}")

# Test Japanese
set_language("ja")
suggestion = get_suggestion(ERROR_KEYS["FILE_NOT_FOUND"], "/path/to/model.safetensors")
print(f"File Not Found (ja):\n  {suggestion}")

# --- Test Analyzer ---
print("\n" + "="*50)
print("TEST: ErrorAnalyzer")
print("="*50)

set_language("zh_TW")

test_cases = [
    (
        "Traceback (most recent call last):\n  File ...\nRuntimeError: expected scalar type Float but found Half",
        "TYPE_MISMATCH"
    ),
    (
        "Traceback (most recent call last):\n  File ...\nCUDA out of memory. Tried to allocate 2.00 GiB",
        "OOM"
    ),
    (
        "Traceback (most recent call last):\n  File ...\nKeyError: 'cond_stage_model'",
        "KEY_ERROR"
    ),
    (
        "Traceback (most recent call last):\n  File ...\nAttributeError: 'NoneType' object has no attribute 'to'",
        "ATTRIBUTE_ERROR"
    ),
    (
        "Traceback (most recent call last):\n  File ...\nFileNotFoundError: [Errno 2] No such file or directory: '/models/test.safetensors'",
        "FILE_NOT_FOUND"
    ),
]

for traceback_text, expected_key in test_cases:
    result = ErrorAnalyzer.analyze(traceback_text)
    status = "✅" if result and "💡" in result else "❌"
    print(f"{status} {expected_key}: {'Found suggestion' if result else 'No suggestion'}")

# Test complete traceback detection
print("\n--- Traceback Detection ---")
incomplete = "Traceback (most recent call last):\n  File ..."
complete = "Traceback (most recent call last):\n  File ...\nRuntimeError: test"

print(f"Incomplete: is_complete={ErrorAnalyzer.is_complete_traceback(incomplete)} (expected: False)")
print(f"Complete: is_complete={ErrorAnalyzer.is_complete_traceback(complete)} (expected: True)")

print("\n" + "="*50)
print(">>> ALL TESTS COMPLETE")
print("="*50)
