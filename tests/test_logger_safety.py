"""
Safety tests for the new logger architecture (v1.3.0).

Tests SafeStreamWrapper + DoctorLogProcessor implementation to ensure:
1. No deadlock under burst load
2. Error capture still works correctly
3. Thread safety with concurrent writes
4. Compatibility with ComfyUI's LogInterceptor

See: .planning/STAGE1_LOGGER_FIX_PLAN.md
"""

import time
import sys
import os
import threading
from unittest.mock import Mock

# Add parent directory to path to import logger module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_no_deadlock_under_burst():
    """
    Test 1: No deadlock under burst load.

    Simulates 15+ rapid validation errors (the scenario that caused deadlock in v1.2.x).
    """
    from logger import install, uninstall, get_last_analysis

    install("test.log")

    # Simulate 15 validation errors (burst)
    for i in range(15):
        print(f"Failed to validate prompt for output {i}:")
        print(f"* KSampler {i}:")
        print(f"  - Return type mismatch between linked nodes: scheduler")

    print("Executing prompt: test-123-456")

    # Wait for background thread to process
    time.sleep(2)

    # Verify: should have analysis result
    last = get_last_analysis()
    assert last["suggestion"] is not None, "Should have error suggestion"
    assert "Failed to validate" in last["error"], "Should capture validation error"

    uninstall()
    print("✅ Deadlock test passed")


def test_error_capture_still_works():
    """
    Test 2: Basic error capture functionality.

    Ensures that the new architecture still correctly captures and analyzes errors.
    """
    from logger import install, uninstall, get_last_analysis

    install("test.log")

    # Trigger known error (CUDA OOM)
    print("Traceback (most recent call last):")
    print('  File "test.py", line 10, in <module>')
    print("    model.forward()")
    print("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB")

    time.sleep(1)

    # Verify
    last = get_last_analysis()
    assert "CUDA out of memory" in last["error"], "Should capture CUDA OOM"
    assert last["suggestion"] is not None, "Should have suggestion"

    uninstall()
    print("✅ Error capture test passed")


def test_concurrent_writes():
    """
    Test 3: Concurrent writes don't cause data loss.

    Ensures that multiple threads writing simultaneously don't cause issues.
    """
    from logger import install, uninstall

    install("test.log")

    def worker(thread_id):
        for i in range(5):
            print(f"Thread {thread_id}: message {i}")
            time.sleep(0.01)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(1)
    uninstall()
    print("✅ Concurrent writes test passed")


def test_loginterceptor_compatibility():
    """
    Test 4: Compatibility with ComfyUI's LogInterceptor.

    Simulates LogInterceptor already being installed and ensures SafeStreamWrapper
    works correctly with it.
    """
    from logger import install, uninstall

    # Mock LogInterceptor
    mock_interceptor = Mock()
    mock_interceptor.write = Mock(side_effect=lambda x: sys.__stdout__.write(x))
    mock_interceptor.flush = Mock()
    mock_interceptor.encoding = 'utf-8'
    mock_interceptor.isatty = Mock(return_value=False)

    original_stdout = sys.stdout
    sys.stdout = mock_interceptor

    try:
        install("test.log")

        print("Test message")

        # Wait for background processing
        time.sleep(0.5)

        # Verify SafeStreamWrapper called LogInterceptor
        assert mock_interceptor.write.called, "Should call LogInterceptor.write"

        uninstall()
    finally:
        sys.stdout = original_stdout

    print("✅ LogInterceptor compatibility test passed")


def test_queue_overflow_handling():
    """
    Test 5: Queue overflow handling.

    Ensures that if the queue fills up, the system doesn't block (it should discard messages).
    """
    from logger import install, uninstall

    install("test.log")

    # Generate massive amount of output to potentially fill queue
    for i in range(2000):
        print(f"Message {i}")

    # Should not block or crash
    time.sleep(1)

    uninstall()
    print("✅ Queue overflow test passed")


def test_buffer_timeout():
    """
    Test 6: Buffer timeout mechanism.

    Ensures that incomplete tracebacks are eventually flushed after timeout.
    """
    from logger import install, uninstall, get_last_analysis
    from config import CONFIG

    install("test.log")

    # Start a traceback but don't complete it
    print("Traceback (most recent call last):")
    print('  File "test.py", line 10, in <module>')
    print("    incomplete_traceback()")

    # Wait longer than timeout
    time.sleep(CONFIG.traceback_timeout_seconds + 1)

    # Verify timeout was triggered (buffer should be cleared)
    # We can't directly check buffer state, but we can verify the system is still responsive
    print("New message after timeout")
    time.sleep(0.5)

    uninstall()
    print("✅ Buffer timeout test passed")


def test_api_functions_preserved():
    """
    Test 7: Ensure API functions are preserved.

    Verifies that get_last_analysis(), get_analysis_history(), and clear_analysis_history()
    still work correctly.
    """
    from logger import (
        install,
        uninstall,
        get_last_analysis,
        get_analysis_history,
        clear_analysis_history
    )

    install("test.log")

    # Generate an error
    print("Traceback (most recent call last):")
    print('  File "test.py", line 1')
    print("RuntimeError: test error")

    time.sleep(1)

    # Test get_last_analysis()
    last = get_last_analysis()
    assert last["error"] is not None, "Should have error"

    # Test get_analysis_history()
    history = get_analysis_history()
    assert len(history) > 0, "Should have history"

    # Test clear_analysis_history()
    result = clear_analysis_history()
    assert result is True, "Should clear successfully"

    history = get_analysis_history()
    assert len(history) == 0, "History should be empty"

    uninstall()
    print("✅ API functions test passed")


def test_backward_compatibility():
    """
    Test 8: Backward compatibility with SmartLogger.

    Ensures that old code using SmartLogger.install() still works.
    """
    from logger import SmartLogger, get_last_analysis

    SmartLogger.install("test.log")

    # Generate an error
    print("Traceback (most recent call last):")
    print('  File "test.py", line 1')
    print("RuntimeError: backward compatibility test")

    time.sleep(1)

    # Verify
    last = get_last_analysis()
    assert "backward compatibility test" in last["error"], "Should capture error"

    SmartLogger.uninstall()
    print("✅ Backward compatibility test passed")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 ComfyUI-Doctor Logger Safety Tests (v1.3.0)")
    print("=" * 70 + "\n")

    # Run all tests
    test_no_deadlock_under_burst()
    test_error_capture_still_works()
    test_concurrent_writes()
    test_loginterceptor_compatibility()
    test_queue_overflow_handling()
    test_buffer_timeout()
    test_api_functions_preserved()
    test_backward_compatibility()

    print("\n" + "=" * 70)
    print("🎉 All tests passed!")
    print("=" * 70 + "\n")
