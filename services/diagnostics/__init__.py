"""
F14 Proactive Diagnostics

This package provides proactive health checking and diagnostics for ComfyUI workflows.

Main Components:
- models: Data contracts (HealthIssue, HealthReport, IntentSignature)
- runner: Orchestrates diagnostic checks with caching and timeouts
- store: Persistent storage for reports and issue status
- checks: Individual diagnostic check implementations (P1)

Usage:
    from services.diagnostics import get_diagnostics_runner, get_diagnostics_store
    from services.diagnostics.models import HealthCheckRequest, DiagnosticsScope

    # Run diagnostics
    runner = get_diagnostics_runner()
    request = HealthCheckRequest(
        workflow=workflow_json,
        scope=DiagnosticsScope.MANUAL,
        include_intent=True,
    )
    report = await runner.run(request)

    # Save to history
    store = get_diagnostics_store()
    store.save_report(report)
"""

from .models import (
    # Enums
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    DiagnosticsScope,
    SignalSource,
    # Data classes
    IssueTarget,
    HealthIssue,
    IssueCounts,
    HealthReport,
    SignalEvidence,
    IntentMatch,
    IntentSignature,
    # Request/Response
    HealthCheckRequest,
    HealthAckRequest,
    ReportMetadata,
)

from .runner import (
    DiagnosticsRunner,
    get_diagnostics_runner,
)

from .store import (
    DiagnosticsStore,
    get_diagnostics_store,
)

__all__ = [
    # Enums
    "IssueCategory",
    "IssueSeverity",
    "IssueStatus",
    "DiagnosticsScope",
    "SignalSource",
    # Data classes
    "IssueTarget",
    "HealthIssue",
    "IssueCounts",
    "HealthReport",
    "SignalEvidence",
    "IntentMatch",
    "IntentSignature",
    # Request/Response
    "HealthCheckRequest",
    "HealthAckRequest",
    "ReportMetadata",
    # Runner
    "DiagnosticsRunner",
    "get_diagnostics_runner",
    # Store
    "DiagnosticsStore",
    "get_diagnostics_store",
]
