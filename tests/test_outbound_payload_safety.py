from pathlib import Path

from outbound import get_outbound_sanitizer, sanitize_outbound_payload
from sanitizer import SanitizationLevel


def test_privacy_none_is_downgraded_for_remote_provider():
    sanitizer, downgraded = get_outbound_sanitizer("https://api.openai.com/v1", "none")
    assert downgraded is True
    assert sanitizer.level == SanitizationLevel.BASIC


def test_privacy_none_is_allowed_for_verified_local_provider():
    sanitizer, downgraded = get_outbound_sanitizer("http://localhost:11434", "none")
    assert downgraded is False
    assert sanitizer.level == SanitizationLevel.NONE


def test_sanitize_outbound_payload_recursively_sanitizes_strings():
    sanitizer, _ = get_outbound_sanitizer("https://api.openai.com/v1", "basic")
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": r"Trace at C:\Users\bob\project\file.py sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            {"role": "assistant", "content": "See /home/alice/private for details"},
        ],
        "extra": {"path": r"C:\Users\bob\.ssh\id_rsa"},
    }

    sanitized = sanitize_outbound_payload(payload, sanitizer)
    assert "<USER_PATH>" in sanitized["messages"][0]["content"]
    assert "<API_KEY>" in sanitized["messages"][0]["content"]
    assert "<USER_HOME>" in sanitized["messages"][1]["content"]
    assert "<USER_PATH>" in sanitized["extra"]["path"]


def test_sensitive_headers_are_redacted_outbound_even_for_local_none_mode():
    sanitizer, downgraded = get_outbound_sanitizer(
        "http://localhost:11434",
        "none",
    )
    payload = {
        "request": {
            "headers": {
                "Authorization": "Bearer fake-outbound-secret",
                "Content-Type": "application/json",
            }
        },
        "responses": [
            {
                "headers": {
                    "x-api-key": "fake-response-secret",
                    "X-Request-ID": "synthetic-id",
                }
            }
        ],
        "log": "Authorization: Basic fake-text-secret",
        "message": "authorization failed without a header value",
    }

    sanitized = sanitize_outbound_payload(payload, sanitizer)
    serialized = repr(sanitized)

    assert downgraded is False
    assert sanitizer.level == SanitizationLevel.NONE
    assert "fake-outbound-secret" not in serialized
    assert "fake-response-secret" not in serialized
    assert "fake-text-secret" not in serialized
    assert sanitized["request"]["headers"]["Authorization"] == "***"
    assert sanitized["responses"][0]["headers"]["x-api-key"] == "***"
    assert sanitized["request"]["headers"]["Content-Type"] == "application/json"
    assert sanitized["responses"][0]["headers"]["X-Request-ID"] == "synthetic-id"
    assert sanitized["message"] == "authorization failed without a header value"


def test_llm_routes_use_outbound_sanitization_funnel():
    project_root = Path(__file__).resolve().parents[1]
    routes_path = project_root / "api_routes.py"
    routes_text = routes_path.read_text(encoding="utf-8")
    assert "sanitize_outbound_payload(payload, sanitizer)" in routes_text
