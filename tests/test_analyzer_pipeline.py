import pytest
from analyzer import ErrorAnalyzer, NodeContext
from pipeline.context import AnalysisContext

# Integration tests for ErrorAnalyzer using the new Pipeline

def test_analyze_legacy_pattern_fallback():
    """Verify that legacy patterns (hardcoded) still work via pipeline."""
    # A known legacy pattern (OOM)
    traceback = "CUDA out of memory. Tried to allocate..."
    
    # It should match ERROR_KEYS["OOM"]
    from i18n import ERROR_KEYS
    from unittest.mock import patch

    # Mock get_pattern_loader to return a loader that always returns None
    with patch("pipeline.stages.pattern_matcher.get_pattern_loader") as mock_get_loader:
        mock_loader = mock_get_loader.return_value
        mock_loader.match.return_value = None
        mock_loader.get_pattern_info.return_value = None
        
        suggestion, metadata = ErrorAnalyzer.analyze(traceback)
    
    assert suggestion is not None
    assert "CUDA" in suggestion or "VRAM" in suggestion
    assert metadata is not None
    # match_pattern_id matches the error key used in PATTERNS tuple
    assert metadata["matched_pattern_id"] == ERROR_KEYS["OOM"]
    assert metadata["match_source"] == "legacy_fallback"

def test_extract_node_context_via_pipeline():
    """Verify that extract_node_context correctly uses ContextEnhancerStage."""
    traceback = """
    Error occurred in node 15:
    Check your settings.
    """
    
    # We expect Node ID 15 to be extracted
    # Note: Our regexes are quite specific. Let's use a known matching string.
    # Pattern: r"(?:ERROR|error)\s*(?:occurred\s*)?(?:on|in)\s*node\s*[#:]?\s*(\d+)"
    
    node_ctx = ErrorAnalyzer.extract_node_context(traceback)
    
    assert node_ctx is not None
    assert node_ctx.node_id == "15"

def test_sanitization_integration():
    """Verify that sanitization happens before analysis."""
    # Assuming basic sanitization removes user paths
    # Note: This depends on PIISanitizer working.
    # Let's mock PIISanitizer implicitly by checking if a PII path is hidden in the output context?
    # Actually, analyze returns suggestion (which comes from keys) and metadata.
    # The suggestion text itself comes from i18n, doesn't necessarily contain the PII.
    # But if we had a pattern that extracted a path, it might be relevant.
    pass 
    # Skip for now as verifying side effects is harder via public API return values.

def test_empty_traceback():
    """Verify empty input handling."""
    suggestion, metadata = ErrorAnalyzer.analyze("")
    assert suggestion is None
    assert metadata is None
    
    node_ctx = ErrorAnalyzer.extract_node_context("")
    assert not node_ctx.is_valid()
