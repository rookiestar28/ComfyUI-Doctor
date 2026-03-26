"""
Logger safety tests for SafeStreamWrapper architecture.

Validates:
1) Traceback capture via stdout wrapper
2) Validation error block capture
3) Install/uninstall behavior
"""

import time


def _wait_for(predicate, timeout=2.0):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_error_capture_from_traceback():
    """Traceback lines should produce a captured analysis."""
    from logger import install, uninstall, get_last_analysis, clear_analysis_history

    install("test.log")
    clear_analysis_history()

    print("Traceback (most recent call last):")
    print('  File "test.py", line 1')
    print("RuntimeError: CUDA out of memory")

    _wait_for(lambda: "CUDA out of memory" in (get_last_analysis().get("error") or ""))
    last = get_last_analysis()

    assert "CUDA out of memory" in (last.get("error") or "")
    assert last.get("suggestion") is not None

    uninstall()


def test_validation_error_block_capture():
    """Validation error blocks should be captured when prompt executes."""
    from logger import install, uninstall, get_last_analysis, clear_analysis_history

    install("test.log")
    clear_analysis_history()

    print("Failed to validate prompt for output 1:")
    print("* KSampler 1:")
    print("  - Return type mismatch between linked nodes: scheduler")
    print("Executing prompt: test-123")

    _wait_for(lambda: "Failed to validate" in (get_last_analysis().get("error") or ""))
    last = get_last_analysis()

    assert "Failed to validate" in (last.get("error") or "")

    uninstall()


def test_last_analysis_includes_sanitization_metadata():
    """Sanitization metadata should be present in last analysis."""
    from logger import install, uninstall, get_last_analysis, clear_analysis_history

    install("test.log")
    clear_analysis_history()

    print("Traceback (most recent call last):")
    print('  File "C:\\Users\\alice\\secret.py", line 1')
    print("RuntimeError: CUDA out of memory")

    _wait_for(lambda: "CUDA out of memory" in (get_last_analysis().get("error") or ""))
    last = get_last_analysis()

    analysis_meta = last.get("analysis_metadata") or {}
    sanitization = analysis_meta.get("sanitization") or {}

    assert sanitization.get("pii_found") is True
    assert sanitization.get("sanitized_length") < sanitization.get("original_length")

    uninstall()


def test_last_analysis_timestamp_is_utc_z():
    """R21 follow-up: latest analysis timestamps should use UTC `Z` serialization."""
    from logger import install, uninstall, get_last_analysis, clear_analysis_history
    from services.time_utils import parse_utc_timestamp

    install("test.log")
    clear_analysis_history()

    print("Traceback (most recent call last):")
    print('  File "test.py", line 1')
    print("RuntimeError: CUDA out of memory")

    _wait_for(lambda: "CUDA out of memory" in (get_last_analysis().get("error") or ""))
    last = get_last_analysis()
    timestamp = last.get("timestamp") or ""

    assert timestamp.endswith("Z")
    assert parse_utc_timestamp(timestamp) is not None

    uninstall()


def test_install_uninstall_idempotent():
    """Installing twice should not break, uninstall restores streams."""
    import sys
    from logger import install, uninstall

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    install("test.log")
    install("test.log")

    uninstall()

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr


def test_install_recovers_from_stale_wrapper_state():
    """R22 follow-up: install() should recover if wrappers remain from interrupted teardown."""
    import sys
    import logger as logger_module

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    logger_module.install("test.log")
    stale_stdout = sys.stdout
    stale_stderr = sys.stderr

    # Simulate an interrupted teardown that lost queue state but left wrappers installed.
    logger_module._message_queue = None
    logger_module.clear_analysis_history()

    logger_module.install("test.log")

    assert sys.stdout is not stale_stdout
    assert sys.stderr is not stale_stderr

    print("Traceback (most recent call last):")
    print('  File "test.py", line 1')
    print("RuntimeError: CUDA out of memory")

    _wait_for(
        lambda: "CUDA out of memory" in (logger_module.get_last_analysis().get("error") or "")
    )
    last = logger_module.get_last_analysis()

    assert "CUDA out of memory" in (last.get("error") or "")

    logger_module.uninstall()
    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr


# ==============================================================================
# R22: Asyncio transport GC recursive pollution fix tests
# ==============================================================================


