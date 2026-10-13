"""Node-health statistics from production-shaped history entries.

History entries are written as ``HistoryEntry(...).to_dict()``: the failing node lives in
``node_context`` and the error is described by ``matched_pattern_id`` / ``pattern_category``.
Node health must count those entries (weighted by ``repeat_count``), still accept the legacy
``node_info`` shape, and never copy raw error text, paths or node ids into the statistics payload.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from history_store import HistoryEntry
from statistics import StatisticsCalculator

RAW_ERROR = r"RuntimeError: CUDA out of memory while loading C:\Users\alice\ComfyUI\models\private.safetensors"
CUSTOM_NODE_PATH = r"C:\Users\alice\ComfyUI\custom_nodes\private-pack"


def _timestamp(minutes_ago: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.isoformat().replace("+00:00", "Z")


def _entry(
    minutes_ago: int,
    node_context: Optional[Dict[str, Any]],
    *,
    pattern: Optional[str] = None,
    category: Optional[str] = None,
    repeat: int = 1,
) -> Dict[str, Any]:
    return HistoryEntry(
        timestamp=_timestamp(minutes_ago),
        error=RAW_ERROR,
        suggestion={"text": "synthetic"},
        node_context=node_context,
        matched_pattern_id=pattern,
        pattern_category=category,
        repeat_count=repeat,
    ).to_dict()


def _node(node_id: str, node_class: Optional[str], node_name: Optional[str] = None) -> Dict[str, Any]:
    return {"node_id": node_id, "node_name": node_name, "node_class": node_class, "custom_node_path": CUSTOM_NODE_PATH}


def test_production_history_entries_produce_weighted_node_health():
    history = [
        _entry(40, _node("10", "KSampler", "KSampler"), pattern="cuda_oom_classic", category="memory", repeat=2),
        _entry(30, _node("11", "VAEDecode", "VAEDecode"), category="memory"),
        _entry(25, _node("12", None, "LoadImage")),
        _entry(20, _node("13", "KSampler", "KSampler"), category="sampling"),
        _entry(15, None, pattern="cuda_oom_classic"),
        _entry(10, {}, pattern="cuda_oom_classic"),
        _entry(5, _node("14", "VAEDecode", "VAEDecode"), pattern="vae_decode_oom", repeat=3),
    ]

    node_health = StatisticsCalculator.calculate(history)["node_health"]

    assert node_health == [
        {"node_class": "VAEDecode", "count": 4, "last_error": "vae_decode_oom"},
        {"node_class": "KSampler", "count": 3, "last_error": "sampling"},
        {"node_class": "LoadImage", "count": 1, "last_error": "unknown"},
    ]


def test_legacy_node_info_entries_still_count():
    history = [
        {"node_info": {"node_class": "KSampler", "node_id": "10"}, "error_type": "RuntimeError", "timestamp": _timestamp(10)},
        {"node_info": {"node_type": "CheckpointLoaderSimple"}, "timestamp": _timestamp(5), "repeat_count": 2},
        {"node_info": {"node_id": "7"}, "timestamp": _timestamp(3)},
    ]

    node_health = StatisticsCalculator.calculate(history)["node_health"]

    assert node_health == [
        {"node_class": "CheckpointLoaderSimple", "count": 2, "last_error": "unknown"},
        {"node_class": "KSampler", "count": 1, "last_error": "unknown"},
    ]


def test_node_health_never_carries_raw_error_text_paths_or_node_ids():
    history = [
        _entry(10, _node("10", "KSampler", "KSampler"), pattern="cuda_oom_classic", category="memory"),
        _entry(5, _node("11", "VAEDecode", "VAEDecode")),
    ]

    node_health = StatisticsCalculator.calculate(history)["node_health"]
    payload = json.dumps(node_health)

    assert [item["node_class"] for item in node_health] == ["KSampler", "VAEDecode"]
    assert [fragment for fragment in (RAW_ERROR, "alice", "private", "RuntimeError", '"10"', '"11"') if fragment in payload] == []
