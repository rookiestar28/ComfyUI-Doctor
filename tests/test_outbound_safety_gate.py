"""
Tests for the outbound safety static check (T12).
"""
import tempfile
from pathlib import Path
import sys

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from check_outbound_safety import check_file, OutboundSafetyChecker


def test_detects_raw_field_in_payload():
    """Should detect raw context field assignment to payload."""
    code = '''
async def bad_handler():
    payload = {"error": context.traceback}
    await session.post(url, json=payload)
'''
    violations = _check_code(code)
    assert len(violations) > 0
    assert any(v.rule == 'RAW_FIELD_IN_PAYLOAD' for v in violations)


def test_detects_dangerous_fallback():
    """Should detect sanitized_X or X pattern."""
    code = '''
async def bad_handler():
    data = {
        "traceback": context.sanitized_traceback or context.traceback
    }
'''
    violations = _check_code(code)
    assert len(violations) > 0
    assert any(v.rule == 'DANGEROUS_FALLBACK' for v in violations)


def test_detects_post_without_sanitization():
    """Should detect POST without sanitize_outbound_payload()."""
    code = '''
async def bad_handler():
    sanitizer, _ = get_outbound_sanitizer(url, mode)
    payload = {"data": "something"}
    await session.post(url, json=payload)
'''
    violations = _check_code(code)
    assert len(violations) > 0
    assert any(v.rule == 'POST_WITHOUT_SANITIZATION' for v in violations)


def test_detects_json_dumps_raw_field():
    """Should detect json.dumps() on raw context field."""
    code = '''
import json
def bad_serializer():
    return json.dumps({
        "system": context.system_info
    })
'''
    violations = _check_code(code)
    assert len(violations) > 0
    assert any(v.rule == 'JSON_DUMPS_RAW_FIELD' for v in violations)


def test_allows_safe_pattern():
    """Should not flag safe sanitization pattern."""
    code = '''
async def good_handler():
    sanitizer, _ = get_outbound_sanitizer(url, mode)
    error_text = sanitizer.sanitize(context.traceback).sanitized_text
    payload = {"error": error_text}
    payload = sanitize_outbound_payload(payload, sanitizer)
    await session.post(url, json=payload)
'''
    violations = _check_code(code)
    assert len(violations) == 0


def test_allows_stage_processing():
    """Should not flag stage processing of context fields."""
    code = '''
def process_stage(context):
    # Reading for processing is safe
    traceback_text = context.traceback
    if context.workflow_json:
        pruned = prune(context.workflow_json)
    return result
'''
    violations = _check_code(code)
    assert len(violations) == 0


def test_respects_nosec_suppression():
    """Should respect nosec comment suppression."""
    code = '''
async def debug_endpoint():
    # nosec: outbound-bypass-allowed - Reason: local debug only
    payload = {"raw": context.traceback}
    await session.post(url, json=payload)
'''
    violations = _check_code(code)
    # Should be suppressed
    assert len(violations) == 0


def test_fixture_file_has_violations():
    """Verify fixture file contains expected violations."""
    fixture_path = Path(__file__).parent / 'fixtures' / 'outbound_violations.py'
    violations = check_file(fixture_path)

    # Should detect multiple violations
    assert len(violations) >= 3, f"Expected at least 3 violations, got {len(violations)}"

    # Check for specific violation types
    rules = {v.rule for v in violations}
    assert 'RAW_FIELD_IN_PAYLOAD' in rules or 'DANGEROUS_FALLBACK' in rules


def _check_code(code: str):
    """Helper to check code snippet."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(code)
        f.flush()
        path = Path(f.name)

    try:
        return check_file(path)
    finally:
        path.unlink()
