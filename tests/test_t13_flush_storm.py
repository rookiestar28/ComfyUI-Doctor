from unittest.mock import MagicMock

from logger import SafeStreamWrapper


def test_flush_storm_suppression_recursion_guard():
    """
    T13: failing stream.flush() must not recurse or raise from wrapper.flush().
    """
    mock_stream = MagicMock()
    mock_stream.flush.side_effect = OSError("Disk full")
    message_queue = MagicMock()
    wrapper = SafeStreamWrapper(mock_stream, message_queue)

    # If wrapper.flush() recursively retried/logged through itself, call_count would
    # grow unexpectedly or raise. We expect exactly one underlying flush per call.
    wrapper.flush()
    wrapper.flush()
    wrapper.flush()

    assert mock_stream.flush.call_count == 3
