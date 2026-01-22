"""
F14 Proactive Diagnostics - History Store

Persists diagnostic reports with retention policies.
Follows existing history patterns in ComfyUI-Doctor.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Lock

from .models import (
    HealthReport,
    HealthIssue,
    IssueStatus,
    ReportMetadata,
)

logger = logging.getLogger("comfyui-doctor.diagnostics.store")


class DiagnosticsStore:
    """
    Persistent storage for diagnostic reports.

    Features:
    - Stores report metadata + issues (no raw logs, no secrets)
    - Configurable retention (default: 100 reports, 30 days)
    - Thread-safe operations
    - Issue status updates (ack/ignore/resolve)
    """

    # Configuration
    DEFAULT_MAX_REPORTS = 100
    DEFAULT_RETENTION_DAYS = 30
    STORE_FILENAME = "diagnostics_history.json"

    def __init__(self, storage_dir: Optional[str] = None, max_reports: int = DEFAULT_MAX_REPORTS, retention_days: int = DEFAULT_RETENTION_DAYS):
        """
        Initialize the diagnostics store.

        Args:
            storage_dir: Directory for persistence (default: user data dir)
            max_reports: Maximum number of reports to retain
            retention_days: Maximum age of reports in days
        """
        self.max_reports = max_reports
        self.retention_days = retention_days
        self._lock = Lock()

        # Determine storage directory
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            # Use ComfyUI user directory if available
            self.storage_dir = self._get_default_storage_dir()

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.storage_dir / self.STORE_FILENAME

        # In-memory cache
        self._reports: Dict[str, Dict[str, Any]] = {}  # report_id -> report dict
        self._issue_status: Dict[str, IssueStatus] = {}  # issue_id -> status

        # Load existing data
        self._load()

    def _get_default_storage_dir(self) -> Path:
        """Get default storage directory."""
        # Try ComfyUI user directory first
        try:
            import folder_paths
            user_dir = folder_paths.get_user_directory()
            return Path(user_dir) / "comfyui-doctor" / "diagnostics"
        except ImportError:
            pass

        # Fallback to system-specific user data
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

        return base / "comfyui-doctor" / "diagnostics"

    def _load(self):
        """Load store from disk."""
        if not self.store_path.exists():
            logger.debug("No existing diagnostics store found")
            return

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._reports = data.get("reports", {})
            self._issue_status = {
                k: IssueStatus(v) for k, v in data.get("issue_status", {}).items()
            }

            logger.info(f"Loaded {len(self._reports)} diagnostic reports from store")

            # Apply retention on load
            self._apply_retention()

        except Exception as e:
            logger.error(f"Failed to load diagnostics store: {e}")
            self._reports = {}
            self._issue_status = {}

    def _save(self):
        """Save store to disk."""
        try:
            data = {
                "reports": self._reports,
                "issue_status": {k: v.value for k, v in self._issue_status.items()},
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            # Atomic write
            temp_path = self.store_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.store_path)

            logger.debug(f"Saved {len(self._reports)} diagnostic reports to store")

        except Exception as e:
            logger.error(f"Failed to save diagnostics store: {e}")

    def _apply_retention(self):
        """Apply retention policies (max count, max age)."""
        if not self._reports:
            return

        now = datetime.utcnow()
        cutoff = now - timedelta(days=self.retention_days)

        # Filter by age
        valid_reports = {
            k: v for k, v in self._reports.items()
            if self._parse_timestamp(v.get("timestamp", "")) > cutoff
        }

        # Sort by timestamp and keep newest
        if len(valid_reports) > self.max_reports:
            sorted_reports = sorted(
                valid_reports.items(),
                key=lambda x: x[1].get("timestamp", ""),
                reverse=True,
            )
            valid_reports = dict(sorted_reports[:self.max_reports])

        removed = len(self._reports) - len(valid_reports)
        if removed > 0:
            logger.info(f"Retention policy removed {removed} old reports")
            self._reports = valid_reports

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse ISO timestamp, return epoch on failure."""
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return datetime.min

    def save_report(self, report: HealthReport):
        """
        Save a diagnostic report.

        Args:
            report: The HealthReport to save
        """
        with self._lock:
            # Convert to dict (strips sensitive data already in models)
            report_dict = report.to_dict()

            # Store
            self._reports[report.report_id] = report_dict

            # Update issue status cache
            for issue in report.issues:
                if issue.issue_id not in self._issue_status:
                    self._issue_status[issue.issue_id] = issue.status

            # Apply retention
            self._apply_retention()

            # Persist
            self._save()

            logger.debug(f"Saved report {report.report_id}")

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a report by ID.

        Args:
            report_id: The report ID

        Returns:
            Report dict or None if not found
        """
        with self._lock:
            report = self._reports.get(report_id)
            if report:
                # Merge current issue statuses
                report = self._merge_issue_status(report)
            return report

    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get report metadata history.

        Args:
            limit: Maximum number of reports to return
            offset: Number of reports to skip

        Returns:
            List of report metadata dicts (lightweight, no full issues)
        """
        with self._lock:
            # Sort by timestamp descending
            sorted_reports = sorted(
                self._reports.items(),
                key=lambda x: x[1].get("timestamp", ""),
                reverse=True,
            )

            # Apply pagination
            paginated = sorted_reports[offset:offset + limit]

            # Return metadata only
            return [
                {
                    "report_id": v.get("report_id"),
                    "timestamp": v.get("timestamp"),
                    "scope": v.get("scope"),
                    "workflow_hash": v.get("workflow_hash"),
                    "health_score": v.get("health_score"),
                    "counts": v.get("counts"),
                }
                for _, v in paginated
            ]

    def update_issue_status(self, report_id: str, issue_id: str, status: IssueStatus) -> bool:
        """
        Update the status of an issue.

        Args:
            report_id: The report ID containing the issue
            issue_id: The issue ID to update
            status: New status

        Returns:
            True if updated, False if not found
        """
        with self._lock:
            if report_id not in self._reports:
                return False

            report = self._reports[report_id]
            issues = report.get("issues", [])

            # Find and update issue
            found = False
            for issue in issues:
                if issue.get("issue_id") == issue_id:
                    issue["status"] = status.value
                    found = True
                    break

            if found:
                # Also update global status cache
                self._issue_status[issue_id] = status
                self._save()
                logger.info(f"Updated issue {issue_id} status to {status.value}")

            return found

    def _merge_issue_status(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Merge current issue statuses into report."""
        report = report.copy()
        issues = report.get("issues", [])
        updated_issues = []
        for issue in issues:
            issue = issue.copy()
            issue_id = issue.get("issue_id")
            if issue_id in self._issue_status:
                issue["status"] = self._issue_status[issue_id].value
            updated_issues.append(issue)
        report["issues"] = updated_issues
        return report

    def get_issue_status(self, issue_id: str) -> Optional[IssueStatus]:
        """Get the current status of an issue."""
        with self._lock:
            return self._issue_status.get(issue_id)

    def clear(self):
        """Clear all stored data."""
        with self._lock:
            self._reports.clear()
            self._issue_status.clear()
            self._save()
            logger.info("Cleared diagnostics store")


# Global instance
_store: Optional[DiagnosticsStore] = None


def get_diagnostics_store() -> DiagnosticsStore:
    """Get or create the global DiagnosticsStore instance."""
    global _store
    if _store is None:
        _store = DiagnosticsStore()
    return _store
