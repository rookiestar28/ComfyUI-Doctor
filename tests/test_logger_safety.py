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
