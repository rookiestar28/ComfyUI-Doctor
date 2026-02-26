"""
F18 signature pack loader/validator for data-driven diagnostics heuristics.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("comfyui-doctor.diagnostics.signature_packs")

SIGNATURE_PACKS_DIR = Path(__file__).resolve().parent / "packs"
SIGNATURE_PACK_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

SUPPORTED_SCHEMA_VERSION = "1.0"
SUPPORTED_SCOPES = {"node_widget", "doctor_metadata"}
SUPPORTED_CATEGORIES = {"workflow", "env", "deps", "model", "runtime", "privacy", "security", "performance"}
SUPPORTED_SEVERITIES = {"info", "warning", "critical"}

_cache_lock = threading.Lock()
_cache_key: Optional[tuple] = None
_cache_value: List[Dict[str, Any]] = []


class SignaturePackValidationError(ValueError):
    pass


def _env_truthy(name: str, default: str = "1") -> bool:
    raw = os.getenv(name, default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def is_signature_packs_enabled() -> bool:
    return _env_truthy("DOCTOR_DIAGNOSTICS_SIGNATURE_PACKS_ENABLED", "1")


def _pack_allowlist() -> Optional[set[str]]:
    raw = os.getenv("DOCTOR_DIAGNOSTICS_SIGNATURE_PACK_IDS", "").strip()
    if not raw:
        return None
    items = {part.strip() for part in raw.split(",") if part.strip()}
    return items or None


def _validate_identifier(name: str, value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        raise SignaturePackValidationError(f"Missing {name}")
    if len(s) > 128:
        raise SignaturePackValidationError(f"{name} too long")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", s):
        raise SignaturePackValidationError(f"Invalid {name}: {s}")
    return s


def _validate_text(name: str, value: Any, *, max_len: int = 300) -> str:
    s = str(value or "").strip()
    if not s:
        raise SignaturePackValidationError(f"Missing {name}")
    if len(s) > max_len:
        raise SignaturePackValidationError(f"{name} too long")
    return s


def _validate_string_list(name: str, values: Any, *, max_items: int = 20, max_len: int = 120) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise SignaturePackValidationError(f"{name} must be a list")
    out: List[str] = []
    for item in values[:max_items]:
        s = str(item or "").strip()
        if not s:
            continue
        out.append(s[:max_len])
    return out


def _compile_regex_list(name: str, patterns: List[str], *, max_items: int = 10) -> List[re.Pattern[str]]:
    compiled: List[re.Pattern[str]] = []
    for raw in patterns[:max_items]:
        try:
            compiled.append(re.compile(raw))
        except re.error as exc:
            raise SignaturePackValidationError(f"{name} invalid regex '{raw}': {exc}") from exc
    return compiled


def validate_signature_pack_dict(data: Dict[str, Any], source: str = "<memory>") -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise SignaturePackValidationError(f"{source}: pack must be an object")

    schema_version = str(data.get("schema_version") or "").strip()
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise SignaturePackValidationError(f"{source}: unsupported schema_version '{schema_version}'")

    pack_id = _validate_identifier("pack_id", data.get("pack_id"))
    pack_version = _validate_text("pack_version", data.get("pack_version"), max_len=32)
    enabled = bool(data.get("enabled", True))
    provenance_tags = _validate_string_list("provenance_tags", data.get("provenance_tags"), max_items=10, max_len=40)
    rules_raw = data.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise SignaturePackValidationError(f"{source}: rules must be a non-empty list")

    rules: List[Dict[str, Any]] = []
    seen_rule_ids: set[str] = set()

    for idx, rule in enumerate(rules_raw):
        if not isinstance(rule, dict):
            raise SignaturePackValidationError(f"{source}: rule[{idx}] must be an object")
        rule_id = _validate_identifier("rule_id", rule.get("rule_id"))
        if rule_id in seen_rule_ids:
            raise SignaturePackValidationError(f"{source}: duplicate rule_id '{rule_id}'")
        seen_rule_ids.add(rule_id)

        scope = str(rule.get("scope") or "").strip()
        if scope not in SUPPORTED_SCOPES:
            raise SignaturePackValidationError(f"{source}: rule '{rule_id}' invalid scope '{scope}'")

        category = str(rule.get("category") or "").strip()
        if category not in SUPPORTED_CATEGORIES:
            raise SignaturePackValidationError(f"{source}: rule '{rule_id}' invalid category '{category}'")

        severity = str(rule.get("severity") or "").strip()
        if severity not in SUPPORTED_SEVERITIES:
            raise SignaturePackValidationError(f"{source}: rule '{rule_id}' invalid severity '{severity}'")

        confidence = float(rule.get("confidence", 0.5))
        if not (0.0 <= confidence <= 1.0):
            raise SignaturePackValidationError(f"{source}: rule '{rule_id}' confidence must be 0..1")

        match = rule.get("match")
        if not isinstance(match, dict):
            raise SignaturePackValidationError(f"{source}: rule '{rule_id}' match must be an object")

        normalized_rule = {
            "rule_id": rule_id,
            "enabled": bool(rule.get("enabled", True)),
            "family": _validate_text("family", rule.get("family"), max_len=64),
            "scope": scope,
            "category": category,
            "severity": severity,
            "confidence": round(confidence, 3),
            "provenance_tags": _validate_string_list("provenance_tags", rule.get("provenance_tags"), max_items=10, max_len=40),
            "title": _validate_text("title", rule.get("title"), max_len=120),
            "summary": _validate_text("summary", rule.get("summary"), max_len=240),
            "recommendation": _validate_string_list("recommendation", rule.get("recommendation"), max_items=6, max_len=220),
            "max_matches": max(1, min(int(rule.get("max_matches", 3)), 10)),
            "match": {},
        }

        if scope == "node_widget":
            node_types_any = _validate_string_list("match.node_types_any", match.get("node_types_any"), max_items=30, max_len=80)
            widget_contains_any = _validate_string_list("match.widget_contains_any", match.get("widget_contains_any"), max_items=20, max_len=80)
            widget_regex_any = _validate_string_list("match.widget_regex_any", match.get("widget_regex_any"), max_items=10, max_len=140)
            widget_numeric = match.get("widget_numeric", [])
            if widget_numeric is None:
                widget_numeric = []
            if not isinstance(widget_numeric, list):
                raise SignaturePackValidationError(f"{source}: rule '{rule_id}' widget_numeric must be a list")
            numeric_rules: List[Dict[str, Any]] = []
            for n_idx, n_rule in enumerate(widget_numeric[:10]):
                if not isinstance(n_rule, dict):
                    raise SignaturePackValidationError(f"{source}: rule '{rule_id}' widget_numeric[{n_idx}] must be an object")
                entry = {
                    "index": int(n_rule.get("index", 0)),
                    "gt": n_rule.get("gt"),
                    "lt": n_rule.get("lt"),
                    "name": str(n_rule.get("name") or f"widget_{n_idx}")[:40],
                }
                if entry["index"] < 0 or entry["index"] > 128:
                    raise SignaturePackValidationError(f"{source}: rule '{rule_id}' widget_numeric[{n_idx}] index out of range")
                if entry["gt"] is None and entry["lt"] is None:
                    raise SignaturePackValidationError(f"{source}: rule '{rule_id}' widget_numeric[{n_idx}] needs gt and/or lt")
                if entry["gt"] is not None:
                    entry["gt"] = float(entry["gt"])
                if entry["lt"] is not None:
                    entry["lt"] = float(entry["lt"])
                numeric_rules.append(entry)

            if not (node_types_any or widget_contains_any or widget_regex_any or numeric_rules):
                raise SignaturePackValidationError(f"{source}: rule '{rule_id}' has no node_widget match conditions")

            normalized_rule["match"] = {
                "node_types_any": node_types_any,
                "widget_contains_any": [s.lower() for s in widget_contains_any],
                "widget_regex_any": widget_regex_any,
                "_compiled_widget_regex_any": _compile_regex_list("widget_regex_any", widget_regex_any),
                "widget_numeric": numeric_rules,
            }
        elif scope == "doctor_metadata":
            base_url_contains_any = _validate_string_list("match.base_url_contains_any", match.get("base_url_contains_any"), max_items=10, max_len=80)
            llm_model_regex_any = _validate_string_list("match.llm_model_regex_any", match.get("llm_model_regex_any"), max_items=10, max_len=100)
            privacy_mode_equals = _validate_string_list("match.privacy_mode_equals", match.get("privacy_mode_equals"), max_items=5, max_len=20)
            if not (base_url_contains_any or llm_model_regex_any or privacy_mode_equals):
                raise SignaturePackValidationError(f"{source}: rule '{rule_id}' has no doctor_metadata match conditions")
            normalized_rule["match"] = {
                "base_url_contains_any": [s.lower() for s in base_url_contains_any],
                "llm_model_regex_any": llm_model_regex_any,
                "_compiled_llm_model_regex_any": _compile_regex_list("llm_model_regex_any", llm_model_regex_any),
                "privacy_mode_equals": [s.lower() for s in privacy_mode_equals],
            }

        rules.append(normalized_rule)

    return {
        "schema_version": schema_version,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "enabled": enabled,
        "description": str(data.get("description") or "")[:300],
        "provenance_tags": provenance_tags,
        "rules": rules,
        "_source": source,
    }


def _compute_cache_key(pack_files: List[Path]) -> tuple:
    allowlist = tuple(sorted(_pack_allowlist() or []))
    mtimes = []
    for fp in sorted(pack_files):
        try:
            stat = fp.stat()
            mtimes.append((str(fp), stat.st_mtime_ns, stat.st_size))
        except OSError:
            mtimes.append((str(fp), None, None))
    return (is_signature_packs_enabled(), allowlist, tuple(mtimes))


def load_signature_packs(force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    Load and validate enabled signature packs from disk.
    Invalid packs are skipped with warnings (fail-closed for each pack).
    """
    global _cache_key, _cache_value

    if not is_signature_packs_enabled():
        return []

    pack_files = list(SIGNATURE_PACKS_DIR.glob("*.json")) if SIGNATURE_PACKS_DIR.exists() else []
    key = _compute_cache_key(pack_files)
    with _cache_lock:
        if not force_reload and _cache_key == key:
            return list(_cache_value)

        allowlist = _pack_allowlist()
        loaded: List[Dict[str, Any]] = []
        for fp in sorted(pack_files):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                pack = validate_signature_pack_dict(raw, source=str(fp.name))
                if not pack.get("enabled", True):
                    continue
                if allowlist and pack["pack_id"] not in allowlist:
                    continue
                loaded.append(pack)
            except Exception as exc:
                logger.warning(f"F18 signature pack skipped ({fp.name}): {exc}")
                continue

        _cache_key = key
        _cache_value = list(loaded)
        return loaded
