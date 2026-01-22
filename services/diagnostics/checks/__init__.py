"""
F14 Proactive Diagnostics - Checks Registry

This module provides the registry for diagnostic checks.
Individual check implementations will be added in P1.

Check Implementation Guide:
--------------------------
Each check is an async function with signature:
    async def check_name(workflow: Dict[str, Any], request: HealthCheckRequest) -> List[HealthIssue]

Checks should:
1. Be deterministic (same input → same output)
2. Complete within 2 seconds (or be skipped)
3. Gracefully handle missing data
4. Never include secrets or PII in evidence
5. Provide actionable recommendations

Example check:
    async def check_disconnected_links(workflow, request):
        issues = []
        # ... detect issues ...
        if problem_found:
            issues.append(HealthIssue(
                issue_id=HealthIssue.generate_issue_id("disconnected_link", target, ""),
                category=IssueCategory.WORKFLOW,
                severity=IssueSeverity.WARNING,
                title="Disconnected Link",
                summary="Node X has an unconnected required input",
                evidence=["Input 'model' on node 5 is not connected"],
                recommendation=["Connect the 'model' input to a compatible output"],
                target=IssueTarget(node_id=5),
            ))
        return issues
"""

from typing import Dict, Any, List, Callable, Awaitable
from ..models import HealthIssue, HealthCheckRequest
from ..runner import get_diagnostics_runner

# Type alias for check functions
CheckFunction = Callable[[Dict[str, Any], HealthCheckRequest], Awaitable[List[HealthIssue]]]

# Registry of available checks
_checks: Dict[str, CheckFunction] = {}


def register_check(name: str):
    """
    Decorator to register a diagnostic check.

    Usage:
        @register_check("workflow_lint")
        async def check_workflow_lint(workflow, request):
            ...
    """
    def decorator(fn: CheckFunction) -> CheckFunction:
        _checks[name] = fn
        return fn
    return decorator


def get_registered_checks() -> Dict[str, CheckFunction]:
    """Get all registered checks."""
    return _checks.copy()


def init_checks():
    """
    Initialize all checks and register them with the runner.

    Called during module initialization.
    """
    runner = get_diagnostics_runner()

    # Import check modules to trigger registration
    from . import workflow_lint
    from . import env_deps
    from . import model_assets
    from . import privacy_security
    from . import runtime_performance

    # Register all discovered checks
    for name, check_fn in _checks.items():
        runner.register_check(name, check_fn)


# Placeholder checks for P0 (will be replaced in P1)
# These ensure the system works end-to-end during initial development


@register_check("placeholder")
async def check_placeholder(workflow: Dict[str, Any], request: HealthCheckRequest) -> List[HealthIssue]:
    """
    Placeholder check for P0 skeleton.

    Returns empty list - actual checks will be implemented in P1.
    """
    return []


# Auto-initialize when module is imported
# Auto-initialize when module is imported
init_checks()
