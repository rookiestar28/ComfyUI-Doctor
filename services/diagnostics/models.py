"""
F14 Proactive Diagnostics - Data Models

Defines data contracts for health checks, diagnostics reports, and intent signatures.
All models use dataclasses for deterministic serialization and validation.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib
import json


class IssueCategory(str, Enum):
    """Categories of diagnostic issues."""
    WORKFLOW = "workflow"
    ENV = "env"
    DEPS = "deps"
    MODEL = "model"
    RUNTIME = "runtime"
    PRIVACY = "privacy"
    SECURITY = "security"
    PERFORMANCE = "performance"


class IssueSeverity(str, Enum):
    """Severity levels for diagnostic issues."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    """Status of a diagnostic issue."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IGNORED = "ignored"
    RESOLVED = "resolved"


class DiagnosticsScope(str, Enum):
    """Scope/trigger of the diagnostics run."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    PRE_EXEC = "pre_exec"
    WORKFLOW_CHANGE = "workflow_change"


class SignalSource(str, Enum):
    """Source of an intent signal."""
    WORKFLOW = "workflow"
    ENV = "env"
    RUNTIME = "runtime"
    ERROR = "error"


@dataclass
class IssueTarget:
    """Target location of a diagnostic issue."""
    node_id: Optional[int] = None
    path: Optional[str] = None
    setting: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HealthIssue:
    """
    A single diagnostic issue detected during health check.

    Attributes:
        issue_id: Stable deterministic ID (check_id + target + hash)
        category: Type of issue (workflow, env, deps, etc.)
        severity: Issue severity level
        title: Short UI title
        summary: 1-2 line description
        evidence: List of evidence strings (sanitized)
        recommendation: List of actionable steps
        target: Location of the issue (node, path, or setting)
        status: Current status of the issue
    """
    issue_id: str
    category: IssueCategory
    severity: IssueSeverity
    title: str
    summary: str
    evidence: List[str] = field(default_factory=list)
    recommendation: List[str] = field(default_factory=list)
    target: IssueTarget = field(default_factory=IssueTarget)
    status: IssueStatus = field(default=IssueStatus.OPEN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "summary": self.summary,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "target": self.target.to_dict(),
            "status": self.status.value,
        }

    @staticmethod
    def generate_issue_id(check_id: str, target: IssueTarget, content_hash: str = "") -> str:
        """Generate a stable, deterministic issue ID."""
        target_str = json.dumps(target.to_dict(), sort_keys=True)
        hash_input = f"{check_id}:{target_str}:{content_hash}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


@dataclass
class IssueCounts:
    """Summary counts of issues by severity."""
    critical: int = 0
    warning: int = 0
    info: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class HealthReport:
    """
    Complete health check report.

    Attributes:
        report_id: Unique report identifier
        timestamp: ISO 8601 timestamp
        duration_ms: Time taken to generate report
        scope: Trigger/scope of the diagnostics run
        workflow_hash: Hash of canonicalized workflow (no PII)
        health_score: Overall health score (0-100)
        counts: Summary counts by severity
        issues: List of detected issues
        intent_signature: Optional intent signature (when enabled)
    """
    report_id: str
    timestamp: str
    duration_ms: int
    scope: DiagnosticsScope
    workflow_hash: str
    health_score: int
    counts: IssueCounts
    issues: List[HealthIssue] = field(default_factory=list)
    intent_signature: Optional["IntentSignature"] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "scope": self.scope.value,
            "workflow_hash": self.workflow_hash,
            "health_score": self.health_score,
            "counts": self.counts.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
        }
        if self.intent_signature:
            result["intent_signature"] = self.intent_signature.to_dict()
        return result

    @staticmethod
    def compute_health_score(issues: List[HealthIssue]) -> int:
        """
        Compute health score from issues.

        Scoring:
        - Start at 100
        - Critical: -30 per issue
        - Warning: -10 per issue
        - Info: -2 per issue
        - Minimum score is 0
        """
        score = 100
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                score -= 30
            elif issue.severity == IssueSeverity.WARNING:
                score -= 10
            elif issue.severity == IssueSeverity.INFO:
                score -= 2
        return max(0, score)

    @staticmethod
    def count_issues(issues: List[HealthIssue]) -> IssueCounts:
        """Count issues by severity."""
        counts = IssueCounts()
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                counts.critical += 1
            elif issue.severity == IssueSeverity.WARNING:
                counts.warning += 1
            elif issue.severity == IssueSeverity.INFO:
                counts.info += 1
        return counts


# ============================================================================
# Intent Signature (ISS) Models
# ============================================================================

@dataclass
class SignalEvidence:
    """
    Evidence for an intent signal.

    Attributes:
        signal_id: Unique signal identifier (e.g., node_present.IPAdapterApply)
        weight: Signal weight for scoring
        value: Signal value (string, number, or bool)
        source: Where the signal came from
        node_ids: Optional list of related node IDs
        explain: Short explanation text (sanitized)
    """
    signal_id: str
    weight: float
    value: Any
    source: SignalSource
    node_ids: Optional[List[int]] = None
    explain: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "signal_id": self.signal_id,
            "weight": self.weight,
            "value": self.value,
            "source": self.source.value,
            "explain": self.explain,
        }
        if self.node_ids:
            result["node_ids"] = self.node_ids
        return result


@dataclass
class IntentMatch:
    """
    A matched intent with confidence score.

    Attributes:
        intent_id: Unique intent identifier
        confidence: Confidence score (0.0-1.0)
        stage: Optional workflow stage (setup, generation, postprocess)
        evidence: List of supporting evidence
    """
    intent_id: str
    confidence: float
    stage: Optional[str] = None
    evidence: List[SignalEvidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "intent_id": self.intent_id,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
        }
        if self.stage:
            result["stage"] = self.stage
        return result


@dataclass
class IntentSignature:
    """
    Intent Signature (ISS) - deterministic inference of user intent.

    Attributes:
        schema_version: ISS schema version
        timestamp: ISO 8601 timestamp
        workflow_hash: Hash of the analyzed workflow
        top_intents: Top-k matched intents (default 3)
        global_signals: Evidence not tied to specific intents
    """
    schema_version: str
    timestamp: str
    workflow_hash: str
    top_intents: List[IntentMatch] = field(default_factory=list)
    global_signals: List[SignalEvidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "workflow_hash": self.workflow_hash,
            "top_intents": [i.to_dict() for i in self.top_intents],
            "global_signals": [s.to_dict() for s in self.global_signals],
        }


# ============================================================================
# Request/Response Models
# ============================================================================

@dataclass
class HealthCheckRequest:
    """Request payload for POST /doctor/health_check."""
    workflow: Dict[str, Any]
    scope: DiagnosticsScope = DiagnosticsScope.MANUAL
    include_intent: bool = True
    max_paths: int = 50

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "HealthCheckRequest":
        """Parse request from JSON dict."""
        options = data.get("options", {})
        scope_str = data.get("scope", "manual")
        try:
            scope = DiagnosticsScope(scope_str)
        except ValueError:
            scope = DiagnosticsScope.MANUAL

        return HealthCheckRequest(
            workflow=data.get("workflow", {}),
            scope=scope,
            include_intent=options.get("include_intent", True),
            max_paths=options.get("max_paths", 50),
        )


@dataclass
class HealthAckRequest:
    """Request payload for POST /doctor/health_ack."""
    report_id: str
    issue_id: str
    status: IssueStatus

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "HealthAckRequest":
        """Parse request from JSON dict."""
        status_str = data.get("status", "acknowledged")
        try:
            status = IssueStatus(status_str)
        except ValueError:
            status = IssueStatus.ACKNOWLEDGED

        return HealthAckRequest(
            report_id=data.get("report_id", ""),
            issue_id=data.get("issue_id", ""),
            status=status,
        )


@dataclass
class ReportMetadata:
    """Lightweight report metadata for history listing."""
    report_id: str
    timestamp: str
    scope: str
    workflow_hash: str
    health_score: int
    counts: IssueCounts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "scope": self.scope,
            "workflow_hash": self.workflow_hash,
            "health_score": self.health_score,
            "counts": self.counts.to_dict(),
        }

    @staticmethod
    def from_report(report: HealthReport) -> "ReportMetadata":
        """Extract metadata from a full report."""
        return ReportMetadata(
            report_id=report.report_id,
            timestamp=report.timestamp,
            scope=report.scope.value,
            workflow_hash=report.workflow_hash,
            health_score=report.health_score,
            counts=report.counts,
        )
