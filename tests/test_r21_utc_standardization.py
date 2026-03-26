from datetime import datetime, timedelta, timezone

from history_store import HistoryEntry, HistoryStore
from services.diagnostics.store import DiagnosticsStore
from services.time_utils import parse_utc_timestamp, utc_isoformat, utc_now
from statistics import StatisticsCalculator
from telemetry import SCHEMA_VERSION, TelemetryEvent, TelemetryStore, validate_event


def test_time_utils_parse_legacy_and_z_timestamps():
    naive = parse_utc_timestamp("2026-03-26T12:00:00")
    aware = parse_utc_timestamp("2026-03-26T12:00:00Z")

    assert naive is not None
    assert aware is not None
    assert naive.tzinfo == timezone.utc
    assert aware.tzinfo == timezone.utc
    assert naive == aware
    assert utc_isoformat(datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)) == "2026-03-26T12:00:00Z"


def test_history_store_aggregates_mixed_legacy_and_aware_timestamps(tmp_path):
    store = HistoryStore(str(tmp_path / "history.json"), maxlen=10)

    store.append(HistoryEntry(timestamp="2026-03-26T12:00:00", error="same", suggestion={}))
    store.append(HistoryEntry(timestamp="2026-03-26T12:00:30Z", error="same", suggestion={}))

    history = store.get_all()
    assert len(history) == 1
    assert history[0]["repeat_count"] == 2
    assert history[0]["first_seen"] == "2026-03-26T12:00:00"
    assert history[0]["last_seen"] == "2026-03-26T12:00:30Z"


def test_validate_event_uses_utc_z_timestamp():
    success, message, event = validate_event({"category": "session", "action": "start"})

    assert success is True
    assert message == ""
    assert event is not None
    assert event.timestamp.endswith("Z")
    assert parse_utc_timestamp(event.timestamp) is not None


def test_telemetry_ttl_handles_mixed_timestamp_formats(tmp_path):
    store = TelemetryStore(filepath=str(tmp_path / "telemetry.json"), enabled=False)
    old_naive = (utc_now() - timedelta(days=8)).replace(tzinfo=None).isoformat()
    recent_aware = utc_isoformat(utc_now() - timedelta(hours=12))
    store._buffer = [
        TelemetryEvent(SCHEMA_VERSION, "old", old_naive, "session", "start"),
        TelemetryEvent(SCHEMA_VERSION, "new", recent_aware, "session", "start"),
    ]

    store._purge_old_events()

    assert [event.event_id for event in store._buffer] == ["new"]


def test_diagnostics_store_retention_handles_mixed_timestamp_formats(tmp_path):
    store = DiagnosticsStore(storage_dir=str(tmp_path), max_reports=10, retention_days=30)
    old_naive = (utc_now() - timedelta(days=45)).replace(tzinfo=None).isoformat()
    recent_aware = utc_isoformat(utc_now() - timedelta(days=1))
    newer_aware = utc_isoformat(utc_now())

    store._reports = {
        "old": {"report_id": "old", "timestamp": old_naive, "scope": "manual"},
        "recent": {"report_id": "recent", "timestamp": recent_aware, "scope": "manual"},
        "newer": {"report_id": "newer", "timestamp": newer_aware, "scope": "manual"},
    }
    store._apply_retention()

    assert set(store._reports.keys()) == {"recent", "newer"}
    history = store.get_history(limit=10)
    assert [item["report_id"] for item in history[:2]] == ["newer", "recent"]


def test_statistics_calculator_handles_mixed_timestamp_formats():
    now = utc_now()
    history = [
        {
            "timestamp": (now - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
            "last_seen": (now - timedelta(minutes=30)).replace(tzinfo=None).isoformat(),
            "matched_pattern_id": "alpha",
            "pattern_category": "memory",
            "repeat_count": 2,
            "resolution_status": "unresolved",
        },
        {
            "timestamp": utc_isoformat(now - timedelta(days=8)),
            "last_seen": utc_isoformat(now - timedelta(days=8)),
            "matched_pattern_id": "beta",
            "pattern_category": "runtime",
            "repeat_count": 1,
            "resolution_status": "resolved",
        },
    ]

    stats = StatisticsCalculator.calculate(history, time_range_days=30)

    assert stats["total_errors"] == 3
    assert stats["trend"]["last_24h"] == 2
    assert stats["trend"]["last_7d"] == 2
    assert stats["trend"]["last_30d"] == 3
