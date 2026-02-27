"""
S10 regression tests:
- Ensure write-sensitive endpoints are admin-guarded.
- Keep route-level guard coverage explicit for future refactors.
"""

from pathlib import Path


def _load_root_init_source() -> str:
    root = Path(__file__).resolve().parent.parent
    for filename in ("__init__.py", "__init__.py.bak"):
        candidate = root / filename
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError("Cannot find project root __init__.py or __init__.py.bak")


def _route_block(source: str, marker: str) -> str:
    start = source.find(marker)
    assert start >= 0, f"Route marker missing: {marker}"

    next_marker = source.find("\n    @server.PromptServer.instance.routes.", start + len(marker))
    if next_marker < 0:
        next_marker = len(source)
    return source[start:next_marker]


def _function_block(source: str, function_name: str) -> str:
    marker = f"async def {function_name}("
    start = source.find(marker)
    assert start >= 0, f"Function missing: {function_name}"

    next_idx = source.find("\nasync def ", start + len(marker))
    if next_idx < 0:
        next_idx = len(source)
    return source[start:next_idx]


def test_s10_write_sensitive_routes_in_init_are_admin_guarded():
    source = _load_root_init_source()
    route_markers = [
        '@server.PromptServer.instance.routes.post("/doctor/statistics/reset")',
        '@server.PromptServer.instance.routes.post("/doctor/mark_resolved")',
        '@server.PromptServer.instance.routes.post("/doctor/telemetry/clear")',
        '@server.PromptServer.instance.routes.post("/doctor/telemetry/toggle")',
        '@server.PromptServer.instance.routes.post("/doctor/health_ack")',
    ]

    for marker in route_markers:
        block = _route_block(source, marker)
        assert "validate_admin_request(" in block, f"Missing admin guard in block: {marker}"


def test_s10_job_mutation_handlers_are_admin_guarded():
    routes_source = Path("services/routes.py").read_text(encoding="utf-8")

    for function_name in ("api_resume_job", "api_cancel_job"):
        block = _function_block(routes_source, function_name)
        assert "validate_admin_request(" in block, f"Missing admin guard in {function_name}"
