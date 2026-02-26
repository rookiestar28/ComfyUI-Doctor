"""
F16: Tests for quick community feedback (GitHub PR) service.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple

import pytest

from services.community_feedback import (
    FeedbackValidationError,
    GitHubFeedbackConfig,
    GitHubPRClient,
    build_feedback_preview,
    submit_feedback,
)


def _sample_payload(**overrides) -> Dict[str, Any]:
    payload = {
        "pattern_candidate": {
            "id": "community_tensor_mismatch_feedback",
            "regex": r"RuntimeError:\s+The size of tensor .+ mismatch",
            "category": "workflow",
            "priority": 65,
            "notes": r"Observed on C:\Users\Ray\ComfyUI with email ray@example.com",
        },
        "suggestion_candidate": {
            "language": "en",
            "message": "Check latent/image sizes and verify node input dimensions before sampling.",
        },
        "error_context": {
            "last_error": r"RuntimeError: tensor mismatch at C:\Users\Ray\foo\bar.py user=ray@example.com ip=192.168.1.12",
            "error_summary": "RuntimeError: tensor mismatch",
            "timestamp": "2026-02-26T12:34:56Z",
            "node_context": {"node_id": "42", "node_name": "KSampler"},
            "workflow": {"extra": {"nodes_count": 37}},
        },
        "include_stats": True,
        "stats_snapshot": {
            "time_range_days": 30,
            "total_errors": 12,
            "resolution_rate": {"resolved": 5, "unresolved": 6, "ignored": 1},
            "top_patterns": [{"pattern_id": "cuda_oom_classic", "count": 4, "category": "memory"}],
        },
    }
    for k, v in overrides.items():
        payload[k] = v
    return payload


def test_build_feedback_preview_sanitizes_sensitive_strings():
    preview = build_feedback_preview(
        _sample_payload(),
        github_config=GitHubFeedbackConfig(token="", repo="rookiestar28/ComfyUI-Doctor"),
    )
    preview_json = str(preview["preview"])
    assert "<USER_PATH>" in preview_json
    assert "<EMAIL>" in preview_json
    assert "<PRIVATE_IP>" in preview_json
    assert preview["files"]["submission"].startswith("feedback/submissions/")
    assert preview["files"]["stats"].startswith("feedback/stats/")
    assert preview["include_stats"] is True


def test_build_feedback_preview_validates_required_fields():
    bad = _sample_payload(
        pattern_candidate={"id": "community_bad", "regex": "", "category": "workflow"},
    )
    with pytest.raises(FeedbackValidationError) as exc:
        build_feedback_preview(bad, github_config=GitHubFeedbackConfig(token="x"))
    assert "pattern_candidate.regex" in exc.value.field_errors


def test_build_feedback_preview_requires_error_context():
    bad = _sample_payload(error_context={})
    with pytest.raises(FeedbackValidationError) as exc:
        build_feedback_preview(bad, github_config=GitHubFeedbackConfig(token="x"))
    assert "error_context" in exc.value.field_errors


class _FakeSubmitClient:
    def __init__(self):
        self.called = False
        self.last_preview = None
        self.last_stats = None

    async def create_feedback_pr(self, *, preview_result, stats_payload):
        self.called = True
        self.last_preview = preview_result
        self.last_stats = stats_payload
        return {
            "branch": f"feedback/20260226/{preview_result['submission_id']}",
            "base_branch": "main",
            "pr_number": 123,
            "pr_url": "https://github.com/rookiestar28/ComfyUI-Doctor/pull/123",
            "files": preview_result["files"],
        }


def test_submit_feedback_uses_injected_github_client():
    fake_client = _FakeSubmitClient()
    config = GitHubFeedbackConfig(token="ghp_test", repo="rookiestar28/ComfyUI-Doctor")
    result = asyncio.run(submit_feedback(_sample_payload(), github_config=config, github_client=fake_client))

    assert fake_client.called is True
    assert result["github"]["pr_number"] == 123
    assert result["github"]["pr_url"].endswith("/pull/123")
    assert result["files"]["submission"].startswith("feedback/submissions/")
    assert fake_client.last_stats is not None


class _MockGitHubClient(GitHubPRClient):
    def __init__(self, config: GitHubFeedbackConfig):
        super().__init__(config)
        self.calls: list[Tuple[str, str, Dict[str, Any] | None]] = []

    async def _request_json(self, method: str, path: str, *, expected=(200,), body=None):  # type: ignore[override]
        self.calls.append((method, path, body))
        if method == "GET" and path == f"/repos/{self.config.repo}":
            return {"default_branch": "main"}
        if method == "GET" and path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "abc123sha"}}
        if method == "POST" and path.endswith("/git/refs"):
            return {"ref": body["ref"], "object": {"sha": body["sha"]}}
        if method == "PUT" and "/contents/" in path:
            return {"content": {"path": path.split("/contents/", 1)[1]}}
        if method == "POST" and path.endswith("/pulls"):
            return {"number": 77, "html_url": "https://github.com/rookiestar28/ComfyUI-Doctor/pull/77"}
        raise AssertionError(f"Unexpected call: {method} {path}")


def test_github_pr_client_create_feedback_pr_sequence():
    config = GitHubFeedbackConfig(token="ghp_test", repo="rookiestar28/ComfyUI-Doctor")
    client = _MockGitHubClient(config)
    preview = build_feedback_preview(_sample_payload(), github_config=config)

    result = asyncio.run(
        client.create_feedback_pr(
            preview_result=preview,
            stats_payload=preview["preview"].get("stats_snapshot"),
        )
    )

    assert result["pr_number"] == 77
    assert result["branch"].startswith("feedback/")
    paths = [p for _, p, _ in client.calls]
    assert f"/repos/{config.repo}" in paths[0]
    assert any("/git/ref/heads/main" in p for p in paths)
    assert sum(1 for p in paths if "/contents/" in p) >= 2  # submission + stats
    assert any(p.endswith("/pulls") for p in paths)
