"""
F16: Quick Community Feedback (GitHub PR) service.

Builds sanitized append-only feedback payloads and opens a GitHub PR with JSON files.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

try:
    from ..sanitizer import PIISanitizer, SanitizationLevel
except ImportError as import_error:  # pragma: no cover - tests may import as top-level package
    from import_compat import ensure_absolute_import_fallback_allowed
    ensure_absolute_import_fallback_allowed(import_error)
    from sanitizer import PIISanitizer, SanitizationLevel


SCHEMA_VERSION = "1.0"
DEFAULT_GITHUB_REPO = "rookiestar28/ComfyUI-Doctor"
GITHUB_API_BASE = "https://api.github.com"
ALLOWED_CATEGORIES = {
    "memory",
    "workflow",
    "model_loading",
    "framework",
    "validation",
    "type",
    "execution",
    "generic",
    "data_type",
}


class FeedbackValidationError(ValueError):
    """Raised when a feedback submission payload is invalid."""

    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.field_errors = field_errors or {}


@dataclass
class GitHubFeedbackConfig:
    token: str
    repo: str = DEFAULT_GITHUB_REPO
    base_branch: str = ""
    api_base: str = GITHUB_API_BASE

    @classmethod
    def from_env(cls) -> "GitHubFeedbackConfig":
        return cls(
            token=os.getenv("DOCTOR_GITHUB_TOKEN", "").strip(),
            repo=(os.getenv("DOCTOR_GITHUB_REPO", "").strip() or DEFAULT_GITHUB_REPO),
            base_branch=os.getenv("DOCTOR_GITHUB_BASE_BRANCH", "").strip(),
            api_base=(os.getenv("DOCTOR_GITHUB_API_BASE", "").strip() or GITHUB_API_BASE),
        )

    @property
    def ready(self) -> bool:
        return bool(self.token and self.repo)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _sanitize_string(sanitizer: PIISanitizer, value: Any, max_len: int = 4000) -> str:
    text = "" if value is None else str(value)
    if max_len > 0 and len(text) > max_len:
        text = text[:max_len]
    return sanitizer.sanitize(text).sanitized_text.strip()


def _safe_int(value: Any, default: int = 0, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    try:
        n = int(value)
    except Exception:
        n = default
    if min_value is not None:
        n = max(min_value, n)
    if max_value is not None:
        n = min(max_value, n)
    return n


def _validate_pattern_id(value: str) -> str:
    if not value:
        raise FeedbackValidationError("Missing pattern id", {"pattern_candidate.id": "required"})
    if len(value) > 120:
        raise FeedbackValidationError("Pattern id too long", {"pattern_candidate.id": "max 120 chars"})
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,119}", value):
        raise FeedbackValidationError(
            "Invalid pattern id",
            {"pattern_candidate.id": "use lowercase letters/numbers/._- (min 3 chars)"},
        )
    return value


def _validate_regex(value: str) -> str:
    if not value:
        raise FeedbackValidationError("Missing regex", {"pattern_candidate.regex": "required"})
    if len(value) > 2000:
        raise FeedbackValidationError("Regex too long", {"pattern_candidate.regex": "max 2000 chars"})
    try:
        re.compile(value)
    except re.error as exc:
        raise FeedbackValidationError("Invalid regex", {"pattern_candidate.regex": str(exc)}) from exc
    return value


def _normalize_category(value: str) -> str:
    category = (value or "").strip().lower().replace(" ", "_")
    if not category:
        return "generic"
    if len(category) > 64:
        category = category[:64]
    return category if category in ALLOWED_CATEGORIES else "generic"


def _pick_error_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx = payload.get("error_context")
    if isinstance(ctx, dict):
        return ctx
    return {}


def _pick_stats_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    stats = payload.get("stats_snapshot")
    if isinstance(stats, dict):
        return stats
    return {}


def _sanitize_error_context(sanitizer: PIISanitizer, ctx: Dict[str, Any]) -> Dict[str, Any]:
    node_ctx = ctx.get("node_context") if isinstance(ctx.get("node_context"), dict) else {}
    workflow = ctx.get("workflow") if isinstance(ctx.get("workflow"), dict) else {}
    workflow_meta = workflow.get("extra") if isinstance(workflow.get("extra"), dict) else {}

    sanitized_node = {
        "node_id": _sanitize_string(sanitizer, node_ctx.get("node_id"), max_len=64) or None,
        "node_name": _sanitize_string(sanitizer, node_ctx.get("node_name") or node_ctx.get("node_class"), max_len=160) or None,
        "node_class": _sanitize_string(sanitizer, node_ctx.get("node_class"), max_len=160) or None,
    }
    # Remove empty values for cleaner payloads
    sanitized_node = {k: v for k, v in sanitized_node.items() if v not in (None, "")}

    return {
        "error": _sanitize_string(sanitizer, ctx.get("error") or ctx.get("last_error"), max_len=8000),
        "error_summary": _sanitize_string(sanitizer, ctx.get("error_summary"), max_len=500),
        "timestamp": _sanitize_string(sanitizer, ctx.get("timestamp"), max_len=64) or None,
        "node_context": sanitized_node or None,
        "workflow_hint": {
            "has_workflow": bool(workflow),
            "nodes_count": _safe_int(workflow_meta.get("nodes_count"), default=0, min_value=0, max_value=100000) if workflow_meta else 0,
        },
    }


def _sanitize_stats_snapshot(stats: Dict[str, Any], include_stats: bool) -> Optional[Dict[str, Any]]:
    if not include_stats:
        return None
    if not stats:
        return {
            "time_range_days": 30,
            "total_errors": 0,
            "resolution_rate": {"resolved": 0, "unresolved": 0, "ignored": 0},
            "top_patterns": [],
        }

    resolution = stats.get("resolution_rate") if isinstance(stats.get("resolution_rate"), dict) else {}
    top_patterns = stats.get("top_patterns") if isinstance(stats.get("top_patterns"), list) else []

    sanitized_top = []
    for item in top_patterns[:5]:
        if not isinstance(item, dict):
            continue
        sanitized_top.append(
            {
                "pattern_id": str(item.get("pattern_id") or "")[:120],
                "count": _safe_int(item.get("count"), default=0, min_value=0, max_value=10**9),
                "category": _normalize_category(str(item.get("category") or "generic")),
            }
        )

    return {
        "time_range_days": _safe_int(stats.get("time_range_days", 30), default=30, min_value=1, max_value=365),
        "total_errors": _safe_int(stats.get("total_errors"), default=0, min_value=0, max_value=10**9),
        "resolution_rate": {
            "resolved": _safe_int(resolution.get("resolved"), default=0, min_value=0, max_value=10**9),
            "unresolved": _safe_int(resolution.get("unresolved"), default=0, min_value=0, max_value=10**9),
            "ignored": _safe_int(resolution.get("ignored"), default=0, min_value=0, max_value=10**9),
        },
        "top_patterns": sanitized_top,
    }


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def _build_submission_id(timestamp: datetime, stable_seed: str) -> str:
    stamp = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{_hash_text(stable_seed)[:10]}"


def _build_feedback_file_paths(timestamp: datetime, submission_id: str, include_stats: bool) -> Dict[str, str]:
    date_path = timestamp.strftime("%Y%m%d")
    paths = {
        "submission": f"feedback/submissions/{date_path}/{submission_id}.json",
    }
    if include_stats:
        paths["stats"] = f"feedback/stats/{date_path}/{submission_id}.json"
    return paths


def build_feedback_preview(payload: Dict[str, Any], github_config: Optional[GitHubFeedbackConfig] = None) -> Dict[str, Any]:
    """Validate and sanitize a proposed feedback submission; returns preview payload."""
    payload = payload or {}
    github_config = github_config or GitHubFeedbackConfig.from_env()

    # Public GitHub PR payloads must be strict-sanitized regardless of UI setting.
    sanitizer = PIISanitizer(SanitizationLevel.STRICT)
    now = _utc_now()

    pattern_raw = payload.get("pattern_candidate") if isinstance(payload.get("pattern_candidate"), dict) else {}
    suggestion_raw = payload.get("suggestion_candidate") if isinstance(payload.get("suggestion_candidate"), dict) else {}
    include_stats = _normalize_bool(payload.get("include_stats"))

    pattern_id = _validate_pattern_id(_sanitize_string(sanitizer, pattern_raw.get("id"), max_len=120))
    regex_text = _sanitize_string(sanitizer, pattern_raw.get("regex"), max_len=2000)
    regex_text = _validate_regex(regex_text)
    category = _normalize_category(_sanitize_string(sanitizer, pattern_raw.get("category"), max_len=64))
    priority = _safe_int(pattern_raw.get("priority"), default=50, min_value=1, max_value=100)
    notes = _sanitize_string(sanitizer, pattern_raw.get("notes"), max_len=600)

    suggestion_message = _sanitize_string(sanitizer, suggestion_raw.get("message"), max_len=2000)
    if not suggestion_message:
        raise FeedbackValidationError("Missing verified suggestion", {"suggestion_candidate.message": "required"})
    suggestion_language = _sanitize_string(sanitizer, suggestion_raw.get("language") or "en", max_len=16) or "en"

    error_ctx = _sanitize_error_context(sanitizer, _pick_error_context(payload))
    if not error_ctx.get("error") and not error_ctx.get("error_summary"):
        raise FeedbackValidationError("Missing error context", {"error_context": "last error context is required"})

    stats_snapshot = _sanitize_stats_snapshot(_pick_stats_snapshot(payload), include_stats=include_stats)

    preview_payload = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "submission_type": "community_feedback",
        "error_signature": _hash_text(error_ctx.get("error_summary") or error_ctx.get("error")),
        "pattern_candidate": {
            "id": pattern_id,
            "regex": regex_text,
            "category": category,
            "priority": priority,
            "notes": notes or None,
        },
        "suggestion_candidate": {
            "language": suggestion_language,
            "message": suggestion_message,
        },
        "context": {
            "error_summary": error_ctx.get("error_summary") or None,
            "sanitized_traceback_preview": (error_ctx.get("error") or "")[:1200] or None,
            "node_context": error_ctx.get("node_context") or None,
            "workflow_hint": error_ctx.get("workflow_hint") or {"has_workflow": False, "nodes_count": 0},
        },
    }
    if stats_snapshot is not None:
        preview_payload["stats_snapshot"] = stats_snapshot

    submission_seed = "|".join(
        [
            preview_payload["pattern_candidate"]["id"],
            preview_payload["pattern_candidate"]["regex"],
            preview_payload["suggestion_candidate"]["message"],
            preview_payload["error_signature"],
        ]
    )
    submission_id = _build_submission_id(now, submission_seed)
    files = _build_feedback_file_paths(now, submission_id, include_stats=stats_snapshot is not None)

    warnings: List[str] = []
    if category == "generic":
        warnings.append("Pattern category normalized to 'generic'.")
    if not github_config.ready:
        warnings.append("DOCTOR_GITHUB_TOKEN not configured; submit endpoint will fail until configured.")

    return {
        "submission_id": submission_id,
        "files": files,
        "include_stats": stats_snapshot is not None,
        "preview": preview_payload,
        "warnings": warnings,
        "github": {
            "ready": github_config.ready,
            "repo": github_config.repo,
            "base_branch": github_config.base_branch or None,
        },
    }


class GitHubPRClient:
    """Minimal GitHub API client for creating feedback PRs."""

    def __init__(self, config: GitHubFeedbackConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "GitHubPRClient":
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "ComfyUI-Doctor-F16",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request_json(self, method: str, path: str, *, expected: Tuple[int, ...] = (200,), body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._session:
            raise RuntimeError("GitHubPRClient session not started")
        url = f"{self.config.api_base.rstrip('/')}{path}"
        async with self._session.request(method, url, json=body) as resp:
            data = await resp.json(content_type=None)
            if resp.status not in expected:
                message = ""
                if isinstance(data, dict):
                    message = str(data.get("message") or data.get("error") or "")
                raise RuntimeError(f"GitHub API {method} {path} failed ({resp.status}): {message or data}")
            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected GitHub API response type for {method} {path}")
            return data

    async def _get_default_branch(self) -> str:
        if self.config.base_branch:
            return self.config.base_branch
        info = await self._request_json("GET", f"/repos/{self.config.repo}")
        branch = str(info.get("default_branch") or "").strip()
        if not branch:
            raise RuntimeError("GitHub repo default_branch missing")
        return branch

    async def _get_branch_sha(self, branch: str) -> str:
        ref = await self._request_json("GET", f"/repos/{self.config.repo}/git/ref/heads/{branch}")
        sha = (((ref.get("object") or {}).get("sha")) if isinstance(ref, dict) else None) or ""
        if not sha:
            raise RuntimeError(f"Failed to resolve SHA for base branch '{branch}'")
        return sha

    async def _create_branch(self, branch_name: str, base_sha: str) -> None:
        await self._request_json(
            "POST",
            f"/repos/{self.config.repo}/git/refs",
            expected=(201,),
            body={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )

    async def _put_file(self, path: str, content_bytes: bytes, branch_name: str, message: str) -> None:
        await self._request_json(
            "PUT",
            f"/repos/{self.config.repo}/contents/{path}",
            expected=(200, 201),
            body={
                "message": message,
                "branch": branch_name,
                "content": base64.b64encode(content_bytes).decode("ascii"),
            },
        )

    async def _create_pr(self, title: str, body: str, head: str, base: str) -> Dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/repos/{self.config.repo}/pulls",
            expected=(201,),
            body={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
            },
        )

    async def create_feedback_pr(
        self,
        *,
        preview_result: Dict[str, Any],
        stats_payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        base_branch = await self._get_default_branch()
        base_sha = await self._get_branch_sha(base_branch)
        submission_id = preview_result["submission_id"]

        branch_name = f"feedback/{_utc_now().strftime('%Y%m%d')}/{submission_id}"
        # Retry once with a suffix to avoid rare branch name collisions.
        try:
            await self._create_branch(branch_name, base_sha)
        except RuntimeError:
            branch_name = f"{branch_name}-{_hash_text(base_sha)[:6]}"
            await self._create_branch(branch_name, base_sha)

        files = preview_result["files"]
        preview_payload = preview_result["preview"]
        submit_msg = f"F16 feedback submission {submission_id}"

        await self._put_file(
            files["submission"],
            (json.dumps(preview_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            branch_name,
            f"{submit_msg} (submission)",
        )

        if stats_payload is not None and "stats" in files:
            await self._put_file(
                files["stats"],
                (json.dumps(stats_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                branch_name,
                f"{submit_msg} (stats)",
            )

        pat = preview_payload.get("pattern_candidate") or {}
        sug = preview_payload.get("suggestion_candidate") or {}
        pr_title = f"[Doctor Feedback] {pat.get('id', 'community_feedback')} ({submission_id})"
        pr_body = "\n".join(
            [
                "Automated F16 community feedback submission from ComfyUI-Doctor.",
                "",
                f"- Submission ID: `{submission_id}`",
                f"- Pattern ID: `{pat.get('id', '')}`",
                f"- Category: `{pat.get('category', '')}`",
                f"- Includes stats snapshot: `{bool(stats_payload)}`",
                f"- Suggestion language: `{(sug.get('language') or 'en')}`",
                "",
                "Files are append-only under `feedback/` to reduce merge conflicts.",
            ]
        )

        pr = await self._create_pr(pr_title, pr_body, branch_name, base_branch)
        return {
            "branch": branch_name,
            "base_branch": base_branch,
            "pr_number": pr.get("number"),
            "pr_url": pr.get("html_url") or pr.get("url"),
            "files": files,
        }


async def submit_feedback(
    payload: Dict[str, Any],
    *,
    github_config: Optional[GitHubFeedbackConfig] = None,
    github_client: Optional[GitHubPRClient] = None,
) -> Dict[str, Any]:
    """
    Validate/sanitize payload and create GitHub PR.
    Returns preview metadata + PR result.
    """
    github_config = github_config or GitHubFeedbackConfig.from_env()
    if not github_config.ready:
        raise RuntimeError("DOCTOR_GITHUB_TOKEN is not configured")

    preview_result = build_feedback_preview(payload, github_config=github_config)
    stats_payload = preview_result["preview"].get("stats_snapshot") if preview_result.get("include_stats") else None

    if github_client is not None:
        pr_result = await github_client.create_feedback_pr(preview_result=preview_result, stats_payload=stats_payload)
    else:
        async with GitHubPRClient(github_config) as client:
            pr_result = await client.create_feedback_pr(preview_result=preview_result, stats_payload=stats_payload)

    return {
        "submission_id": preview_result["submission_id"],
        "files": preview_result["files"],
        "preview": preview_result["preview"],
        "warnings": preview_result["warnings"],
        "github": {
            **preview_result["github"],
            **pr_result,
        },
    }