def test_asyncio_gc_warning_not_captured():
    """R22: asyncio transport GC warnings should NOT trigger error analysis."""
    from logger import install, uninstall, get_last_analysis, clear_analysis_history

    install("test.log")
    clear_analysis_history()

    # Simulate the exact asyncio GC warning that causes recursive pollution
    import sys
    print(
        "Traceback (most recent call last):\n"
        '  File "C:\\Users\\Ray\\.conda\\envs\\comfyui\\Lib\\asyncio\\proactor_events.py", line 116, in __del__\n'
        '    _warn(f"unclosed transport {self!r}", ResourceWarning, source=self)\n'
        '  File "C:\\Users\\Ray\\.conda\\envs\\comfyui\\Lib\\asyncio\\proactor_events.py", line 80, in __repr__\n'
        "    info.append(f'fd={self._sock.fileno()}')\n"
        '  File "C:\\Users\\Ray\\.conda\\envs\\comfyui\\Lib\\asyncio\\windows_utils.py", line 102, in fileno\n'
        '    raise ValueError("I/O operation on closed pipe")\n'
        "ValueError: I/O operation on closed pipe",
        file=sys.stderr,
    )

    # Give processor time to process the message
    time.sleep(0.5)

    last = get_last_analysis()
    # The asyncio GC warning should have been filtered out — no analysis recorded
    error_text = last.get("error") or ""
    assert "I/O operation on closed pipe" not in error_text, (
        "asyncio GC warning should be excluded from error analysis"
    )

    uninstall()


def test_asyncio_gc_helper_function():
    """R22: _is_asyncio_gc_noise correctly identifies asyncio GC patterns."""
    from logger import _is_asyncio_gc_noise

    # Positive matches
    assert _is_asyncio_gc_noise("_ProactorBasePipeTransport.__del__") is True
    assert _is_asyncio_gc_noise("ValueError: I/O operation on closed pipe") is True
    assert _is_asyncio_gc_noise("unclosed transport <_ProactorSocketTransport>") is True
    assert _is_asyncio_gc_noise(
        "some prefix _ProactorBasePipeTransport.__del__ some suffix"
    ) is True

    # Negative matches
    assert _is_asyncio_gc_noise("RuntimeError: CUDA out of memory") is False
    assert _is_asyncio_gc_noise("ValueError: invalid literal for int()") is False
    assert _is_asyncio_gc_noise("") is False
    assert _is_asyncio_gc_noise(None) is False


def test_reentrance_guard_prevents_recursive_capture():
    """R22: Thread-local reentrance guard prevents recursive write capture."""
    import sys
    from logger import install, uninstall, _stream_reentrance

    install("test.log")

    # Simulate reentrance condition: set flag before write
    _stream_reentrance.active = True
    try:
        # This write should pass through to original stream but NOT enqueue
        # (the reentrance guard should skip the enqueue step)
        sys.stdout.write("test reentrant write\n")
    finally:
        _stream_reentrance.active = False

    uninstall()
    # If we reach here without deadlock or recursion, the test passes


def test_record_analysis_uses_internal_logger():
    """R22: _record_analysis should use _doctor_internal_logger, not logging.info."""
    import logging
    import sys
    from logger import _doctor_internal_logger, FlushSafeProxy

    # Verify the internal logger exists and is correctly configured
    assert _doctor_internal_logger.name == "doctor._internal"
    assert _doctor_internal_logger.propagate is False
    assert len(_doctor_internal_logger.handlers) >= 1

    # Verify the handler writes through a flush-safe proxy around real stderr
    handler = _doctor_internal_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert isinstance(handler.stream, FlushSafeProxy)
    assert handler.stream._original_stream is sys.__stderr__


def test_internal_logger_stream_is_write_safe():
    """R22 follow-up: internal logger must not invoke logging.handleError on invalid stderr handles."""
    import logging
    from unittest.mock import patch
    from logger import _doctor_internal_logger, FlushSafeProxy

    class BrokenStream:
        def write(self, _data):
            raise OSError(6, "invalid handle")

        def flush(self):
            raise OSError(6, "invalid handle")

    handler = _doctor_internal_logger.handlers[0]
    original_stream = handler.stream
    handler.stream = FlushSafeProxy(BrokenStream())
    record = _doctor_internal_logger.makeRecord(
        _doctor_internal_logger.name,
        logging.DEBUG,
        __file__,
        0,
        "debug message",
        (),
        None,
    )

    try:
        with patch.object(logging.Handler, "handleError", side_effect=AssertionError("handleError should not be called")):
            handler.emit(record)
    finally:
        handler.stream = original_stream
