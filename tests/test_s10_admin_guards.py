"""
S10 regression tests:
- Ensure write-sensitive endpoints are admin-guarded.
- Keep route-level guard coverage explicit for future refactors.
"""

from pathlib import Path


def _load_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parent.parent
    candidate = root / relative_path
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    if relative_path == "__init__.py":
        backup = root / "__init__.py.bak"
        if backup.exists():
            return backup.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Cannot find {relative_path}")


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


def test_s10_write_sensitive_routes_are_admin_guarded():
    source = _load_source("api_routes.py")
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
    routes_source = _load_source("services/routes.py")

    for function_name in ("api_resume_job", "api_cancel_job"):
        block = _function_block(routes_source, function_name)
        assert "validate_admin_request(" in block, f"Missing admin guard in {function_name}"


def test_s10_package_entrypoint_only_wires_route_modules():
    source = _load_source("__init__.py")

    assert "register_api_routes(" in source
    assert "@server.PromptServer.instance.routes." not in source
    assert "async def api_" not in source


def test_a11_api_routes_keep_expected_method_path_contracts():
    source = _load_source("api_routes.py")
    expected_markers = [
        '@server.PromptServer.instance.routes.get("/debugger/last_analysis")',
        '@server.PromptServer.instance.routes.post("/debugger/set_language")',
        '@server.PromptServer.instance.routes.get("/doctor/ui_text")',
        '@server.PromptServer.instance.routes.post("/doctor/analyze")',
        '@server.PromptServer.instance.routes.post("/doctor/chat")',
        '@server.PromptServer.instance.routes.get("/debugger/history")',
        '@server.PromptServer.instance.routes.post("/debugger/clear_history")',
        '@server.PromptServer.instance.routes.get("/doctor/provider_defaults")',
        '@server.PromptServer.instance.routes.get("/doctor/secrets/status")',
        '@server.PromptServer.instance.routes.put("/doctor/secrets")',
        '@server.PromptServer.instance.routes.delete("/doctor/secrets/{provider}")',
        '@server.PromptServer.instance.routes.post("/doctor/verify_key")',
        '@server.PromptServer.instance.routes.post("/doctor/list_models")',
        '@server.PromptServer.instance.routes.get("/doctor/statistics")',
        '@server.PromptServer.instance.routes.post("/doctor/statistics/reset")',
        '@server.PromptServer.instance.routes.post("/doctor/mark_resolved")',
        '@server.PromptServer.instance.routes.post("/doctor/feedback/preview")',
        '@server.PromptServer.instance.routes.post("/doctor/feedback/submit")',
        '@server.PromptServer.instance.routes.get("/doctor/health")',
        '@server.PromptServer.instance.routes.get("/doctor/telemetry/status")',
        '@server.PromptServer.instance.routes.get("/doctor/telemetry/buffer")',
        '@server.PromptServer.instance.routes.post("/doctor/telemetry/track")',
        '@server.PromptServer.instance.routes.post("/doctor/telemetry/clear")',
        '@server.PromptServer.instance.routes.get("/doctor/telemetry/export")',
        '@server.PromptServer.instance.routes.post("/doctor/telemetry/toggle")',
        '@server.PromptServer.instance.routes.post("/doctor/health_check")',
        '@server.PromptServer.instance.routes.get("/doctor/health_report")',
        '@server.PromptServer.instance.routes.get("/doctor/health_history")',
        '@server.PromptServer.instance.routes.post("/doctor/health_ack")',
    ]

    for marker in expected_markers:
        assert marker in source, f"Missing route contract: {marker}"
