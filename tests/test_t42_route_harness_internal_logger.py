"""The route harness leaves the process-global ``doctor._internal`` logger as it found it.

``DoctorRouteHarness`` imports the package under a synthetic name, so ``logger.py`` runs a second time and
attaches its stream handler to the process-global ``doctor._internal`` logger whenever that logger has none.
A handler left behind wraps the synthetic module's ``FlushSafeProxy``; the real ``logger`` module imported
later skips its own setup, and ``test_logger_safety`` then compares against a different class object.
The synthetic module also sets the logger's level and ``propagate`` flag on every import.

Each case saves the real logger state first and restores it in ``finally``, so this module cannot pollute
the tests that run after it. Every case starts from a level and a ``propagate`` value that the synthetic
module's own setup would overwrite (``DEBUG`` and ``False``), so the check does not depend on whether the
real ``logger`` module was imported earlier in the process.
"""

from __future__ import annotations

import io
import logging

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness  # noqa: E402

_INTERNAL_LOGGER_NAME = "doctor._internal"


class _RecordingHandler(logging.StreamHandler):
    """A caller-owned handler that notes whether anyone closed it (StreamHandler.close never closes the stream)."""

    close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


def _snapshot(logger: logging.Logger):
    return list(logger.handlers), logger.level, logger.propagate


def _restore(logger: logging.Logger, saved) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handlers, level, propagate = saved
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate


def _prepare(logger: logging.Logger, handlers) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = True


def test_harness_leaves_an_empty_internal_logger_empty():
    logger = logging.getLogger(_INTERNAL_LOGGER_NAME)
    real_state = _snapshot(logger)
    try:
        _prepare(logger, [])
        before = _snapshot(logger)

        with DoctorRouteHarness():
            pass

        after = _snapshot(logger)
        assert after[0] == [], [type(h.stream).__module__ for h in after[0] if hasattr(h, "stream")]
        assert (after[1], after[2]) == (before[1], before[2])
    finally:
        _restore(logger, real_state)


def test_harness_restores_the_handlers_the_logger_already_had():
    logger = logging.getLogger(_INTERNAL_LOGGER_NAME)
    real_state = _snapshot(logger)
    sentinel = _RecordingHandler(io.StringIO())
    try:
        _prepare(logger, [sentinel])
        before = _snapshot(logger)

        with DoctorRouteHarness():
            pass

        after = _snapshot(logger)
        assert len(after[0]) == 1 and after[0][0] is sentinel
        assert (after[1], after[2]) == (before[1], before[2])
        # The sentinel belongs to the caller: the harness must neither close it nor its stream.
        assert sentinel.close_calls == 0
        assert sentinel.stream.closed is False
    finally:
        _restore(logger, real_state)


def test_harness_closes_the_handler_the_synthetic_import_created(monkeypatch):
    logger = logging.getLogger(_INTERNAL_LOGGER_NAME)
    real_state = _snapshot(logger)
    closed = []
    original_close = logging.StreamHandler.close

    def recording_close(self):
        closed.append(self)
        return original_close(self)

    try:
        _prepare(logger, [])
        monkeypatch.setattr(logging.StreamHandler, "close", recording_close)

        with DoctorRouteHarness():
            created = list(logger.handlers)

        # Compare by identity: other loggers the synthetic import configures (the API logger) have handlers
        # that are closed by their own restore, which must not satisfy this check.
        assert created, "the synthetic import is expected to attach a handler to an empty doctor._internal"
        for handler in created:
            assert any(handler is done for done in closed), handler
    finally:
        monkeypatch.undo()
        _restore(logger, real_state)
