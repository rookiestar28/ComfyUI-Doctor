import io
import json
import sys
import threading
import time
import types
from collections import deque
from copy import deepcopy
from pathlib import Path

import pytest

import logger
import services.dynamic_vram_advisory as advisory
from services.diagnostics.checks import env_deps
from services.dynamic_vram_advisory import (
    COMFY_AIMDO_FALLBACK_WARNING,
    DYNAMIC_VRAM_RECOMMENDATION,
    MAX_HOST_LOG_ENTRIES,
    MAX_REASON_CODES,
    MAX_REPEAT_COUNT,
    PYTORCH_FALLBACK_WARNING,
    classify_dynamic_vram_warning,
    clear_dynamic_vram_advisory,
    get_dynamic_vram_advisory,
    record_dynamic_vram_warning,
    replay_host_dynamic_vram_advisory,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_KEYS = {
    "active",
    "kind",
    "severity",
    "fatal",
    "reasons",
    "title",
    "message",
    "recommendation",
    "repeat_count",
    "first_seen",
    "last_seen",
}


@pytest.fixture(autouse=True)
def _clean_advisory_state():
    logger.uninstall()
    clear_dynamic_vram_advisory()
    yield
    logger.uninstall()
    clear_dynamic_vram_advisory()
    logger._TRACEBACK_ACTIVE.clear()


def _host_logger_module(logs_or_factory):
    module = types.ModuleType("app.logger")
    if callable(logs_or_factory):
        module.get_logs = logs_or_factory
    else:
        module.get_logs = lambda: logs_or_factory
    return module


def test_contract_constants_and_inactive_projection_are_exact():
    assert MAX_HOST_LOG_ENTRIES == 300
    assert MAX_REPEAT_COUNT == 65535
    assert MAX_REASON_CODES == 2
    assert get_dynamic_vram_advisory() == {"active": False}


@pytest.mark.parametrize(
    ("message", "reason"),
    (
        (PYTORCH_FALLBACK_WARNING, "pytorch_threshold"),
        (COMFY_AIMDO_FALLBACK_WARNING, "comfy_aimdo_unavailable"),
        (f"[WARNING] {PYTORCH_FALLBACK_WARNING}\n", "pytorch_threshold"),
        (
            f"\x1b[1m\x1b[33m[WARNING]\x1b[0m {COMFY_AIMDO_FALLBACK_WARNING}\n",
            "comfy_aimdo_unavailable",
        ),
    ),
)
def test_exact_source_messages_and_narrow_host_wrapper_are_classified(message, reason):
    assert classify_dynamic_vram_warning(message) == reason


@pytest.mark.parametrize(
    "message",
    (
        "",
        None,
        27,
        PYTORCH_FALLBACK_WARNING.lower(),
        f"[WARNING]{PYTORCH_FALLBACK_WARNING}",
        f"root [WARNING] {PYTORCH_FALLBACK_WARNING}",
        f"[INFO] {PYTORCH_FALLBACK_WARNING}",
        f"{PYTORCH_FALLBACK_WARNING} extra",
        PYTORCH_FALLBACK_WARNING.replace("2.8", "2.9"),
        (
            "Dynamic vram disabled with argument. If you have any issues with "
            "dynamic vram enabled please give us a detailed reports."
        ),
        "PyTorch 2.7 is installed on an NVIDIA GPU",
        "Unrelated VRAM text",
        "private-prefix " + PYTORCH_FALLBACK_WARNING,
    ),
)
def test_near_misses_and_inferred_context_are_rejected(message):
    assert classify_dynamic_vram_warning(message) is None
    assert record_dynamic_vram_warning(message) is False
    assert get_dynamic_vram_advisory() == {"active": False}


def test_both_reasons_share_one_bounded_deterministic_advisory(monkeypatch):
    monkeypatch.setattr(advisory, "MAX_REPEAT_COUNT", 2)

    assert record_dynamic_vram_warning(COMFY_AIMDO_FALLBACK_WARNING) is True
    assert record_dynamic_vram_warning(PYTORCH_FALLBACK_WARNING) is True
    assert record_dynamic_vram_warning(PYTORCH_FALLBACK_WARNING) is True

    result = get_dynamic_vram_advisory()
    assert set(result) == ACTIVE_KEYS
    assert result["active"] is True
    assert result["kind"] == "dynamic_vram_fallback"
    assert result["severity"] == "warning"
    assert result["fatal"] is False
    assert result["reasons"] == ["pytorch_threshold", "comfy_aimdo_unavailable"]
    assert result["recommendation"] == DYNAMIC_VRAM_RECOMMENDATION
    assert result["repeat_count"] == 2
    assert result["first_seen"].endswith("Z")
    assert result["last_seen"].endswith("Z")


def test_getter_returns_an_independent_safe_projection():
    record_dynamic_vram_warning(PYTORCH_FALLBACK_WARNING)
    first = get_dynamic_vram_advisory()
    first["reasons"].append("caller_mutation")
    first["message"] = PYTORCH_FALLBACK_WARNING

    second = get_dynamic_vram_advisory()
    serialized = json.dumps(second, sort_keys=True)
    assert second["reasons"] == ["pytorch_threshold"]
    assert PYTORCH_FALLBACK_WARNING not in serialized
    assert COMFY_AIMDO_FALLBACK_WARNING not in serialized
    for forbidden in ("C:\\", "https://", "--disable-dynamic-vram", "token", "secret"):
        assert forbidden not in serialized


def test_corrupt_internal_snapshot_fails_closed_to_inactive(monkeypatch):
    monkeypatch.setattr(advisory, "_active_state", {"unexpected": "private payload"})
    assert get_dynamic_vram_advisory() == {"active": False}


def test_valid_startup_replay_is_single_call_read_only_and_deduplicated(monkeypatch):
    source = [
        {"t": "2026-08-19T00:00:00", "m": "ordinary startup line\n"},
        {
            "t": "2026-08-19T00:00:01",
            "m": f"\x1b[1m\x1b[33m[WARNING]\x1b[0m {PYTORCH_FALLBACK_WARNING}\n",
        },
    ]
    original = deepcopy(source)
    calls = 0

    def get_logs():
        nonlocal calls
        calls += 1
        return source

    monkeypatch.setitem(sys.modules, "app.logger", _host_logger_module(get_logs))

    assert replay_host_dynamic_vram_advisory() is True
    assert calls == 1
    assert source == original
    assert get_dynamic_vram_advisory()["repeat_count"] == 1

    queue = logger.DroppingQueue(maxsize=4)
    wrapper = logger.SafeStreamWrapper(io.StringIO(), queue)
    wrapper.write(PYTORCH_FALLBACK_WARNING)
    priority, delivered = queue.get()
    assert priority is False
    processor = logger.DoctorLogProcessor(queue)
    processor._process_message(delivered)
    result = get_dynamic_vram_advisory()
    assert result["active"] is True
    assert result["repeat_count"] == 2
    assert len(result["reasons"]) == 1


class _UnexpectedMutableList(list):
    pass


@pytest.mark.parametrize(
    "source",
    (
        (PYTORCH_FALLBACK_WARNING,),
        [{"m": PYTORCH_FALLBACK_WARNING}, {"m": 27}],
        [{"m": PYTORCH_FALLBACK_WARNING}] * (MAX_HOST_LOG_ENTRIES + 1),
        (entry for entry in ({"m": PYTORCH_FALLBACK_WARNING},)),
        _UnexpectedMutableList([{"m": PYTORCH_FALLBACK_WARNING}]),
    ),
)
def test_malformed_oversized_or_unexpected_startup_sources_fail_closed(monkeypatch, source):
    monkeypatch.setitem(sys.modules, "app.logger", _host_logger_module(source))
    assert replay_host_dynamic_vram_advisory() is False
    assert get_dynamic_vram_advisory() == {"active": False}


def test_partial_valid_snapshot_is_rejected_before_any_state_mutation(monkeypatch):
    source = [
        {"m": PYTORCH_FALLBACK_WARNING},
        {"not_m": COMFY_AIMDO_FALLBACK_WARNING},
    ]
    original = deepcopy(source)
    monkeypatch.setitem(sys.modules, "app.logger", _host_logger_module(source))

    assert replay_host_dynamic_vram_advisory() is False
    assert source == original
    assert get_dynamic_vram_advisory() == {"active": False}


def test_absent_noncallable_and_throwing_host_log_boundary_fail_closed(monkeypatch, caplog):
    monkeypatch.delitem(sys.modules, "app.logger", raising=False)
    assert replay_host_dynamic_vram_advisory() is False

    module = types.ModuleType("app.logger")
    module.get_logs = None
    monkeypatch.setitem(sys.modules, "app.logger", module)
    assert replay_host_dynamic_vram_advisory() is False

    def fail():
        raise RuntimeError("private startup payload must not escape")

    monkeypatch.setitem(sys.modules, "app.logger", _host_logger_module(fail))
    assert replay_host_dynamic_vram_advisory() is False
    assert get_dynamic_vram_advisory() == {"active": False}
    assert "private startup payload" not in caplog.text


def test_advisory_capture_and_clear_do_not_touch_runtime_error_or_traceback(monkeypatch):
    sentinel_last = {
        "error": "RuntimeError: sentinel",
        "suggestion": "sentinel suggestion",
        "timestamp": "2026-08-19T00:00:00Z",
        "node_context": {"node_id": "7"},
        "analysis_metadata": {"pipeline_status": "ok"},
        "matched_pattern_id": "sentinel",
        "pattern_category": "execution",
        "pattern_priority": 90,
        "resolution_status": "resolved",
    }
    sentinel_history = deque([dict(sentinel_last)])
    monkeypatch.setattr(logger, "_last_analysis", sentinel_last)
    monkeypatch.setattr(logger, "_analysis_history", sentinel_history)
    monkeypatch.setattr(logger.ErrorAnalyzer, "analyze", lambda *_args, **_kwargs: pytest.fail("analyzer called"))

    processor = logger.DoctorLogProcessor(logger.DroppingQueue(maxsize=4))
    processor.buffer = ["Traceback (most recent call last):\n"]
    processor._set_traceback_state(True)
    processor.last_buffer_time = time.time()
    monkeypatch.setattr(logger.CONFIG, "traceback_timeout_seconds", 60)

    processor._process_message(PYTORCH_FALLBACK_WARNING)
    assert get_dynamic_vram_advisory()["active"] is True
    assert logger.get_last_analysis() == sentinel_last
    assert logger.get_analysis_history() == list(reversed(sentinel_history))
    assert processor.buffer == ["Traceback (most recent call last):\n"]
    assert processor.in_traceback is True
    assert sentinel_last["resolution_status"] == "resolved"

    clear_dynamic_vram_advisory()
    assert get_dynamic_vram_advisory() == {"active": False}
    assert logger.get_last_analysis() == sentinel_last
    assert logger.get_analysis_history() == list(reversed(sentinel_history))
    assert processor.buffer == ["Traceback (most recent call last):\n"]


def test_dynamic_vram_warning_remains_non_priority_and_cannot_evict_priority_traffic():
    queue = logger.DroppingQueue(maxsize=2)
    traceback = "Traceback (most recent call last):\n"
    validation = "Failed to validate prompt for output 1:\n"
    assert logger._is_priority_message(PYTORCH_FALLBACK_WARNING) is False
    assert queue.put_nowait(traceback, priority=logger._is_priority_message(traceback)) is True
    assert queue.put_nowait(validation, priority=logger._is_priority_message(validation)) is True

    wrapper = logger.SafeStreamWrapper(io.StringIO(), queue)
    wrapper.write(PYTORCH_FALLBACK_WARNING)

    assert queue.qsize() == 2
    stats = queue.get_stats()
    assert stats["queue_dropped_non_priority"] == 1
    assert queue.get()[1] == traceback
    assert queue.get()[1] == validation
    assert get_dynamic_vram_advisory() == {"active": False}


def test_install_reinstall_and_uninstall_replay_once_and_leave_no_processor(monkeypatch):
    source = deque([{"m": PYTORCH_FALLBACK_WARNING}], maxlen=MAX_HOST_LOG_ENTRIES)
    monkeypatch.setitem(sys.modules, "app.logger", _host_logger_module(source))

    logger.install("test.log")
    first_processor = logger._log_processor
    assert get_dynamic_vram_advisory()["repeat_count"] == 1
    assert first_processor is not None and first_processor.is_alive()

    logger.install("test.log")
    second_processor = logger._log_processor
    assert second_processor is not None and second_processor is not first_processor
    assert first_processor.is_alive() is False
    assert get_dynamic_vram_advisory()["repeat_count"] == 1

    logger.uninstall()
    assert second_processor.is_alive() is False
    assert logger._log_processor is None
    assert logger._message_queue is None
    assert get_dynamic_vram_advisory() == {"active": False}


def test_repeated_health_reads_and_concurrent_record_clear_stay_bounded():
    record_dynamic_vram_warning(PYTORCH_FALLBACK_WARNING)
    baseline = get_dynamic_vram_advisory()
    for _ in range(20):
        assert get_dynamic_vram_advisory() == baseline

    errors = []

    def record_worker():
        try:
            for _ in range(200):
                record_dynamic_vram_warning(COMFY_AIMDO_FALLBACK_WARNING)
        except Exception as exc:  # pragma: no cover - assertion captures unexpected races
            errors.append(exc)

    def clear_worker():
        try:
            for _ in range(50):
                clear_dynamic_vram_advisory()
        except Exception as exc:  # pragma: no cover - assertion captures unexpected races
            errors.append(exc)

    threads = [threading.Thread(target=record_worker) for _ in range(4)]
    threads.extend(threading.Thread(target=clear_worker) for _ in range(2))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert errors == []
    assert all(not thread.is_alive() for thread in threads)
    result = get_dynamic_vram_advisory()
    assert set(result) in ({"active"}, ACTIVE_KEYS)
    if result["active"]:
        assert 1 <= result["repeat_count"] <= MAX_REPEAT_COUNT
        assert len(result["reasons"]) <= MAX_REASON_CODES


def test_health_route_and_package_context_use_only_the_safe_injected_getter():
    api_source = (PROJECT_ROOT / "api_routes.py").read_text(encoding="utf-8")
    init_source = (PROJECT_ROOT / "__init__.py").read_text(encoding="utf-8")

    assert '"dynamic_vram_advisory": get_dynamic_vram_advisory(),' in api_source
    assert "from .services.dynamic_vram_advisory import (" in init_source
    assert "get_dynamic_vram_advisory" in init_source
    assert "clear_dynamic_vram_advisory" in init_source
    assert "app.logger" not in api_source
    assert "dynamic_vram_advisory" not in api_source.split(
        '@server.PromptServer.instance.routes.get("/debugger/last_analysis")', 1
    )[1].split('@server.PromptServer.instance.routes.post("/debugger/set_language")', 1)[0]


def test_base_pytorch_contract_remains_27_and_does_not_create_version_only_advisory():
    assert env_deps.TORCH_MIN_VERSION == (2, 7)
    assert env_deps._check_torch_availability(
        {"torch_available": True, "torch_version": "2.7.0"}
    ) == []
    assert classify_dynamic_vram_warning("PyTorch 2.7.0") is None
    assert get_dynamic_vram_advisory() == {"active": False}
