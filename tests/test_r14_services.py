"""
Tests for R14: LogRingBuffer and PromptComposer.

Coverage:
- LogRingBuffer: add_line, get_recent, sanitization, noise filtering
- PromptComposer: compose, summary-first ordering, legacy format
"""

import pytest
from services.log_ring_buffer import LogRingBuffer, RingBufferConfig, get_ring_buffer, reset_ring_buffer
from services.prompt_composer import PromptComposer, PromptComposerConfig


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: LogRingBuffer
# ═══════════════════════════════════════════════════════════════════════════

class TestLogRingBuffer:
    """Tests for LogRingBuffer class."""
    
    def setup_method(self):
        """Reset global buffer before each test."""
        reset_ring_buffer()
    
    def test_add_and_get_recent(self):
        """Should add lines and retrieve them."""
        buffer = LogRingBuffer(RingBufferConfig(max_lines=100, sanitize_on_retrieval=False))
        buffer.add_line("Line 1")
        buffer.add_line("Line 2")
        buffer.add_line("Line 3")
        
        recent = buffer.get_recent(10)
        assert len(recent) == 3
        assert recent[0] == "Line 1"
        assert recent[2] == "Line 3"
    
    def test_bounded_capacity(self):
        """Should evict old lines when full."""
        config = RingBufferConfig(max_lines=5, sanitize_on_retrieval=False, filter_noise=False)
        buffer = LogRingBuffer(config)
        
        for i in range(10):
            buffer.add_line(f"Line {i}")
        
        assert len(buffer) == 5
        recent = buffer.get_recent(10)
        assert recent[0] == "Line 5"
        assert recent[4] == "Line 9"
    
    def test_noise_filtering(self):
        """Should filter DEBUG/VERBOSE lines when enabled."""
        config = RingBufferConfig(filter_noise=True, sanitize_on_retrieval=False)
        buffer = LogRingBuffer(config)
        
        buffer.add_line("INFO: Normal log")
        buffer.add_line("DEBUG: Verbose detail")
        buffer.add_line("[TRACE] Very verbose")
        buffer.add_line("VERBOSE: More detail")
        buffer.add_line("ERROR: Something failed")
        
        recent = buffer.get_recent(10)
        # Only INFO and ERROR should remain
        assert len(recent) == 2
        assert "Normal log" in recent[0]
        assert "failed" in recent[1]
    
    def test_empty_line_ignored(self):
        """Should ignore empty lines."""
        buffer = LogRingBuffer(RingBufferConfig(sanitize_on_retrieval=False))
        buffer.add_line("")
        buffer.add_line(None)
        buffer.add_line("Valid line")
        
        assert len(buffer) == 1
    
    def test_get_recent_limit(self):
        """Should respect the N limit in get_recent."""
        buffer = LogRingBuffer(RingBufferConfig(sanitize_on_retrieval=False, filter_noise=False))
        for i in range(100):
            buffer.add_line(f"Line {i}")
        
        recent = buffer.get_recent(5)
        assert len(recent) == 5
        assert recent[0] == "Line 95"  # 5 most recent
    
    def test_clear(self):
        """Should clear all lines."""
        buffer = LogRingBuffer()
        buffer.add_line("Line 1")
        buffer.add_line("Line 2")
        buffer.clear()
        
        assert len(buffer) == 0
        assert buffer.is_empty
    
    def test_sanitization_returns_strings(self):
        """Sanitization should return list of strings, not objects."""
        config = RingBufferConfig(sanitize_on_retrieval=True)
        buffer = LogRingBuffer(config)
        
        buffer.add_line("Error at C:\\Users\\TestUser\\Documents\\file.py")
        recent = buffer.get_recent(1, sanitize=True)
        
        assert len(recent) == 1
        # Result should be a string, not a SanitizationResult object
        assert isinstance(recent[0], str)


# ═══════════════════════════════════════════════════════════════════════════
# TESTS: PromptComposer
# ═══════════════════════════════════════════════════════════════════════════

class TestPromptComposer:
    """Tests for PromptComposer class."""
    
    def test_compose_with_summary(self):
        """Should include error_summary first in output."""
        composer = PromptComposer()
        llm_context = {
            "error_summary": "ValueError: Invalid input",
            "node_info": {"node_id": "42", "node_class": "KSampler"},
            "traceback": "Traceback...",
            "execution_logs": ["Log 1", "Log 2"],
            "workflow_subset": {},
            "system_info": {}
        }
        
        result = composer.compose(llm_context)
        
        # Summary should be at the beginning
        lines = result.split("\n")
        assert "Error Summary" in lines[0]
        assert "ValueError: Invalid input" in result
    
    def test_compose_summary_first_order(self):
        """Should order sections: summary → node → traceback → logs."""
        composer = PromptComposer()
        llm_context = {
            "error_summary": "RuntimeError: Test error",
            "node_info": {"node_id": "99"},
            "traceback": "Full traceback here",
            "execution_logs": ["Log entry"],
            "workflow_subset": None,
            "system_info": {}
        }
        
        result = composer.compose(llm_context)
        
        # Find positions
        summary_pos = result.find("Error Summary")
        node_pos = result.find("Failed Node")
        traceback_pos = result.find("Traceback")
        logs_pos = result.find("Recent Logs")
        
        # Verify order
        assert summary_pos < node_pos < traceback_pos < logs_pos
    
    def test_compose_legacy_format(self):
        """Should use legacy format when flag is set."""
        composer = PromptComposer()
        config = PromptComposerConfig(use_legacy_format=True)
        llm_context = {
            "error_summary": "Test error",
            "traceback": "Traceback content",
            "node_info": {"node_id": "1"},
            "workflow_subset": {},
            "system_info": {}
        }
        
        result = composer.compose(llm_context, config)
        
        # Legacy format starts with "Error:"
        assert result.startswith("Error:")
    
    def test_compose_empty_context(self):
        """Should handle empty/minimal context."""
        composer = PromptComposer()
        llm_context = {}
        
        result = composer.compose(llm_context)
        
        # Should not crash, may be empty
        assert isinstance(result, str)
    
    def test_compose_truncation(self):
        """Should truncate long sections."""
        composer = PromptComposer()
        config = PromptComposerConfig(max_traceback_chars=100)
        llm_context = {
            "traceback": "x" * 500,  # 500 chars
        }
        
        result = composer.compose(llm_context, config)
        
        # Should be truncated
        assert "truncated" in result
        assert len(result) < 500 + 100  # Some overhead for section headers
    
    def test_compose_node_info_formatting(self):
        """Should format node info with bullet points."""
        composer = PromptComposer()
        llm_context = {
            "node_info": {
                "node_id": "42",
                "node_name": "My Sampler",
                "node_class": "KSampler",
                "custom_node_path": "/path/to/node"
            }
        }
        
        result = composer.compose(llm_context)
        
        assert "Node ID: #42" in result
        assert "Node Name: My Sampler" in result
        assert "Node Class: KSampler" in result
