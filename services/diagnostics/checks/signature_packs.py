"""
F18 Proactive Diagnostics - Data-Driven Signature Pack Check

Applies validated JSON heuristic signature packs to workflow and doctor metadata.
Diagnostic enrichment only (no verdict claims).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from ..signatures import load_signature_packs, is_signature_packs_enabled
from . import register_check

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.signature_packs")

# F18 runtime caps (bounded deterministic scan)
MAX_NODES_SCAN = 400
MAX_WIDGETS_PER_NODE = 24
MAX_WIDGET_STRING_CHARS = 256
MAX_ISSUES_PER_RUN = 20


def _to_severity(value: str) -> IssueSeverity:
    try:
        return IssueSeverity(value)
    except Exception:
        return IssueSeverity.INFO


def _to_category(value: str) -> IssueCategory:
    try:
        return IssueCategory(value)
    except Exception:
        return IssueCategory.WORKFLOW


def _safe_node_id(node: Dict[str, Any]) -> Optional[int]:
    try:
        node_id = node.get("id")
        if node_id is None:
            return None
        return int(node_id)
    except Exception:
        return None


def _rule_metadata(pack: Dict[str, Any], rule: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = {
        "signature_pack": {
            "pack_id": pack.get("pack_id"),
            "pack_version": pack.get("pack_version"),
            "rule_id": rule.get("rule_id"),
            "family": rule.get("family"),
            "confidence": rule.get("confidence"),
            "provenance_tags": sorted(set((pack.get("provenance_tags") or []) + (rule.get("provenance_tags") or []))),
        }
    }
    if extra:
        meta["signature_pack"].update(extra)
    return meta


def _node_type_match(rule: Dict[str, Any], node_type: str) -> bool:
    node_types = ((rule.get("match") or {}).get("node_types_any") or [])
    if not node_types:
        return True
    return node_type in node_types


def _string_widget_match(rule: Dict[str, Any], widgets: List[Any]) -> Optional[Tuple[str, int]]:
    match_cfg = rule.get("match") or {}
    contains_any = match_cfg.get("widget_contains_any") or []
    regex_any = match_cfg.get("_compiled_widget_regex_any") or []

    if not contains_any and not regex_any:
        return None

    for idx, value in enumerate(widgets[:MAX_WIDGETS_PER_NODE]):
        if not isinstance(value, str):
            continue
        text = value[:MAX_WIDGET_STRING_CHARS]
        lower = text.lower()
        if any(token in lower for token in contains_any):
            return ("widget_contains_any", idx)
        for compiled in regex_any:
            try:
                if compiled.search(text):
                    return ("widget_regex_any", idx)
            except Exception:
                continue
    return None


def _numeric_widget_match(rule: Dict[str, Any], widgets: List[Any]) -> Optional[Tuple[str, int, float]]:
    numeric_rules = ((rule.get("match") or {}).get("widget_numeric") or [])
    if not numeric_rules:
        return None

    for n_rule in numeric_rules:
        idx = int(n_rule.get("index", 0))
        if idx >= len(widgets):
            continue
        value = widgets[idx]
        if not isinstance(value, (int, float)):
            continue
        f_value = float(value)
        gt = n_rule.get("gt")
        lt = n_rule.get("lt")
        if gt is not None and f_value > float(gt):
            return (str(n_rule.get("name") or "numeric"), idx, f_value)
        if lt is not None and f_value < float(lt):
            return (str(n_rule.get("name") or "numeric"), idx, f_value)
    return None


def _doctor_metadata_match(rule: Dict[str, Any], workflow: Dict[str, Any]) -> Optional[List[str]]:
    extra = workflow.get("extra") if isinstance(workflow.get("extra"), dict) else {}
    meta = extra.get("doctor_metadata") if isinstance(extra.get("doctor_metadata"), dict) else {}
    if not meta:
        return None

    match_cfg = rule.get("match") or {}
    reasons: List[str] = []

    base_url = str(meta.get("base_url") or "")
    base_url_lower = base_url.lower()
    base_needles = match_cfg.get("base_url_contains_any") or []
    if base_needles:
        if not any(n in base_url_lower for n in base_needles):
            return None
        reasons.append("base_url")

    model = str(meta.get("llm_model") or "")
    model_regex = match_cfg.get("_compiled_llm_model_regex_any") or []
    if model_regex:
        if not any(r.search(model) for r in model_regex):
            return None
        reasons.append("llm_model")

    privacy_mode = str(meta.get("privacy_mode") or "").lower()
    privacy_equals = match_cfg.get("privacy_mode_equals") or []
    if privacy_equals:
        if privacy_mode not in privacy_equals:
            return None
        reasons.append("privacy_mode")

    return reasons or []


def _build_issue_for_node(pack: Dict[str, Any], rule: Dict[str, Any], node: Dict[str, Any], evidence_hint: str) -> HealthIssue:
    node_type = str(node.get("type") or "Unknown")
    node_id = _safe_node_id(node)
    node_title = str(node.get("title") or node_type)
    target = IssueTarget(node_id=node_id)
    content_hash = f"{pack.get('pack_id')}:{rule.get('rule_id')}:{node_type}:{evidence_hint}"
    issue_id = HealthIssue.generate_issue_id("f18_signature_pack", target, content_hash)

    return HealthIssue(
        issue_id=issue_id,
        category=_to_category(str(rule.get("category") or "workflow")),
        severity=_to_severity(str(rule.get("severity") or "info")),
        title=str(rule.get("title") or "Diagnostics Signature Match"),
        summary=str(rule.get("summary") or "").format(
            node_id=node_id if node_id is not None else "?",
            node_type=node_type,
            node_title=node_title,
        ),
        evidence=[
            f"Signature pack rule matched: {pack.get('pack_id')}::{rule.get('rule_id')}",
            f"Node #{node_id if node_id is not None else '?'} ({node_type})",
            f"Match source: {evidence_hint}",
        ],
        recommendation=list(rule.get("recommendation") or []),
        target=target,
        metadata=_rule_metadata(pack, rule, {"scope": "node_widget", "node_type": node_type}),
    )


def _build_issue_for_metadata(pack: Dict[str, Any], rule: Dict[str, Any], reasons: List[str]) -> HealthIssue:
    target = IssueTarget(path="workflow.extra.doctor_metadata")
    content_hash = f"{pack.get('pack_id')}:{rule.get('rule_id')}:{','.join(sorted(reasons))}"
    issue_id = HealthIssue.generate_issue_id("f18_signature_pack", target, content_hash)
    return HealthIssue(
        issue_id=issue_id,
        category=_to_category(str(rule.get("category") or "env")),
        severity=_to_severity(str(rule.get("severity") or "info")),
        title=str(rule.get("title") or "Diagnostics Signature Match"),
        summary=str(rule.get("summary") or ""),
        evidence=[
            f"Signature pack rule matched: {pack.get('pack_id')}::{rule.get('rule_id')}",
            f"Matched doctor metadata fields: {', '.join(sorted(reasons))}",
        ],
        recommendation=list(rule.get("recommendation") or []),
        target=target,
        metadata=_rule_metadata(pack, rule, {"scope": "doctor_metadata", "matched_fields": sorted(reasons)}),
    )


@register_check("signature_packs")
async def check_signature_packs(workflow: Dict[str, Any], request: HealthCheckRequest) -> List[HealthIssue]:
    """
    Apply F18 data-driven signature packs to workflow/metadata.

    Bounded by deterministic caps to avoid unbounded scan cost on large workflows.
    """
    if not is_signature_packs_enabled():
        return []

    packs = load_signature_packs()
    if not packs:
        return []

    issues: List[HealthIssue] = []
    nodes = workflow.get("nodes", [])
    node_list = nodes if isinstance(nodes, list) else []

    try:
        for pack in packs:
            for rule in pack.get("rules", []):
                if not rule.get("enabled", True):
                    continue
                if len(issues) >= MAX_ISSUES_PER_RUN:
                    return issues

                max_rule_matches = max(1, min(int(rule.get("max_matches", 3)), 10))
                rule_matches = 0

                if rule.get("scope") == "doctor_metadata":
                    reasons = _doctor_metadata_match(rule, workflow)
                    if reasons:
                        issues.append(_build_issue_for_metadata(pack, rule, reasons))
                    continue

                if rule.get("scope") != "node_widget":
                    continue

                for node in node_list[:MAX_NODES_SCAN]:
                    if not isinstance(node, dict):
                        continue
                    node_type = str(node.get("type") or "")
                    if not _node_type_match(rule, node_type):
                        continue

                    widgets = node.get("widgets_values")
                    if not isinstance(widgets, list):
                        continue

                    string_match = _string_widget_match(rule, widgets)
                    numeric_match = _numeric_widget_match(rule, widgets)
                    if not string_match and not numeric_match:
                        continue

                    if string_match:
                        evidence_hint = f"{string_match[0]}@widget[{string_match[1]}]"
                    else:
                        evidence_hint = f"{numeric_match[0]}={numeric_match[2]:g}@widget[{numeric_match[1]}]"

                    issues.append(_build_issue_for_node(pack, rule, node, evidence_hint))
                    rule_matches += 1

                    if len(issues) >= MAX_ISSUES_PER_RUN:
                        return issues
                    if rule_matches >= max_rule_matches:
                        break
    except Exception as exc:
        # Fail closed for this check; runner isolates this anyway.
        logger.warning(f"F18 signature pack check failed: {exc}")
        return []

    return issues
