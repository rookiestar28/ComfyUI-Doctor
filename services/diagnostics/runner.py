"""
F14 Proactive Diagnostics - Runner

Orchestrates diagnostic checks with caching, timeouts, and graceful degradation.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Awaitable
from functools import lru_cache

from .models import (
    HealthReport,
    HealthIssue,
    HealthCheckRequest,
    DiagnosticsScope,
    IssueCounts,
    IntentSignature,
)

logger = logging.getLogger("comfyui-doctor.diagnostics")


class DiagnosticsRunner:
    """
    Orchestrates diagnostic checks on workflow snapshots.

    Responsibilities:
    - Accept workflow snapshot + scope + options
    - Canonicalize workflow and compute hash
    - Execute registered checks with timeouts
    - Aggregate issues and compute health score
    - Optionally compute intent signature
    - Cache results for short TTL
    """

    # Configuration
    DEFAULT_CHECK_TIMEOUT_MS = 2000  # 2s per check
    DEFAULT_GLOBAL_TIMEOUT_MS = 5000  # 5s total
    CACHE_TTL_SECONDS = 60  # Cache results for 60s

    def __init__(self):
        self._checks: List[Callable[[Dict[str, Any], HealthCheckRequest], Awaitable[List[HealthIssue]]]] = []
        self._check_names: List[str] = []
        self._cache: Dict[str, tuple[HealthReport, float]] = {}  # (report, timestamp)
        self._last_report: Optional[HealthReport] = None
        self._intent_scorer: Optional[Any] = None  # Set by services/intent

    def register_check(
        self,
        name: str,
        check_fn: Callable[[Dict[str, Any], HealthCheckRequest], Awaitable[List[HealthIssue]]],
    ):
        """
        Register a diagnostic check function.

        Args:
            name: Human-readable check name for logging
            check_fn: Async function that takes (workflow, request) and returns List[HealthIssue]
        """
        self._checks.append(check_fn)
        self._check_names.append(name)
        logger.info(f"Registered diagnostic check: {name}")

    def set_intent_scorer(self, scorer: Any):
        """Set the intent signature scorer (from services/intent)."""
        self._intent_scorer = scorer

    def canonicalize_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Canonicalize workflow for deterministic hashing.

        Normalizes:
        - Sort keys
        - Strip UI-only fields (position, size, color, etc.)
        - Normalize node IDs to strings
        - Sort nodes by ID for stable ordering
        - Exclude viewport/UI state (extra.ds)
        """
        if not workflow:
            return {}

        # Fields to strip (UI-only, no semantic meaning)
        strip_fields = {"pos", "size", "color", "bgcolor", "shape", "flags", "order"}

        def normalize_node(node: Dict[str, Any]) -> Dict[str, Any]:
            """Normalize a single node, converting id to string."""
            normalized = {}
            for k, v in sorted(node.items()):
                if k in strip_fields:
                    continue
                # Normalize node id to string for consistency
                if k == "id" and v is not None:
                    normalized[k] = str(v)
                else:
                    normalized[k] = v
            return normalized

        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        # Normalize nodes and sort by id for deterministic ordering
        normalized_nodes = []
        if isinstance(nodes, list):
            for n in nodes:
                if isinstance(n, dict):
                    normalized_nodes.append(normalize_node(n))
            # Sort by id (now string) for stable ordering
            normalized_nodes.sort(key=lambda x: x.get("id", ""))

        canonical = {
            "nodes": normalized_nodes,
            "links": sorted(links, key=lambda x: x[0] if isinstance(x, list) and x else 0) if isinstance(links, list) else [],
        }

        # Include extra graph properties if present
        # NOTE: Exclude 'ds' (viewport/zoom state) as it's UI-only
        if "extra" in workflow and isinstance(workflow["extra"], dict):
            extra = workflow["extra"]
            # Only include workflow-relevant extra fields (not ds)
            workflow_extra = {k: v for k, v in extra.items() if k not in ("ds",)}
            if workflow_extra:
                canonical["extra"] = workflow_extra

        return canonical

    def compute_workflow_hash(self, workflow: Dict[str, Any]) -> str:
        """Compute deterministic hash of canonicalized workflow."""
        canonical = self.canonicalize_workflow(workflow)
        json_str = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode()).hexdigest()[:32]

    def _get_cache_key(self, workflow_hash: str, request: HealthCheckRequest) -> str:
        """Generate cache key from workflow hash and options."""
        options_str = f"{request.include_intent}:{request.max_paths}"
        return f"{workflow_hash}:{options_str}"

    def _get_cached_report(self, cache_key: str) -> Optional[HealthReport]:
        """Get cached report if still valid."""
        if cache_key in self._cache:
            report, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL_SECONDS:
                logger.debug(f"Cache hit for {cache_key[:16]}...")
                return report
            else:
                del self._cache[cache_key]
        return None

    def _cache_report(self, cache_key: str, report: HealthReport):
        """Cache a report with current timestamp."""
        self._cache[cache_key] = (report, time.time())
        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest = sorted(self._cache.items(), key=lambda x: x[1][1])[:50]
            for key, _ in oldest:
                del self._cache[key]

    async def _run_check_with_timeout(
        self,
        name: str,
        check_fn: Callable[[Dict[str, Any], HealthCheckRequest], Awaitable[List[HealthIssue]]],
        workflow: Dict[str, Any],
        request: HealthCheckRequest,
        timeout_ms: int,
    ) -> List[HealthIssue]:
        """Run a single check with timeout and error handling."""
        try:
            result = await asyncio.wait_for(
                check_fn(workflow, request),
                timeout=timeout_ms / 1000.0,
            )
            return result if isinstance(result, list) else []
        except asyncio.TimeoutError:
            logger.warning(f"Check '{name}' timed out after {timeout_ms}ms")
            return []
        except Exception as e:
            logger.error(f"Check '{name}' failed: {e}")
            return []

    async def run(self, request: HealthCheckRequest) -> HealthReport:
        """
        Run diagnostics on a workflow.

        Args:
            request: Health check request with workflow and options

        Returns:
            HealthReport with issues, score, and optional intent signature
        """
        start_time = time.time()
        workflow = request.workflow or {}
        workflow_hash = self.compute_workflow_hash(workflow)

        # Check cache
        cache_key = self._get_cache_key(workflow_hash, request)
        cached = self._get_cached_report(cache_key)
        if cached:
            return cached

        # Run all checks concurrently with global timeout
        all_issues: List[HealthIssue] = []

        if self._checks:
            try:
                check_tasks = [
                    self._run_check_with_timeout(
                        name,
                        check_fn,
                        workflow,
                        request,
                        self.DEFAULT_CHECK_TIMEOUT_MS,
                    )
                    for name, check_fn in zip(self._check_names, self._checks)
                ]

                results = await asyncio.wait_for(
                    asyncio.gather(*check_tasks, return_exceptions=True),
                    timeout=self.DEFAULT_GLOBAL_TIMEOUT_MS / 1000.0,
                )

                for result in results:
                    if isinstance(result, list):
                        all_issues.extend(result)

            except asyncio.TimeoutError:
                logger.warning("Global diagnostics timeout reached")
            except Exception as e:
                logger.error(f"Diagnostics runner error: {e}")

        # Compute intent signature if requested
        intent_signature = None
        if request.include_intent and self._intent_scorer:
            try:
                intent_signature = await self._intent_scorer.compute(
                    workflow, workflow_hash
                )
            except Exception as e:
                logger.error(f"Intent signature computation failed: {e}")

        # Compute score and counts
        health_score = HealthReport.compute_health_score(all_issues)
        counts = HealthReport.count_issues(all_issues)

        # Build report
        duration_ms = int((time.time() - start_time) * 1000)
        report = HealthReport(
            report_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            duration_ms=duration_ms,
            scope=request.scope,
            workflow_hash=workflow_hash,
            health_score=health_score,
            counts=counts,
            issues=all_issues,
            intent_signature=intent_signature,
        )

        # Cache and store
        self._cache_report(cache_key, report)
        self._last_report = report

        logger.info(
            f"Diagnostics completed: score={health_score}, "
            f"issues={len(all_issues)}, duration={duration_ms}ms"
        )

        return report

    def get_last_report(self) -> Optional[HealthReport]:
        """Get the last computed report (cached)."""
        return self._last_report

    def clear_cache(self):
        """Clear the report cache."""
        self._cache.clear()


# Global instance
_runner: Optional[DiagnosticsRunner] = None


def get_diagnostics_runner() -> DiagnosticsRunner:
    """Get or create the global DiagnosticsRunner instance."""
    global _runner
    if _runner is None:
        _runner = DiagnosticsRunner()
    return _runner
