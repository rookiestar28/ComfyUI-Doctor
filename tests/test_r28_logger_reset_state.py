from unittest.mock import MagicMock


def test_clear_analysis_history_uses_processor_owned_reset(monkeypatch):
    import logger

    class ProcessorWithResetOnly:
        def __init__(self):
            self.reset_called = False

        def reset_traceback_state(self):
            self.reset_called = True

    processor = ProcessorWithResetOnly()
    queue = MagicMock()
    queue.clear.return_value = None
    store = MagicMock()
    store.clear.return_value = None

    monkeypatch.setattr(logger, "_log_processor", processor)
    monkeypatch.setattr(logger, "_message_queue", queue)
    monkeypatch.setattr(logger, "_get_history_store", lambda: store)

    assert logger.clear_analysis_history() is True
    assert processor.reset_called is True
    queue.clear.assert_called_once_with()


def test_doctor_log_processor_reset_traceback_state_clears_buffer_and_flags():
    import logger

    processor = logger.DoctorLogProcessor(logger.DroppingQueue(maxsize=4))
    processor.buffer = ["Traceback (most recent call last):\n"]
    processor._set_traceback_state(True)
    processor.last_buffer_time = 123.45

    processor.reset_traceback_state()

    assert processor.buffer == []
    assert processor.in_traceback is False
    assert processor.last_buffer_time == 0
