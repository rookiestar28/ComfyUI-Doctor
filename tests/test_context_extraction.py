"""
Tests for R14: Context Extraction & Prompt Optimization.

Coverage:
- extract_error_summary: Standard traceback, single-line errors
- collapse_stack_frames: Head/tail preservation, omit indicator
- detect_fatal_pattern: Non-traceback error detection
- build_context_manifest: Observability metadata
"""

import pytest
from services.context_extractor import (
    extract_error_summary,
    collapse_stack_frames,
    detect_fatal_pattern,
    build_context_manifest,
    ErrorSummary,
    ContextManifest,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_TRACEBACK = """Traceback (most recent call last):
  File "/app/main.py", line 10, in <module>
    result = process_data(data)
  File "/app/processor.py", line 25, in process_data
    validated = validate(data)
  File "/app/validator.py", line 42, in validate
    check_schema(data)
  File "/app/schema.py", line 15, in check_schema
    raise ValueError("Invalid schema")
ValueError: Invalid schema"""

SAMPLE_TRACEBACK_LONG = """Traceback (most recent call last):
  File "/app/main.py", line 10, in <module>
    result = process()
  File "/app/step1.py", line 20, in step1
    step2()
  File "/app/step2.py", line 30, in step2
    step3()
  File "/app/step3.py", line 40, in step3
    step4()
  File "/app/step4.py", line 50, in step4
    step5()
  File "/app/step5.py", line 60, in step5
    step6()
  File "/app/step6.py", line 70, in step6
    step7()
  File "/app/step7.py", line 80, in step7
    step8()
  File "/app/step8.py", line 90, in step8
    raise RuntimeError("Deep error")
RuntimeError: Deep error"""

SINGLE_LINE_ERROR = "RuntimeError: Failed to load model checkpoint"

CUDA_OOM_ERROR = "CUDA out of memory. Tried to allocate 2.00 GiB"


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: extract_error_summary
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractErrorSummary:
    """Tests for extract_error_summary function."""
    
    def test_standard_traceback(self):
        """Should extract exception type and message from standard traceback."""
        summary = extract_error_summary(SAMPLE_TRACEBACK)
        
        assert summary is not None
        assert summary.exception_type == "ValueError"
        assert summary.message == "Invalid schema"
    
    def test_with_category(self):
        """Should include category when provided."""
        summary = extract_error_summary(SAMPLE_TRACEBACK, pattern_category="validation")
        
        assert summary is not None
        assert summary.category == "validation"
        assert "[validation]" in summary.to_string()
    
    def test_single_line_error(self):
        """Should handle single-line error messages."""
        summary = extract_error_summary(SINGLE_LINE_ERROR)
        
        assert summary is not None
        assert summary.exception_type == "RuntimeError"
        assert "Failed to load" in summary.message
    
    def test_empty_input(self):
        """Should return None for empty input."""
        assert extract_error_summary("") is None
        assert extract_error_summary(None) is None
    
    def test_long_message_truncation(self):
        """Should truncate very long error messages."""
        long_msg = "ValueError: " + "x" * 500
        summary = extract_error_summary(long_msg)
        
        assert summary is not None
        assert len(summary.message) <= 203  # 200 + "..."
        assert summary.message.endswith("...")


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: collapse_stack_frames
# ═══════════════════════════════════════════════════════════════════════════

class TestCollapseStackFrames:
    """Tests for collapse_stack_frames function."""
    
    def test_short_traceback_unchanged(self):
        """Should not modify traceback with few frames."""
        result = collapse_stack_frames(SAMPLE_TRACEBACK, head_frames=3, tail_frames=3)
        
        # 4 frames total, head+tail=6, so no collapsing
        assert "frames omitted" not in result
    
    def test_long_traceback_collapsed(self):
        """Should collapse middle frames in long traceback."""
        result = collapse_stack_frames(SAMPLE_TRACEBACK_LONG, head_frames=2, tail_frames=2)
        
        assert "frames omitted" in result
        # First 2 frames should be present
        assert "/app/main.py" in result
        assert "/app/step1.py" in result
        # Last 2 frames should be present
        assert "/app/step8.py" in result
        assert "RuntimeError: Deep error" in result
    
    def test_preserves_exception_line(self):
        """Should always preserve the exception line."""
        result = collapse_stack_frames(SAMPLE_TRACEBACK_LONG, head_frames=1, tail_frames=1)
        
        assert "RuntimeError: Deep error" in result
    
    def test_empty_input(self):
        """Should handle empty input."""
        assert collapse_stack_frames("") == ""
        assert collapse_stack_frames(None) == ""


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: detect_fatal_pattern
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectFatalPattern:
    """Tests for detect_fatal_pattern function."""
    
    def test_cuda_oom(self):
        """Should detect CUDA OOM errors."""
        result = detect_fatal_pattern(CUDA_OOM_ERROR)
        assert result is not None
    
    def test_critical_log(self):
        """Should detect CRITICAL log level."""
        result = detect_fatal_pattern("CRITICAL: System failure")
        assert result is not None
    
    def test_error_exception(self):
        """Should detect ERROR: Exception pattern."""
        result = detect_fatal_pattern("ERROR: Exception in node execution")
        assert result is not None
    
    def test_normal_line_no_match(self):
        """Should not match normal log lines."""
        result = detect_fatal_pattern("INFO: Processing completed")
        assert result is None
    
    def test_empty_input(self):
        """Should handle empty input."""
        assert detect_fatal_pattern("") is None
        assert detect_fatal_pattern(None) is None


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: build_context_manifest
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildContextManifest:
    """Tests for build_context_manifest function."""
    
    def test_full_context(self):
        """Should count all context sections."""
        summary = ErrorSummary(exception_type="ValueError", message="test")
        manifest = build_context_manifest(
            traceback_text=SAMPLE_TRACEBACK,
            execution_logs=["line1", "line2", "line3"],
            workflow_json={"node1": {}, "node2": {}},
            system_info={"packages": ["pkg1", "pkg2"]},
            error_summary=summary
        )
        
        assert manifest.traceback_chars > 0
        assert manifest.traceback_frames == 4  # 4 File lines in SAMPLE_TRACEBACK
        assert manifest.logs_lines == 3
        assert manifest.workflow_nodes == 2
        assert manifest.env_packages_included == 2
        assert manifest.summary_present is True
    
    def test_empty_context(self):
        """Should handle empty/None inputs."""
        manifest = build_context_manifest()
        
        assert manifest.traceback_chars == 0
        assert manifest.logs_lines == 0
        assert manifest.workflow_nodes == 0
        assert manifest.summary_present is False
    
    def test_to_dict(self):
        """Should serialize to dict."""
        manifest = build_context_manifest(traceback_text="test")
        d = manifest.to_dict()
        
        assert "traceback_chars" in d
        assert "summary_present" in d
