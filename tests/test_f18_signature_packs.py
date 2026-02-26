"""
F18: Data-driven signature packs for diagnostics heuristics.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from services.diagnostics.models import DiagnosticsScope, HealthCheckRequest
from services.diagnostics.checks.signature_packs import (
    MAX_ISSUES_PER_RUN,
    check_signature_packs,
)
from services.diagnostics.signatures.loader import (
    SIGNATURE_PACKS_DIR,
    SIGNATURE_PACK_SCHEMA_PATH,
    SignaturePackValidationError,
    load_signature_packs,
    validate_signature_pack_dict,
)


def test_f18_schema_and_builtin_pack_files_exist():
    assert SIGNATURE_PACK_SCHEMA_PATH.exists(), f"Missing schema file: {SIGNATURE_PACK_SCHEMA_PATH}"
    assert SIGNATURE_PACKS_DIR.exists(), f"Missing packs dir: {SIGNATURE_PACKS_DIR}"
    builtin = SIGNATURE_PACKS_DIR / "builtin.comfyui_heuristics.json"
    assert builtin.exists(), f"Missing builtin F18 pack: {builtin}"


def test_validate_builtin_pack_and_regex_compile():
    builtin = SIGNATURE_PACKS_DIR / "builtin.comfyui_heuristics.json"
    data = json.loads(builtin.read_text(encoding="utf-8"))
    validated = validate_signature_pack_dict(data, source=builtin.name)
    assert validated["schema_version"] == "1.0"
    assert validated["pack_id"] == "builtin.comfyui_heuristics"
    assert len(validated["rules"]) >= 4
    # Ensure compiled regex caches exist for regex-based rules
    regex_rules = [r for r in validated["rules"] if r["match"].get("_compiled_widget_regex_any") or r["match"].get("_compiled_llm_model_regex_any")]
    assert regex_rules


def test_validate_signature_pack_rejects_invalid_confidence():
    with pytest.raises(SignaturePackValidationError):
        validate_signature_pack_dict(
            {
                "schema_version": "1.0",
                "pack_id": "test.invalid_confidence",
                "pack_version": "1",
                "enabled": True,
                "rules": [
                    {
                        "rule_id": "r1",
                        "family": "x",
                        "scope": "node_widget",
                        "category": "workflow",
                        "severity": "info",
                        "confidence": 1.5,
                        "title": "x",
                        "summary": "x",
                        "match": {"widget_contains_any": ["todo"]},
                    }
                ],
            },
            source="invalid.json",
        )


def _run_check(workflow):
    req = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
    return asyncio.run(check_signature_packs(workflow, req))


def test_signature_pack_check_matches_comfyui_heuristic_families(monkeypatch):
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", raising=False)
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACK_IDS", raising=False)

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "title": "Checkpoint Loader",
                "widgets_values": ["path/to/model.safetensors"],
            },
            {
                "id": 2,
                "type": "ControlNetLoader",
                "title": "ControlNet Loader",
                "widgets_values": ["model not found - select model"],
            },
            {
                "id": 3,
                "type": "KSampler",
                "title": "KSampler",
                "widgets_values": [12345, "fixed", 20, 8.0, "euler", "normal", 1.5],
            },
        ],
        "extra": {
            "doctor_metadata": {
                "base_url": "http://127.0.0.1:11434",
                "llm_model": "gpt-4o",
                "privacy_mode": "basic",
            }
        },
    }

    issues = _run_check(workflow)
    assert len(issues) >= 4

    titles = [i.title for i in issues]
    assert any("Placeholder" in t for t in titles)
    assert any("Missing Asset" in t or "Unconfigured Loader" in t for t in titles)
    assert any("Denoise" in t for t in titles)
    assert any("Endpoint / Model Naming Mismatch" in t for t in titles)

    # F18 requirement: confidence + provenance tags in diagnostics output metadata
    issue_dict = issues[0].to_dict()
    assert "metadata" in issue_dict
    sig = issue_dict["metadata"]["signature_pack"]
    assert "confidence" in sig
    assert isinstance(sig["confidence"], float)
    assert "provenance_tags" in sig and sig["provenance_tags"]


def test_signature_pack_check_respects_global_disable(monkeypatch):
    monkeypatch.setenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", "0")
    issues = _run_check({"nodes": []})
    assert issues == []


def test_signature_pack_check_runtime_cap(monkeypatch):
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", raising=False)
    nodes = []
    for i in range(MAX_ISSUES_PER_RUN + 20):
        nodes.append(
            {
                "id": i + 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["path/to/example.safetensors"],
            }
        )
    issues = _run_check({"nodes": nodes})
    assert len(issues) <= MAX_ISSUES_PER_RUN


def test_load_signature_packs_returns_builtin_pack(monkeypatch):
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", raising=False)
    monkeypatch.delenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACK_IDS", raising=False)
    packs = load_signature_packs(force_reload=True)
    pack_ids = {p["pack_id"] for p in packs}
    assert "builtin.comfyui_heuristics" in pack_ids
