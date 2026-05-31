import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OPENAPI_PATH = ROOT / "docs" / "openapi.json"
API_ROUTES_PATH = ROOT / "api_routes.py"

ROUTE_PATTERN = re.compile(
    r"(?:@server\.PromptServer\.instance\.routes\.|server\.PromptServer\.instance\.routes\.)"
    r"(get|post|put|delete)\(\"([^\"]+)\"\)"
)

ADMIN_GATED_OPERATIONS = {
    ("GET", "/doctor/secrets/status"),
    ("PUT", "/doctor/secrets"),
    ("DELETE", "/doctor/secrets/{provider}"),
    ("POST", "/doctor/statistics/reset"),
    ("POST", "/doctor/mark_resolved"),
    ("POST", "/doctor/feedback/submit"),
    ("POST", "/doctor/telemetry/clear"),
    ("POST", "/doctor/telemetry/toggle"),
    ("POST", "/doctor/jobs/{job_id}/resume"),
    ("POST", "/doctor/jobs/{job_id}/cancel"),
    ("POST", "/doctor/health_ack"),
}


def _load_openapi():
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


def _registered_routes():
    source = API_ROUTES_PATH.read_text(encoding="utf-8")
    return {(method.upper(), path) for method, path in ROUTE_PATTERN.findall(source)}


def _operation(spec, method, path):
    return spec["paths"][path][method.lower()]


def test_d1_openapi_spec_is_valid_json_and_openapi_3():
    spec = _load_openapi()

    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "ComfyUI-Doctor API"
    assert "paths" in spec and spec["paths"]
    assert "AdminTokenAuth" in spec["components"]["securitySchemes"]


def test_d1_openapi_spec_matches_registered_route_contracts():
    spec = _load_openapi()
    registered = _registered_routes()
    documented = {
        (method.upper(), path)
        for path, path_item in spec["paths"].items()
        for method in path_item
        if method.lower() in {"get", "post", "put", "delete"}
    }

    assert registered - documented == set()
    assert documented - registered == set()


def test_d1_admin_gated_operations_declare_admin_security():
    spec = _load_openapi()

    for method, path in sorted(ADMIN_GATED_OPERATIONS):
        operation = _operation(spec, method, path)
        security = operation.get("security", [])
        assert {"AdminTokenAuth": []} in security, f"{method} {path} must declare AdminTokenAuth"


def test_d1_chat_documents_sse_streaming_response():
    spec = _load_openapi()
    content = _operation(spec, "POST", "/doctor/chat")["responses"]["200"]["content"]

    assert "application/json" in content
    assert "text/event-stream" in content


def test_d1_public_spec_does_not_leak_internal_records():
    raw = OPENAPI_PATH.read_text(encoding="utf-8")
    forbidden_fragments = [
        ".planning",
        "reference/",
        "REFERENCE/",
        "ROADMAP",
        "IMPLEMENTATION_RECORD",
        "command log",
        "validation evidence",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in raw
