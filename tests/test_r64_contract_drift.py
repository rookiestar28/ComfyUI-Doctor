"""Contract-drift regressions between producers and consumers.

Each test drives the real producer (diagnostics settings, pattern files, the analysis pipeline,
the pattern loader) instead of mocking the contract under test, so a shape mismatch fails here.
Each test collects its observations into one dict so a failure shows the complete picture.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Union
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pattern_loader  # noqa: E402
import telemetry  # noqa: E402
from services.diagnostics.checks import privacy_security  # noqa: E402
from services.diagnostics.models import DiagnosticsScope, HealthCheckRequest  # noqa: E402

OOM_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "nodes.py", line 1, in sample\n'
    "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB"
)


def _shipped_pattern_ids() -> List[str]:
    ids: List[str] = []
    for directory in ("builtin", "community"):
        for path in sorted((PROJECT_ROOT / "patterns" / directory).glob("*.json")):
            patterns = json.loads(path.read_text(encoding="utf-8")).get("patterns", [])
            ids.extend(item["id"] for item in patterns if item.get("id"))
    return ids


def _privacy_outcome(base_url: str, privacy_mode: str, keys: Dict[str, bool]) -> Union[str, List[str]]:
    workflow = {"extra": {"doctor_metadata": {"privacy_mode": privacy_mode, "base_url": base_url}}}
    request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
    settings = {"api_keys_present": keys, "privacy_mode": privacy_mode}
    with patch.object(privacy_security, "_get_settings_info", return_value=settings):
        try:
            issues = asyncio.run(privacy_security.check_privacy_security(workflow, request))
        except Exception as exc:  # noqa: BLE001 - the exception type is the observation
            return f"raised {type(exc).__name__}"
    return sorted(issue.title for issue in issues)


def test_privacy_check_completes_for_unknown_and_unset_endpoints():
    keys = {"OpenAI": False, "Anthropic": True}
    observed = {
        "unknown_remote_privacy_none": _privacy_outcome("https://llm.example.net/v1", "none", keys),
        "no_base_url": _privacy_outcome("", "basic", keys),
        "known_provider_without_key": _privacy_outcome("https://api.openai.com/v1", "basic", keys),
    }

    assert observed == {
        "unknown_remote_privacy_none": ["Privacy Mode Disabled with Unknown Provider"],
        "no_base_url": [],
        "known_provider_without_key": ["API Key Not Configured for OpenAI"],
    }


def test_telemetry_allowlist_contains_every_loaded_pattern_id():
    shipped = _shipped_pattern_ids()
    telemetry._pattern_cache = None
    try:
        allowlist = telemetry.get_pattern_allowlist()
        observed = {
            "allowlist_equals_shipped_ids": allowlist == set(shipped),
            "allowlist_size": len(allowlist),
            "known_label": telemetry.validate_pattern_label("safetensors_error"),
            "unknown_label": telemetry.validate_pattern_label("not_a_pattern_id"),
        }
    finally:
        telemetry._pattern_cache = None

    assert len(set(shipped)) >= 58
    assert observed == {
        "allowlist_equals_shipped_ids": True,
        "allowlist_size": len(set(shipped)),
        "known_label": "safetensors_error",
        "unknown_label": "__unknown__",
    }


def test_error_summary_carries_the_matched_pattern_category():
    from analyzer import ErrorAnalyzer

    context = ErrorAnalyzer.build_llm_context(OOM_TRACEBACK)
    observed = {
        "matched_pattern_id": context.metadata.get("matched_pattern_id"),
        "category": context.metadata.get("category"),
        "error_summary": context.error_summary,
    }

    assert observed == {
        "matched_pattern_id": "cuda_oom_classic",
        "category": "memory",
        "error_summary": "[memory] torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB",
    }


def test_missing_optional_custom_pattern_directory_does_not_warn(caplog):
    pattern_loader.reset_pattern_loader()
    try:
        with caplog.at_level(logging.DEBUG, logger=pattern_loader.logger.name):
            loader = pattern_loader.get_pattern_loader()
    finally:
        pattern_loader.reset_pattern_loader()

    observed = {
        "custom_directory_exists": (PROJECT_ROOT / "patterns" / "custom").exists(),
        "warnings": [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
        "loaded": len(loader.patterns),
    }
    assert observed == {"custom_directory_exists": False, "warnings": [], "loaded": len(_shipped_pattern_ids())}


def test_missing_required_pattern_directory_still_warns(tmp_path, caplog):
    loader = pattern_loader.PatternLoader([str(tmp_path / "builtin")])
    with caplog.at_level(logging.DEBUG, logger=pattern_loader.logger.name):
        loader.load()

    warnings = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert [message for message in warnings if "Pattern directory not found" in message] == [
        f"[PatternLoader] Pattern directory not found: {tmp_path / 'builtin'}"
    ]
